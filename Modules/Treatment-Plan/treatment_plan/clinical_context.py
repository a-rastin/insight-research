from __future__ import annotations

import asyncio
import hashlib
import json
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping
from uuid import UUID, uuid4

import httpx

from .observability import current_observability


class Dependency(str, Enum):
    PATIENT = "add-new-patient"
    DIAGNOSIS = "diagnosis"
    SEVERITY = "severity"
    MEDICAL_HISTORY = "medical-history"
    DDI = "ddi-checker"
    BN = "bn-manager"


class ContextErrorCode(str, Enum):
    MISSING = "missing"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    CIRCUIT_OPEN = "circuit-open"
    INVALID_SCHEMA = "invalid-schema"
    STALE = "stale"
    CONFLICT = "conflict"


@dataclass(frozen=True)
class ContextError:
    dependency: Dependency
    code: ContextErrorCode
    detail: str
    retryable: bool = False


@dataclass(frozen=True)
class SourceCapture:
    dependency: Dependency
    resource_id: str
    schema_version: str
    retrieved_at: str
    content_hash: str
    etag: str | None = None


@dataclass(frozen=True)
class DependencyResult:
    dependency: Dependency
    value: Mapping[str, Any] | None = None
    source: SourceCapture | None = None
    errors: tuple[ContextError, ...] = ()


@dataclass(frozen=True)
class ClinicalContext:
    patient_id: str
    encounter_id: str
    inputs: Mapping[Dependency, Mapping[str, Any]]
    sources: tuple[SourceCapture, ...]
    findings: tuple[ContextError, ...]

    @property
    def complete(self) -> bool:
        return len(self.inputs) == len(Dependency) and not self.findings


@dataclass(frozen=True)
class RetryPolicy:
    max_attempts: int = 2
    base_delay_seconds: float = 0.025


@dataclass
class _Circuit:
    threshold: int = 3
    reset_seconds: float = 15.0
    failures: int = 0
    opened_at: float | None = None

    def allow(self, now: float) -> bool:
        if self.opened_at is None:
            return True
        if now - self.opened_at >= self.reset_seconds:
            self.failures = 0
            self.opened_at = None
            return True
        return False

    def success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def failure(self, now: float) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = now


def _is_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_uuid(value: Any) -> bool:
    try:
        return str(UUID(str(value))) == str(value).lower()
    except (ValueError, TypeError, AttributeError):
        return False


def _validate_common(payload: Any, required: Mapping[str, Callable[[Any], bool]]) -> list[str]:
    if not isinstance(payload, dict):
        return ["response must be an object"]
    errors = []
    allowed = set(required) | {"observedAt", "status"}
    unknown = set(payload) - allowed
    if unknown:
        errors.append("unexpected fields: " + ", ".join(sorted(unknown)))
    for key, predicate in required.items():
        if key not in payload:
            errors.append(f"{key} is required")
        elif not predicate(payload[key]):
            errors.append(f"{key} is invalid")
    if payload.get("schemaVersion") != "1.0.0":
        errors.append("schemaVersion must be 1.0.0")
    return errors


_list = lambda value: isinstance(value, list)
_dict = lambda value: isinstance(value, dict)


