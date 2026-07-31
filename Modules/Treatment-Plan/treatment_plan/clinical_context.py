from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import json
import random
import re
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx

from .observability import current_observability


class Dependency(str, Enum):
    PATIENT = "add-new-patient"
    DIAGNOSIS = "diagnosis"
    SEVERITY = "severity"
    MEDICAL_HISTORY = "medical-history"
    SUICIDE_RISK = "suicide-risk"


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
    interface_version: str
    schema_version: str
    resource_version: int
    retrieved_at: str
    content_hash: str
    etag: str
    source_versions: Mapping[str, str | int]
    provider_content_hash: str | None = None


@dataclass(frozen=True)
class DependencyResult:
    dependency: Dependency
    value: Mapping[str, Any] | None = None
    source: SourceCapture | None = None
    observed_at: str | None = None
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
class OutboundRequestContext:
    session_cookie_value: str
    parent_request_id: str
    correlation_id: str

    def __post_init__(self) -> None:
        if not self.session_cookie_value or any(char in self.session_cookie_value for char in ";\r\n"):
            raise ValueError("session cookie value is invalid")
        if not _is_uuid(self.parent_request_id) or not _is_uuid(self.correlation_id):
            raise ValueError("request context identifiers must be canonical UUIDs")


@dataclass(frozen=True)
class ServiceAuthConfig:
    service_id: str
    key_id: str
    destination_secrets: Mapping[Dependency, bytes]
    session_cookie_name: str = "insight_session"

    def __post_init__(self) -> None:
        if not self.service_id or not self.key_id:
            raise ValueError("service authentication identity is required")
        if set(self.destination_secrets) != set(Dependency):
            raise ValueError("one service secret is required for every clinical dependency")
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", self.session_cookie_name):
            raise ValueError("session cookie name is invalid")
        if any(not isinstance(secret, bytes) or len(secret) < 32 for secret in self.destination_secrets.values()):
            raise ValueError("service authentication secrets must contain at least 256 bits")


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


def _is_uuid(value: Any) -> bool:
    if not isinstance(value, str) or not re.fullmatch(
        r"[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", value
    ):
        return False
    try:
        return UUID(value).int != 0
    except ValueError:
        return False