class _RestAdapter:
    """Internal seam: all remote-read resilience and contract enforcement lives here."""

    dependency: Dependency
    required: Mapping[str, Callable[[Any], bool]]
    resource_field: str

    def __init__(self, base_url: str, client: httpx.AsyncClient, timeout_seconds: float,
                 retry: RetryPolicy, circuit: _Circuit, clock: Callable[[], float] = time.monotonic):
        self._base_url = base_url.rstrip("/")
        self._client = client
        self._timeout = timeout_seconds
        self._retry = retry
        self._circuit = circuit
        self._clock = clock

    async def read(self, patient_id: str, encounter_id: str, deadline: float) -> DependencyResult:
        now = self._clock()
        if not self._circuit.allow(now):
            return self._error(ContextErrorCode.CIRCUIT_OPEN, "dependency circuit is open", True)
        url = self._url(patient_id, encounter_id)
        last: ContextError | None = None
        for attempt in range(self._retry.max_attempts):
            remaining = deadline - self._clock()
            if remaining <= 0:
                return self._error(ContextErrorCode.TIMEOUT, "request deadline exhausted", True)
            try:
                response = await self._client.get(url, headers={"Accept": "application/json", "X-Schema-Version": "1.0.0"},
                                                  timeout=min(self._timeout, remaining))
                if response.status_code == 404:
                    self._circuit.success()
                    return self._error(ContextErrorCode.MISSING, "dependency has no matching resource")
                if response.status_code in {408, 425, 429, 500, 502, 503, 504}:
                    last = ContextError(self.dependency, ContextErrorCode.UNAVAILABLE,
                                        f"dependency returned HTTP {response.status_code}", True)
                    raise _Retryable()
                response.raise_for_status()
                payload = response.json()
                schema_errors = _validate_common(payload, self.required)
                if schema_errors:
                    self._circuit.success()
                    return self._error(ContextErrorCode.INVALID_SCHEMA, "; ".join(schema_errors))
                content = response.content
                source = SourceCapture(self.dependency, str(payload[self.resource_field]), "1.0.0",
                                       datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                                       "sha256:" + hashlib.sha256(content).hexdigest(), response.headers.get("etag"))
                self._circuit.success()
                return DependencyResult(self.dependency, payload, source)
            except (httpx.TimeoutException, asyncio.TimeoutError):
                last = ContextError(self.dependency, ContextErrorCode.TIMEOUT, "dependency read timed out", True)
            except _Retryable:
                pass
            except (httpx.HTTPError, ValueError, json.JSONDecodeError) as exc:
                last = ContextError(self.dependency, ContextErrorCode.UNAVAILABLE,
                                    f"dependency read failed: {type(exc).__name__}", True)
            if attempt + 1 < self._retry.max_attempts:
                delay = self._retry.base_delay_seconds * (2 ** attempt) * random.uniform(0.8, 1.2)
                await asyncio.sleep(min(delay, max(0.0, deadline - self._clock())))
        self._circuit.failure(self._clock())
        assert last is not None
        return DependencyResult(self.dependency, errors=(last,))

    def _error(self, code: ContextErrorCode, detail: str, retryable: bool = False) -> DependencyResult:
        return DependencyResult(self.dependency, errors=(ContextError(self.dependency, code, detail, retryable),))

    def _url(self, patient_id: str, encounter_id: str) -> str:
        raise NotImplementedError


class _Retryable(Exception):
    pass


_base = {"schemaVersion": _is_string, "patientId": _is_uuid, "encounterId": _is_uuid}


class _PatientAdapter(_RestAdapter):
    dependency = Dependency.PATIENT
    resource_field = "resourceId"
    required = {**_base, "resourceId": _is_string, "currentMedications": _list}
    def _url(self, patient_id: str, encounter_id: str) -> str:
        return f"{self._base_url}/api/add-new-patient/v1/patients/{patient_id}/encounters/{encounter_id}"


class _DiagnosisAdapter(_RestAdapter):
    dependency = Dependency.DIAGNOSIS
    resource_field = "assessmentId"
    required = {**_base, "assessmentId": _is_string, "diagnosis": _dict}
    def _url(self, patient_id: str, encounter_id: str) -> str:
        return f"{self._base_url}/api/diagnosis/v1/patients/{patient_id}/encounters/{encounter_id}/latest"


class _SeverityAdapter(_RestAdapter):
    dependency = Dependency.SEVERITY
    resource_field = "assessmentId"
    required = {**_base, "assessmentId": _is_string, "severity": _dict}
    def _url(self, patient_id: str, encounter_id: str) -> str:
        return f"{self._base_url}/api/severity/v1/patients/{patient_id}/encounters/{encounter_id}/latest"


class _MedicalHistoryAdapter(_RestAdapter):
    dependency = Dependency.MEDICAL_HISTORY
    resource_field = "assessmentId"
    required = {**_base, "assessmentId": _is_string, "medicalHistory": _dict}
    def _url(self, patient_id: str, encounter_id: str) -> str:
        return f"{self._base_url}/api/medical-history/v1/patients/{patient_id}/encounters/{encounter_id}/latest"