def _utc(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.tzinfo is not None
    except ValueError:
        return False


def _object(value: Any, required: set[str], allowed: set[str] | None = None) -> list[str]:
    if not isinstance(value, dict):
        return ["response must be an object"]
    errors = [f"{key} is required" for key in sorted(required - set(value))]
    if allowed is not None and set(value) - allowed:
        errors.append("unexpected fields: " + ", ".join(sorted(set(value) - allowed)))
    return errors


def _version(value: Any, expected: str, field: str) -> list[str]:
    return [] if value == expected else [f"{field} must be {expected}"]


def _identity(payload: Mapping[str, Any], resource_field: str) -> list[str]:
    return [f"{field} must be a canonical UUID" for field in (resource_field, "patientId", "encounterId")
            if not _is_uuid(payload.get(field))]


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _strong_etag(value: str | None) -> bool:
    return bool(value and re.fullmatch(r'"[^"\r\n]+"', value))


def _validate_patient(payload: Any) -> list[str]:
    required = {"intakeSnapshotId", "patientId", "encounterId", "schemaVersion", "resourceVersion",
                "presentingComplaint", "provisionalDiagnosis", "treatmentHistory", "allergies",
                "currentMedications", "riskFlags", "provenance"}
    errors = _object(payload, required, required)
    if errors or not isinstance(payload, dict):
        return errors
    errors += _identity(payload, "intakeSnapshotId") + _version(payload.get("schemaVersion"), "2.0.0", "schemaVersion")
    if not _positive_int(payload.get("resourceVersion")):
        errors.append("resourceVersion is invalid")
    for field in ("presentingComplaint", "provisionalDiagnosis"):
        if not isinstance(payload.get(field), str) or not payload[field]:
            errors.append(f"{field} is invalid")
    for field in ("treatmentHistory", "allergies", "currentMedications"):
        if not isinstance(payload.get(field), list) or any(not isinstance(item, str) for item in payload.get(field, [])):
            errors.append(f"{field} is invalid")
    risk = payload.get("riskFlags")
    errors += _object(risk, {"suicidality", "substanceUse"}, {"suicidality", "substanceUse"})
    if isinstance(risk, dict) and (risk.get("suicidality") not in {"suicidality_none", "ideation", "plan", "attempt"}
                                   or not isinstance(risk.get("substanceUse"), bool)):
        errors.append("riskFlags is invalid")
    provenance = payload.get("provenance")
    errors += _object(provenance, {"sourceModule", "createdByUserId", "createdAt", "updatedAt"},
                      {"sourceModule", "createdByUserId", "createdAt", "updatedAt", "legacyIntakeId"})
    if isinstance(provenance, dict) and (provenance.get("sourceModule") != "add-new-patient"
                                        or not _utc(provenance.get("createdAt")) or not _utc(provenance.get("updatedAt"))):
        errors.append("provenance is invalid")
    return errors


def _validate_diagnosis(payload: Any) -> list[str]:
    required = {"assessmentId", "patientId", "encounterId", "checkedCriteria", "evaluation", "clinicianDecision",
                "ruleVersion", "schemaVersion", "status", "resourceVersion", "createdAt", "updatedAt", "provenance"}
    errors = _object(payload, required, required)
    if errors or not isinstance(payload, dict):
        return errors
    errors += _identity(payload, "assessmentId") + _version(payload.get("schemaVersion"), "2.0.0", "schemaVersion")
    if payload.get("ruleVersion") != "diagnosis-rules-1.0.0" or payload.get("status") not in {"initialized", "in-progress", "decided"}:
        errors.append("diagnosis rule version or status is invalid")
    if not _positive_int(payload.get("resourceVersion")) or not _utc(payload.get("createdAt")) or not _utc(payload.get("updatedAt")):
        errors.append("diagnosis resource version or timestamps are invalid")
    criteria = payload.get("checkedCriteria")
    allowed_criteria = {"A1", "A2", "A3", "A4", "A5", "A6", "B1", "C1", "D1"}
    if not isinstance(criteria, list) or len(criteria) != len(set(criteria)) or not set(criteria) <= allowed_criteria:
        errors.append("checkedCriteria is invalid")
    evaluation = payload.get("evaluation")
    evaluation_fields = {"met", "aCount", "coreCount", "failures", "reason", "checkedCriteria", "ruleVersion"}
    errors += _object(evaluation, evaluation_fields, evaluation_fields)
    if isinstance(evaluation, dict) and (not isinstance(evaluation.get("met"), bool)
                                         or evaluation.get("ruleVersion") != "diagnosis-rules-1.0.0"):
        errors.append("evaluation is invalid")
    decision = payload.get("clinicianDecision")
    if decision is not None:
        errors += _object(decision, {"type", "actorUserId", "recordedAt"}, {"type", "actorUserId", "recordedAt"})
        if isinstance(decision, dict) and (decision.get("type") not in {"confirmed", "bypass"} or not _utc(decision.get("recordedAt"))):
            errors.append("clinicianDecision is invalid")
    provenance = payload.get("provenance")
    provenance_fields = {"sourceModule", "createdByUserId", "lastUpdatedByUserId"}
    errors += _object(provenance, provenance_fields, provenance_fields)
    if isinstance(provenance, dict) and provenance.get("sourceModule") != "diagnosis":
        errors.append("provenance is invalid")
    return errors


def _validate_severity(payload: Any) -> list[str]:
    required = {"interfaceVersion", "schemaVersion", "assessmentId", "patientId", "encounterId", "assessmentType",
                "status", "itemScores", "scores", "evaluation", "resourceVersion", "provenance"}
    errors = _object(payload, required, required)
    if errors or not isinstance(payload, dict):
        return errors
    errors += _identity(payload, "assessmentId")
    errors += _version(payload.get("interfaceVersion"), "2.0.0", "interfaceVersion")
    errors += _version(payload.get("schemaVersion"), "2.0.0", "schemaVersion")
    if payload.get("assessmentType") != "PANSS" or payload.get("status") not in {"in-progress", "completed", "skipped"}:
        errors.append("assessment type or status is invalid")
    item_scores = payload.get("itemScores")
    item_codes = {f"P{index}" for index in range(1, 8)} | {f"N{index}" for index in range(1, 8)} | {
        f"G{index}" for index in range(1, 17)}
    if (not _positive_int(payload.get("resourceVersion")) or not isinstance(item_scores, dict)
            or not set(item_scores) <= item_codes
            or any(not isinstance(score, int) or isinstance(score, bool) or not 1 <= score <= 7
                   for score in item_scores.values())):
        errors.append("severity resource version or item scores are invalid")
    evaluation = payload.get("evaluation")
    evaluation_fields = {"state", "missingItemCodes", "scores", "scaleVersion", "ruleVersion"}
    errors += _object(evaluation, evaluation_fields, evaluation_fields)
    if isinstance(evaluation, dict) and (evaluation.get("state") not in {"incomplete", "passed", "completed"}
                                         or evaluation.get("scaleVersion") != "PANSS-30-1.0.0"
                                         or evaluation.get("ruleVersion") != "PANSS-SUM-2.0.0"
                                         or not isinstance(evaluation.get("missingItemCodes"), list)
                                         or not set(evaluation.get("missingItemCodes", [])) <= item_codes):
        errors.append("severity evaluation is invalid")
    status = payload.get("status")
    if status == "completed" and (not isinstance(item_scores, dict) or set(item_scores) != item_codes
                                  or payload.get("scores") is None or not isinstance(evaluation, dict)
                                  or evaluation.get("state") != "completed" or evaluation.get("missingItemCodes")
                                  or evaluation.get("scores") != payload.get("scores")):
        errors.append("completed severity assessment is inconsistent")
    if status == "in-progress" and (not isinstance(item_scores, dict) or len(item_scores) > 29
                                    or payload.get("scores") is not None or not isinstance(evaluation, dict)
                                    or evaluation.get("state") != "incomplete" or not evaluation.get("missingItemCodes")
                                    or evaluation.get("scores") is not None):
        errors.append("in-progress severity assessment is inconsistent")
    if status == "skipped" and (item_scores != {} or payload.get("scores") is not None or not isinstance(evaluation, dict)
                                or evaluation.get("state") != "passed" or evaluation.get("missingItemCodes")
                                or evaluation.get("scores") is not None):
        errors.append("skipped severity assessment is inconsistent")
    provenance = payload.get("provenance")
    provenance_fields = {"sourceModule", "createdAt", "updatedAt", "createdRequestId", "updatedRequestId", "scaleVersion", "ruleVersion"}
    errors += _object(provenance, provenance_fields, provenance_fields)
    if isinstance(provenance, dict) and (provenance.get("sourceModule") != "severity"
                                        or not _utc(provenance.get("createdAt")) or not _utc(provenance.get("updatedAt"))
                                        or not _is_uuid(provenance.get("createdRequestId")) or not _is_uuid(provenance.get("updatedRequestId"))):
        errors.append("severity provenance is invalid")
    return errors


def _validate_medical_history(payload: Any) -> list[str]:
    required = {"interfaceVersion", "schemaVersion", "assessmentId", "patientId", "encounterId", "status",
                "pastMedicalHistory", "medications", "substantialSuicideRisk", "priorAntipsychoticTherapy",
                "priorAntipsychoticTherapySuccessful", "antipsychotic", "clozapineContraindication",
                "clozapineContraindications", "recurrentNonAdherenceDeterioration", "actor", "createdAt", "updatedAt",
                "resourceVersion", "provenance"}
    errors = _object(payload, required, required)
    if errors or not isinstance(payload, dict):
        return errors
    errors += _identity(payload, "assessmentId")
    errors += _version(payload.get("interfaceVersion"), "2.0.0", "interfaceVersion")
    errors += _version(payload.get("schemaVersion"), "2.0.0", "schemaVersion")
    states = {"yes", "no", "unknown", "not-assessed"}
    if payload.get("status") not in {"in-progress", "completed", "not-assessed"}:
        errors.append("medical history status is invalid")
    for field in ("substantialSuicideRisk", "priorAntipsychoticTherapy", "priorAntipsychoticTherapySuccessful",
                  "clozapineContraindication", "recurrentNonAdherenceDeterioration"):
        if payload.get(field) not in states:
            errors.append(f"{field} is invalid")
    medications = payload.get("medications")
    if not isinstance(medications, list) or len(medications) > 20:
        errors.append("medications is invalid")
    else:
        for medication in medications:
            fields = {"originalText", "doseText", "routeText", "frequencyText", "normalizedIdentity"}
            errors += _object(medication, fields, fields)
            identity = medication.get("normalizedIdentity") if isinstance(medication, dict) else None
            identity_fields = {"state", "conceptId", "display", "terminologyVersion"}
            errors += _object(identity, identity_fields, identity_fields)
            if isinstance(identity, dict):
                state = identity.get("state")
                if state not in {"matched", "unresolved", "ambiguous", "not-assessed"}:
                    errors.append("medication normalized identity is invalid")
                elif state == "matched" and (not identity.get("conceptId") or not identity.get("display")):
                    errors.append("matched medication identity is incomplete")
                elif state != "matched" and any(identity.get(field) is not None for field in ("conceptId", "display", "terminologyVersion")):
                    errors.append("unresolved medication identity contains resolved fields")
    if not _positive_int(payload.get("resourceVersion")) or not _utc(payload.get("createdAt")) or not _utc(payload.get("updatedAt")):
        errors.append("medical history resource version or timestamps are invalid")
    actor = payload.get("actor")
    errors += _object(actor, {"actorId", "role"}, {"actorId", "role"})
    if isinstance(actor, dict) and (not _is_uuid(actor.get("actorId")) or actor.get("role") != "psychiatrist"):
        errors.append("actor is invalid")
    provenance = payload.get("provenance")
    provenance_fields = {"sourceModule", "optionSetVersion", "createdRequestId", "updatedRequestId"}
    errors += _object(provenance, provenance_fields, provenance_fields)
    if isinstance(provenance, dict) and (provenance.get("sourceModule") != "medical-history"
                                        or provenance.get("optionSetVersion") != "2.0.0"
                                        or not _is_uuid(provenance.get("createdRequestId"))
                                        or not _is_uuid(provenance.get("updatedRequestId"))):
        errors.append("medical history provenance is invalid")
    if payload.get("priorAntipsychoticTherapy") == "yes" and not isinstance(payload.get("antipsychotic"), str):
        errors.append("antipsychotic is required after prior therapy")
    if payload.get("priorAntipsychoticTherapy") != "yes" and (payload.get("antipsychotic") is not None
                                                               or payload.get("priorAntipsychoticTherapySuccessful") != "not-assessed"):
        errors.append("prior therapy conditional fields are inconsistent")
    contraindications = payload.get("clozapineContraindications")
    if (payload.get("clozapineContraindication") == "yes" and not contraindications) or (
            payload.get("clozapineContraindication") != "yes" and contraindications != []):
        errors.append("clozapine contraindication fields are inconsistent")
    return errors


def _validate_suicide_risk(payload: Any) -> list[str]:
    wrapper_fields = {"interfaceVersion", "schemaVersion", "snapshotType", "patientId", "encounterId", "source", "assessment"}
    errors = _object(payload, wrapper_fields, wrapper_fields)
    if errors or not isinstance(payload, dict):
        return errors
    errors += _version(payload.get("interfaceVersion"), "1.0.0", "interfaceVersion")
    errors += _version(payload.get("schemaVersion"), "1.0.0", "schemaVersion")
    if payload.get("snapshotType") != "suicide-risk-encounter-snapshot" or not _is_uuid(payload.get("patientId")) or not _is_uuid(payload.get("encounterId")):
        errors.append("suicide-risk snapshot identity is invalid")
    source = payload.get("source")
    source_fields = {"owner", "assessmentId", "resourceVersion", "etag", "contentSha256"}
    errors += _object(source, source_fields, source_fields)
    if isinstance(source, dict) and (source.get("owner") != "suicide-risk" or not _is_uuid(source.get("assessmentId"))
                                    or not _positive_int(source.get("resourceVersion"))
                                    or not _strong_etag(source.get("etag"))
                                    or not re.fullmatch(r"[0-9a-f]{64}", str(source.get("contentSha256", "")))):
        errors.append("suicide-risk source is invalid")
    assessment = payload.get("assessment")
    assessment_fields = {"interfaceVersion", "schemaVersion", "assessmentId", "patientId", "encounterId", "assessmentType",
                         "instrument", "riskState", "riskScore", "safetyDisposition", "actor", "createdAt", "updatedAt",
                         "resourceVersion", "provenance"}
    errors += _object(assessment, assessment_fields, assessment_fields)
    if isinstance(assessment, dict):
        errors += _identity(assessment, "assessmentId")
        errors += _version(assessment.get("interfaceVersion"), "1.0.0", "assessment.interfaceVersion")
        errors += _version(assessment.get("schemaVersion"), "1.0.0", "assessment.schemaVersion")
        if (assessment.get("assessmentType") != "psychiatrist-suicide-risk-assertion"
                or assessment.get("riskState") not in {
                    "unknown", "unavailable", "conflicting", "not-elevated",
                    "imminent-suicide-risk", "substantial-suicide-risk-requiring-urgent-evaluation",
                }
                or assessment.get("riskScore") is not None or not _positive_int(assessment.get("resourceVersion"))
                or not _utc(assessment.get("createdAt")) or not _utc(assessment.get("updatedAt"))):
            errors.append("suicide-risk state is invalid")
        instrument = assessment.get("instrument")
        instrument_fields = {"name", "completionClaimed", "sourceLicensingStatus", "questionsDefined", "scoringDefined"}
        errors += _object(instrument, instrument_fields, instrument_fields)
        if isinstance(instrument, dict) and instrument != {"name": "C-SSRS", "completionClaimed": False,
                                                           "sourceLicensingStatus": "unavailable",
                                                           "questionsDefined": False, "scoringDefined": False}:
            errors.append("suicide-risk instrument boundary is invalid")
        disposition = assessment.get("safetyDisposition")
        disposition_fields = {"outcome", "code", "routinePlanningAllowed", "overrideAllowed", "persistentUntilResolved", "guidance"}
        errors += _object(disposition, disposition_fields, disposition_fields)
        if isinstance(disposition, dict):
            risk_state = assessment.get("riskState")
            if risk_state == "not-elevated":
                valid = (
                    disposition.get("outcome") == "allowed"
                    and disposition.get("code") == "TP_SUICIDE_RISK_NOT_ELEVATED"
                    and disposition.get("routinePlanningAllowed") is True
                    and disposition.get("overrideAllowed") is False
                    and disposition.get("persistentUntilResolved") is False
                    and disposition.get("guidance")
                )
            else:
                valid = (
                    disposition.get("outcome") in {"blocked", "emergency-blocked"}
                    and disposition.get("code") in {
                        "TP_SUICIDE_RISK_UNAVAILABLE",
                        "TP_REQUIRED_DATA_CONFLICTING",
                        "TP_EMERGENCY_ACTION_REQUIRED",
                    }
                    and disposition.get("routinePlanningAllowed") is False
                    and disposition.get("overrideAllowed") is False
                    and disposition.get("persistentUntilResolved") is True
                    and disposition.get("guidance")
                )
            if not valid:
                errors.append("suicide-risk disposition is invalid")
        actor = assessment.get("actor")
        errors += _object(actor, {"actorId", "role"}, {"actorId", "role"})
        if isinstance(actor, dict) and (not _is_uuid(actor.get("actorId")) or actor.get("role") != "psychiatrist"):
            errors.append("suicide-risk actor is invalid")
        provenance = assessment.get("provenance")
        provenance_fields = {"sourceModule", "policyVersion", "governanceVersion", "createdRequestId", "updatedRequestId"}
        errors += _object(provenance, provenance_fields, provenance_fields)
        if (not isinstance(provenance, dict) or provenance.get("sourceModule") != "suicide-risk"
                or provenance.get("policyVersion") != "insight.treatment-plan-safety-policy/1.0.0"
                or provenance.get("governanceVersion") != "insight.clinical-ownership/1.0.0"):
            errors.append("suicide-risk provenance is invalid")
        if isinstance(source, dict) and (source.get("assessmentId") != assessment.get("assessmentId")
                                        or source.get("resourceVersion") != assessment.get("resourceVersion")):
            errors.append("suicide-risk source conflicts with assessment")
        if assessment.get("patientId") != payload.get("patientId") or assessment.get("encounterId") != payload.get("encounterId"):
            errors.append("suicide-risk wrapper conflicts with assessment")
    return errors


class _Retryable(Exception):
    pass


class _RestAdapter:
    dependency: Dependency
    interface_version: str
    schema_version: str
    resource_field: str
    validator: Callable[[Any], list[str]]

    def __init__(self, base_url: str, client: httpx.AsyncClient, timeout_seconds: float, retry: RetryPolicy,
                 circuit: _Circuit, service_auth: ServiceAuthConfig, clock: Callable[[], float],
                 wall_clock: Callable[[], datetime]):
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
            raise ValueError(f"invalid endpoint origin for {self.dependency.value}")
        self._base_url = base_url.rstrip("/")
        self._client = client
        self._timeout = timeout_seconds
        self._retry = retry
        self._circuit = circuit
        self._service_auth = service_auth
        self._clock = clock
        self._wall_clock = wall_clock

    async def read(self, patient_id: str, encounter_id: str, severity_assessment_id: str,
                   request_context: OutboundRequestContext, deadline: float) -> DependencyResult:
        now = self._clock()
        if not self._circuit.allow(now):
            return self._error(ContextErrorCode.CIRCUIT_OPEN, "dependency circuit is open", True)
        path = self._path(patient_id, encounter_id, severity_assessment_id)
        url = self._base_url + path
        last: ContextError | None = None
        for attempt in range(self._retry.max_attempts):
            remaining = deadline - self._clock()
            if remaining <= 0:
                return self._error(ContextErrorCode.TIMEOUT, "request deadline exhausted", True)
            try:
                headers = self._headers(path, request_context)
                response = await self._client.get(url, headers=headers, timeout=min(self._timeout, remaining), follow_redirects=False)
                if response.status_code == 404:
                    self._circuit.success()
                    return self._error(ContextErrorCode.MISSING, "dependency has no matching resource")
                if response.status_code in {408, 425, 429, 500, 502, 503, 504}:
                    last = ContextError(self.dependency, ContextErrorCode.UNAVAILABLE,
                                        f"dependency returned HTTP {response.status_code}", True)
                    raise _Retryable()
                response.raise_for_status()
                payload = response.json()
                schema_errors = self.validator(payload)
                response_schema = response.headers.get("X-Schema-Version")
                if response_schema != self.schema_version:
                    schema_errors.append(f"X-Schema-Version must be {self.schema_version}")
                etag = response.headers.get("ETag")
                if not _strong_etag(etag):
                    schema_errors.append("a strong ETag is required")
                if self.dependency is Dependency.SEVERITY and isinstance(payload, dict) and payload.get("assessmentId") != severity_assessment_id:
                    schema_errors.append("assessmentId conflicts with the requested severity resource")
                if self.dependency is Dependency.SUICIDE_RISK and isinstance(payload, dict) and isinstance(payload.get("source"), dict) and payload["source"].get("etag") != etag:
                    schema_errors.append("response ETag conflicts with suicide-risk source")
                if schema_errors:
                    self._circuit.success()
                    return self._error(ContextErrorCode.INVALID_SCHEMA, "; ".join(schema_errors))
                assert isinstance(payload, dict) and etag is not None
                source = SourceCapture(
                    self.dependency,
                    self._resource_id(payload),
                    self.interface_version,
                    self.schema_version,
                    self._resource_version(payload),
                    self._wall_clock().astimezone(timezone.utc).isoformat().replace("+00:00", "Z"),
                    "sha256:" + hashlib.sha256(response.content).hexdigest(),
                    etag,
                    self._source_versions(payload),
                    self._provider_content_hash(payload),
                )
                self._circuit.success()
                return DependencyResult(self.dependency, payload, source, self._observed_at(payload))
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

    def _headers(self, path: str, context: OutboundRequestContext) -> dict[str, str]:
        request_id = str(uuid4())
        timestamp = str(int(self._wall_clock().timestamp()))
        nonce = secrets.token_hex(16)
        content_hash = hashlib.sha256(b"").hexdigest()
        fields = ("INSIGHT-HMAC-V1", self._service_auth.service_id, self._service_auth.key_id, timestamp, nonce,
                  self.dependency.value, "GET", path, content_hash, request_id, context.correlation_id,
                  context.parent_request_id)
        canonical = "\n".join(fields).encode("utf-8")
        signature = hmac.new(self._service_auth.destination_secrets[self.dependency], canonical, hashlib.sha256).digest()
        return {
            "Accept": "application/json",
            "Cookie": f"{self._service_auth.session_cookie_name}={context.session_cookie_value}",
            "X-Request-ID": request_id,
            "X-Correlation-ID": context.correlation_id,
            "X-Causation-ID": context.parent_request_id,
            "X-Insight-Service-ID": self._service_auth.service_id,
            "X-Insight-Key-ID": self._service_auth.key_id,
            "X-Insight-Timestamp": timestamp,
            "X-Insight-Nonce": nonce,
            "X-Insight-Content-SHA256": content_hash,
            "X-Insight-Signature": "v1=" + base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii"),
        }

    def _error(self, code: ContextErrorCode, detail: str, retryable: bool = False) -> DependencyResult:
        return DependencyResult(self.dependency, errors=(ContextError(self.dependency, code, detail, retryable),))

    def _path(self, patient_id: str, encounter_id: str, severity_assessment_id: str) -> str:
        raise NotImplementedError

    def _resource_id(self, payload: Mapping[str, Any]) -> str:
        return str(payload[self.resource_field])

    def _resource_version(self, payload: Mapping[str, Any]) -> int:
        return int(payload["resourceVersion"])

    def _source_versions(self, payload: Mapping[str, Any]) -> Mapping[str, str | int]:
        return {"resourceVersion": self._resource_version(payload)}

    def _observed_at(self, payload: Mapping[str, Any]) -> str | None:
        return None

    def _provider_content_hash(self, payload: Mapping[str, Any]) -> str | None:
        return None


class _PatientAdapter(_RestAdapter):
    dependency = Dependency.PATIENT
    interface_version = "2.0.0"
    schema_version = "2.0.0"
    resource_field = "intakeSnapshotId"
    validator = staticmethod(_validate_patient)

    def _path(self, patient_id: str, encounter_id: str, severity_assessment_id: str) -> str:
        return f"/api/add-new-patient/v2/encounters/{encounter_id}/intake-snapshot"

    def _observed_at(self, payload: Mapping[str, Any]) -> str:
        return str(payload["provenance"]["updatedAt"])


class _DiagnosisAdapter(_RestAdapter):
    dependency = Dependency.DIAGNOSIS
    interface_version = "2.0.0"
    schema_version = "2.0.0"
    resource_field = "assessmentId"
    validator = staticmethod(_validate_diagnosis)

    def _path(self, patient_id: str, encounter_id: str, severity_assessment_id: str) -> str:
        return f"/api/diagnosis/v2/encounters/{encounter_id}/assessment-snapshot"

    def _source_versions(self, payload: Mapping[str, Any]) -> Mapping[str, str | int]:
        return {"resourceVersion": self._resource_version(payload), "ruleVersion": str(payload["ruleVersion"])}

    def _observed_at(self, payload: Mapping[str, Any]) -> str:
        return str(payload["updatedAt"])


class _SeverityAdapter(_RestAdapter):
    dependency = Dependency.SEVERITY
    interface_version = "2.0.0"
    schema_version = "2.0.0"
    resource_field = "assessmentId"
    validator = staticmethod(_validate_severity)

    def _path(self, patient_id: str, encounter_id: str, severity_assessment_id: str) -> str:
        return f"/api/severity/v2/assessments/{severity_assessment_id}"

    def _source_versions(self, payload: Mapping[str, Any]) -> Mapping[str, str | int]:
        evaluation = payload["evaluation"]
        return {"resourceVersion": self._resource_version(payload), "scaleVersion": str(evaluation["scaleVersion"]),
                "ruleVersion": str(evaluation["ruleVersion"])}

    def _observed_at(self, payload: Mapping[str, Any]) -> str:
        return str(payload["provenance"]["updatedAt"])


class _MedicalHistoryAdapter(_RestAdapter):
    dependency = Dependency.MEDICAL_HISTORY
    interface_version = "2.0.0"
    schema_version = "2.0.0"
    resource_field = "assessmentId"
    validator = staticmethod(_validate_medical_history)

    def _path(self, patient_id: str, encounter_id: str, severity_assessment_id: str) -> str:
        return f"/api/medical-history/v2/encounters/{encounter_id}/assessments/latest"

    def _source_versions(self, payload: Mapping[str, Any]) -> Mapping[str, str | int]:
        versions: dict[str, str | int] = {
            "resourceVersion": self._resource_version(payload),
            "optionSetVersion": str(payload["provenance"]["optionSetVersion"]),
        }
        terminology = sorted({str(item["normalizedIdentity"]["terminologyVersion"])
                              for item in payload["medications"] if item["normalizedIdentity"]["terminologyVersion"]})
        if terminology:
            versions["terminologyVersions"] = ",".join(terminology)
        return versions

    def _observed_at(self, payload: Mapping[str, Any]) -> str:
        return str(payload["updatedAt"])


class _SuicideRiskAdapter(_RestAdapter):
    dependency = Dependency.SUICIDE_RISK
    interface_version = "1.0.0"
    schema_version = "1.0.0"
    resource_field = "assessmentId"
    validator = staticmethod(_validate_suicide_risk)

    def _path(self, patient_id: str, encounter_id: str, severity_assessment_id: str) -> str:
        return f"/api/suicide-risk/v1/encounters/{encounter_id}/snapshot"

    def _resource_id(self, payload: Mapping[str, Any]) -> str:
        return str(payload["source"]["assessmentId"])

    def _resource_version(self, payload: Mapping[str, Any]) -> int:
        return int(payload["source"]["resourceVersion"])

    def _source_versions(self, payload: Mapping[str, Any]) -> Mapping[str, str | int]:
        provenance = payload["assessment"]["provenance"]
        return {"resourceVersion": self._resource_version(payload), "policyVersion": str(provenance["policyVersion"]),
                "governanceVersion": str(provenance["governanceVersion"])}

    def _observed_at(self, payload: Mapping[str, Any]) -> str:
        return str(payload["assessment"]["updatedAt"])

    def _provider_content_hash(self, payload: Mapping[str, Any]) -> str:
        return "sha256:" + str(payload["source"]["contentSha256"])


class ClinicalContextAssembler:
    """Fetch validated owner snapshots while preserving uncertainty and provenance."""

    _types = (_PatientAdapter, _DiagnosisAdapter, _SeverityAdapter, _MedicalHistoryAdapter, _SuicideRiskAdapter)

    def __init__(self, endpoints: Mapping[Dependency, str], client: httpx.AsyncClient, service_auth: ServiceAuthConfig, *,
                 request_deadline_seconds: float = 3.0, dependency_timeout_seconds: float = 1.0,
                 max_attempts: int = 2, stale_after_seconds: float = 900.0,
                 clock: Callable[[], float] = time.monotonic,
                 wall_clock: Callable[[], datetime] = lambda: datetime.now(timezone.utc)):
        missing = set(Dependency) - set(endpoints)
        if missing:
            raise ValueError("missing dependency endpoints: " + ", ".join(sorted(item.value for item in missing)))
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        self._clock = clock
        self._wall_clock = wall_clock
        self._deadline = request_deadline_seconds
        self._stale_after = stale_after_seconds
        retry = RetryPolicy(max_attempts=max_attempts)
        self._adapters = tuple(cls(endpoints[cls.dependency], client, dependency_timeout_seconds, retry, _Circuit(),
                                   service_auth, clock, wall_clock) for cls in self._types)

    async def assemble(self, patient_id: str, encounter_id: str, severity_assessment_id: str,
                       request_context: OutboundRequestContext) -> ClinicalContext:
        if not all(_is_uuid(value) for value in (patient_id, encounter_id, severity_assessment_id)):
            raise ValueError("patient, encounter, and severity assessment IDs must be canonical UUIDs")
        started = self._clock()
        deadline = started + self._deadline
        tasks = [asyncio.create_task(adapter.read(patient_id, encounter_id, severity_assessment_id, request_context, deadline))
                 for adapter in self._adapters]
        done, pending = await asyncio.wait(tasks, timeout=max(0.0, deadline - self._clock()))
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        results = [task.result() for task in done]
        completed = {result.dependency for result in results}
        results.extend(DependencyResult(dependency, errors=(ContextError(
            dependency, ContextErrorCode.TIMEOUT, "strict request deadline exhausted", True),))
            for dependency in Dependency if dependency not in completed)
        inputs: dict[Dependency, Mapping[str, Any]] = {}
        sources: list[SourceCapture] = []
        findings: list[ContextError] = []
        for result in results:
            findings.extend(result.errors)
            if result.value is None:
                continue
            returned_patient = result.value.get("patientId")
            returned_encounter = result.value.get("encounterId")
            if returned_patient != patient_id or returned_encounter != encounter_id:
                findings.append(ContextError(result.dependency, ContextErrorCode.CONFLICT,
                                              "response identifiers conflict with the requested context"))
                continue
            if result.observed_at and self._is_stale(result.observed_at):
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
            return (self._wall_clock().astimezone(timezone.utc) - observed).total_seconds() > self._stale_after
        except (ValueError, TypeError):
            return True