class _DdiAdapter(_RestAdapter):
    dependency = Dependency.DDI
    resource_field = "checkId"
    required = {**_base, "checkId": _is_string, "knowledgeVersion": _is_string, "findings": _list}
    def _url(self, patient_id: str, encounter_id: str) -> str:
        return f"{self._base_url}/api/ddi-checker/v1/patients/{patient_id}/encounters/{encounter_id}/latest"


class _BnAdapter(_RestAdapter):
    dependency = Dependency.BN
    resource_field = "evaluationId"
    required = {**_base, "evaluationId": _is_string, "modelId": _is_string, "modelVersion": _is_string, "evaluation": _dict}
    def _url(self, patient_id: str, encounter_id: str) -> str:
        return f"{self._base_url}/api/bn-manager/v1/patients/{patient_id}/encounters/{encounter_id}/latest"


class ClinicalContextAssembler:
    """Fetch one honest clinical context; partial results and every finding are returned."""

    _types = (_PatientAdapter, _DiagnosisAdapter, _SeverityAdapter, _MedicalHistoryAdapter, _DdiAdapter, _BnAdapter)

    def __init__(self, endpoints: Mapping[Dependency, str], client: httpx.AsyncClient, *,
                 request_deadline_seconds: float = 3.0, dependency_timeout_seconds: float = 1.0,
                 max_attempts: int = 2, stale_after_seconds: float = 900.0,
                 clock: Callable[[], float] = time.monotonic):
        missing = set(Dependency) - set(endpoints)
        if missing:
            raise ValueError("missing dependency endpoints: " + ", ".join(sorted(x.value for x in missing)))
        self._clock = clock
        self._deadline = request_deadline_seconds
        self._stale_after = stale_after_seconds
        retry = RetryPolicy(max_attempts=max_attempts)
        self._adapters = tuple(cls(endpoints[cls.dependency], client, dependency_timeout_seconds, retry, _Circuit(), clock)
                               for cls in self._types)

    async def assemble(self, patient_id: str, encounter_id: str) -> ClinicalContext:
        if not _is_uuid(patient_id) or not _is_uuid(encounter_id):
            raise ValueError("patient_id and encounter_id must be canonical UUIDs")
        started = self._clock()
        deadline = started + self._deadline
        tasks = [asyncio.create_task(adapter.read(patient_id, encounter_id, deadline)) for adapter in self._adapters]
        done, pending = await asyncio.wait(tasks, timeout=max(0.0, deadline - self._clock()))
        for task in pending:
            task.cancel()
        results = [task.result() for task in done]
        completed = {result.dependency for result in results}
        results.extend(DependencyResult(dep, errors=(ContextError(dep, ContextErrorCode.TIMEOUT,
                                                                  "strict request deadline exhausted", True),))
                       for dep in Dependency if dep not in completed)
        inputs: dict[Dependency, Mapping[str, Any]] = {}
        sources: list[SourceCapture] = []
        findings: list[ContextError] = []
        for result in results:
            findings.extend(result.errors)
            if result.value is None:
                continue
            if result.value["patientId"] != patient_id or result.value["encounterId"] != encounter_id:
                findings.append(ContextError(result.dependency, ContextErrorCode.CONFLICT,
                                             "response identifiers conflict with the requested context"))
                continue
            observed = result.value.get("observedAt")
            if observed and self._is_stale(observed):
                findings.append(ContextError(result.dependency, ContextErrorCode.STALE,
                                             "source observation exceeds the configured freshness limit"))
            inputs[result.dependency] = result.value
            if result.source:
                sources.append(result.source)
        observer = current_observability()
        elapsed_ms = max(0.0, (self._clock() - started) * 1000)
        for result in results:
            outcome = "failure" if result.errors else "success"
            observer.metric("tp_dependency_latency_ms", elapsed_ms,
                            labels={"dependency": result.dependency.value, "outcome": outcome})
            if result.errors:
                observer.metric("tp_dependency_failure_total", labels={"dependency": result.dependency.value, "outcome": "failure"})
            if result.value is None:
                observer.metric("tp_missing_input_total", labels={"dependency": result.dependency.value, "kind": "clinical-context"})
        return ClinicalContext(patient_id, encounter_id, inputs, tuple(sources), tuple(findings))

    def _is_stale(self, value: str) -> bool:
        try:
            observed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return (datetime.now(timezone.utc) - observed).total_seconds() > self._stale_after
        except (ValueError, TypeError):
            return True

