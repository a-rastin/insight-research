"""Medication-set DDI checking through the DDI Checker REST seam (TP-13)."""
from __future__ import annotations

import hashlib
import hmac
import json
import base64
import re
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Protocol, Sequence
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import httpx

from .clinical_context import OutboundRequestContext

from .primary_plan import PrimaryTreatmentPlan
from .observability import current_observability


SCHEMA_VERSION = "1.0.0"
_SHA256 = re.compile(r"^sha256:[a-f0-9]{64}$")
_SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")


@dataclass(frozen=True)
class Medication:
    """An exact medication input as known before DDI normalization."""

    original_text: str
    medication_code: str | None = None
    code_system: str | None = None
    dose: str | None = None
    route: str | None = None
    frequency: str | None = None


@dataclass(frozen=True)
class ReviewedMedicationPlan:
    """The exact reconstructed pharmacotherapy submitted for a final DDI check."""

    semantic_hash: str
    proposed_medications: tuple[Medication, ...]

    @classmethod
    def from_reconstructed(cls, plan: Mapping[str, Any]) -> "ReviewedMedicationPlan":
        try:
            pharmacotherapy = plan["content"]["pharmacotherapy"]
        except (KeyError, TypeError) as exc:
            raise ValueError("review plan requires content.pharmacotherapy") from exc
        if not isinstance(pharmacotherapy, list) or not pharmacotherapy:
            raise ValueError("review plan pharmacotherapy must be a non-empty array")
        medications: list[Medication] = []
        required = ("medicationCode", "codeSystem", "dose", "route", "frequency")
        for raw in pharmacotherapy:
            if not isinstance(raw, Mapping) or any(
                not isinstance(raw.get(field), str) or not raw[field].strip()
                for field in required
            ):
                raise ValueError("review plan pharmacotherapy contains an incomplete medication")
            medications.append(Medication(
                original_text=raw["medicationCode"],
                medication_code=raw["medicationCode"],
                code_system=raw["codeSystem"],
                dose=raw["dose"],
                route=raw["route"],
                frequency=raw["frequency"],
            ))
        encoded = json.dumps(plan, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
        return cls(DdiMedicationChecker._hash_text(encoded), tuple(medications))


@dataclass(frozen=True)
class DdiMedicationIdentity:
    input_index: int
    source: str
    original_text: str
    concept_id: str | None
    code_system: str | None
    display: str | None
    reason: str | None
    candidates: tuple[Mapping[str, Any], ...]
    details: Mapping[str, Any]


@dataclass(frozen=True)
class DdiInteraction:
    alert_id: str
    medication_input_indexes: tuple[int, ...]
    severity: str
    mechanism: str | None
    evidence: tuple[Mapping[str, Any], ...]
    recommended_action: str
    details: Mapping[str, Any]


@dataclass(frozen=True)
class DdiFailure:
    code: str
    detail: str


@dataclass(frozen=True)
class DdiCheckResult:
    plan_semantic_hash: str
    medication_set_hash: str
    check_id: str | None = None
    knowledge_base_id: str | None = None
    knowledge_base_version: str | None = None
    normalized_medications: tuple[DdiMedicationIdentity, ...] = ()
    unresolved_medications: tuple[DdiMedicationIdentity, ...] = ()
    pairs_checked: tuple[Mapping[str, Any], ...] = ()
    interactions: tuple[DdiInteraction, ...] = ()
    failure: DdiFailure | None = None

    @property
    def checker_succeeded(self) -> bool:
        return self.failure is None

    @property
    def allows_no_interactions_claim(self) -> bool:
        return (
            self.checker_succeeded
            and not self.unresolved_medications
            and not self.interactions
        )

    @property
    def interaction_statement(self) -> str:
        if self.failure:
            return "Interaction status unknown: the DDI checker failed."
        if self.unresolved_medications:
            prefix = f"{len(self.interactions)} interaction(s) identified; " if self.interactions else ""
            return prefix + "interaction coverage is incomplete because medication identities are unresolved."
        if self.interactions:
            return f"{len(self.interactions)} interaction(s) identified."
        return "No interactions identified by the DDI checker."


class _DdiPort(Protocol):
    async def check(
        self, request: Mapping[str, Any], request_context: OutboundRequestContext | None = None
    ) -> Mapping[str, Any]: ...


class HttpDdiPort:
    """Authenticated REST adapter for DDI v1 clinical checks."""

    def __init__(
        self,
        base_url: str,
        service_id: str,
        key_id: str,
        secret: bytes,
        *,
        session_cookie_name: str = "insight_session",
        timeout_seconds: float = 3.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        parsed = urlsplit(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.path not in {"", "/"} or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ValueError("DDI base URL must be an HTTP origin")
        if not service_id or not key_id or not secret or len(secret) < 32:
            raise ValueError("DDI service authentication configuration is incomplete")
        if not session_cookie_name or any(character not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.-" for character in session_cookie_name):
            raise ValueError("DDI session cookie name is invalid")
        if not 0 < timeout_seconds <= 30:
            raise ValueError("DDI timeout must be greater than zero and at most 30 seconds")
        self._base_url = base_url.rstrip("/")
        self._service_id = service_id
        self._key_id = key_id
        self._secret = secret
        self._session_cookie_name = session_cookie_name
        self._timeout = timeout_seconds
        self._client = client

    async def check(
        self, request: Mapping[str, Any], request_context: OutboundRequestContext | None = None
    ) -> Mapping[str, Any]:
        if request_context is None:
            raise ValueError("DDI check requires authenticated outbound request context")
        path = "/api/ddi/v1/checks"
        body = json.dumps(request, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")
        request_id = str(uuid4())
        timestamp = str(int(datetime.now(timezone.utc).timestamp()))
        nonce = secrets.token_hex(16)
        content_hash = hashlib.sha256(body).hexdigest()
        canonical = "\n".join((
            "INSIGHT-HMAC-V1", self._service_id, self._key_id, timestamp, nonce,
            "ddi-checker", "POST", path, content_hash, request_id,
            request_context.correlation_id, request_context.parent_request_id,
        )).encode("utf-8")
        signature = base64.urlsafe_b64encode(
            hmac.new(self._secret, canonical, hashlib.sha256).digest()
        ).rstrip(b"=").decode("ascii")
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Cookie": f"{self._session_cookie_name}={request_context.session_cookie_value}",
            "Idempotency-Key": str(request["idempotencyKey"]),
            "X-Schema-Version": SCHEMA_VERSION,
            "X-Request-ID": request_id,
            "X-Correlation-ID": request_context.correlation_id,
            "X-Causation-ID": request_context.parent_request_id,
            "X-Insight-Service-ID": self._service_id,
            "X-Insight-Key-ID": self._key_id,
            "X-Insight-Timestamp": timestamp,
            "X-Insight-Nonce": nonce,
            "X-Insight-Content-SHA256": content_hash,
            "X-Insight-Signature": f"v1={signature}",
        }
        response = await self._request("POST", path, headers=headers, content=body)
        response.raise_for_status()
        if response.headers.get("X-Schema-Version") != SCHEMA_VERSION:
            raise ValueError("DDI response schema header is unsupported")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("DDI response must be an object")
        return payload

    async def ready(self) -> bool:
        try:
            response = await self._request("GET", "/readyz", headers={"Accept": "application/json"})
            payload = response.json()
            return (
                response.status_code == 200
                and response.headers.get("X-Schema-Version") == SCHEMA_VERSION
                and isinstance(payload, dict)
                and payload.get("status") == "ready"
                and payload.get("module") == "ddi-checker"
                and payload.get("schemaVersion") == SCHEMA_VERSION
                and isinstance(payload.get("knowledgeBaseVersion"), str)
                and bool(_SEMVER.fullmatch(payload["knowledgeBaseVersion"]))
                and isinstance(payload.get("knowledgeBaseContentHash"), str)
                and bool(_SHA256.fullmatch(payload["knowledgeBaseContentHash"]))
            )
        except (httpx.HTTPError, ValueError):
            return False

    async def _request(self, method: str, path: str, **kwargs: Any) -> httpx.Response:
        if self._client is not None:
            return await self._client.request(method, self._base_url + path, timeout=self._timeout, **kwargs)
        async with httpx.AsyncClient() as client:
            return await client.request(method, self._base_url + path, timeout=self._timeout, **kwargs)


class _InvalidDdiResponse(ValueError):
    pass


class DdiMedicationChecker:
    """Check the exact current + proposed medication set through one interface."""

    def __init__(self, port: _DdiPort):
        self._port = port

    async def check(
        self,
        plan: PrimaryTreatmentPlan | ReviewedMedicationPlan,
        current_medications: Sequence[Medication],
        request_context: OutboundRequestContext | None = None,
    ) -> DdiCheckResult:
        if not isinstance(plan, (PrimaryTreatmentPlan, ReviewedMedicationPlan)):
            raise TypeError("plan must be a PrimaryTreatmentPlan or ReviewedMedicationPlan")
        current = tuple(current_medications)
        for medication in current:
            self._validate_medication(medication)

        proposed = self._proposed_medications(plan)
        if not proposed:
            raise ValueError("plan must contain at least one proposed medication")
        medications = (*current, *proposed)
        request_medications = tuple(
            self._request_medication(item, "current" if index < len(current) else "proposed", index)
            for index, item in enumerate(medications)
        )
        medication_set_hash = self._medication_set_hash(request_medications)
        idempotency_key = self._hash_text(f"{plan.semantic_hash}|{medication_set_hash}")
        request = {
            "schemaVersion": SCHEMA_VERSION,
            "idempotencyKey": idempotency_key,
            "planSemanticHash": plan.semantic_hash,
            "medicationSetHash": medication_set_hash,
            "medications": list(request_medications),
        }

        started = time.monotonic()
        observer = current_observability()
        try:
            if request_context is None:
                raw = await self._port.check(request)
            else:
                raw = await self._port.check(request, request_context)
            result = self._parse_response(raw, plan.semantic_hash, medication_set_hash, medications, request_medications)
        except Exception as exc:
            observer.metric("tp_dependency_latency_ms", (time.monotonic() - started) * 1000,
                            labels={"dependency": "ddi-checker", "outcome": "failure"})
            observer.metric("tp_dependency_failure_total", labels={"dependency": "ddi-checker", "outcome": "failure"})
            observer.metric("tp_generation_total", labels={"kind": "ddi-check", "outcome": "failure"})
            code = "invalid-response" if isinstance(exc, _InvalidDdiResponse) else "checker-failed"
            return DdiCheckResult(
                plan.semantic_hash,
                medication_set_hash,
                failure=DdiFailure(code, f"DDI check unavailable: {type(exc).__name__}"),
            )
        observer.metric("tp_dependency_latency_ms", (time.monotonic() - started) * 1000,
                        labels={"dependency": "ddi-checker", "outcome": "success"})
        observer.metric("tp_generation_total", labels={"kind": "ddi-check", "outcome": "success"})
        observer.metric("tp_version_info", labels={"kind": "knowledge-base", "version": result.knowledge_base_version or "unknown"})
        return result

    @staticmethod
    def _validate_medication(medication: Medication) -> None:
        if not isinstance(medication, Medication):
            raise TypeError("current medications must be Medication values")
        if not isinstance(medication.original_text, str) or not medication.original_text.strip():
            raise ValueError("medication original_text must be non-empty")

    @classmethod
    def _proposed_medications(
        cls, plan: PrimaryTreatmentPlan | ReviewedMedicationPlan
    ) -> tuple[Medication, ...]:
        if isinstance(plan, ReviewedMedicationPlan):
            for medication in plan.proposed_medications:
                cls._validate_medication(medication)
            return plan.proposed_medications
        value = plan.pharmacotherapy.value
        required = ("medicationCode", "codeSystem", "dose", "route", "frequency")
        if any(not isinstance(value.get(field), str) or not value[field].strip() for field in required):
            raise ValueError("plan pharmacotherapy must contain a complete structured medication")
        medication = Medication(
            original_text=value["medicationCode"],
            medication_code=value["medicationCode"],
            code_system=value["codeSystem"],
            dose=value["dose"],
            route=value["route"],
            frequency=value["frequency"],
        )
        cls._validate_medication(medication)
        return (medication,)

    @staticmethod
    def _request_medication(medication: Medication, source: str, input_index: int) -> dict[str, Any]:
        values = {
            "inputIndex": input_index,
            "source": source,
            "originalText": medication.original_text,
            "medicationCode": medication.medication_code,
            "codeSystem": medication.code_system,
            "dose": medication.dose,
            "route": medication.route,
            "frequency": medication.frequency,
        }
        return {key: value for key, value in values.items() if value is not None}

    @classmethod
    def _medication_set_hash(cls, medications: Sequence[Mapping[str, Any]]) -> str:
        canonical_items = [
            {key: value for key, value in item.items() if key != "inputIndex"}
            for item in medications
        ]
        canonical_items.sort(key=lambda item: json.dumps(item, sort_keys=True, separators=(",", ":")))
        encoded = json.dumps(
            {"schemaVersion": SCHEMA_VERSION, "medications": canonical_items},
            sort_keys=True,
            separators=(",", ":"),
        )
        return cls._hash_text(encoded)

    @staticmethod
    def _hash_text(value: str) -> str:
        return "sha256:" + hashlib.sha256(value.encode("utf-8")).hexdigest()

    def _parse_response(
        self,
        raw: Mapping[str, Any],
        plan_hash: str,
        medication_set_hash: str,
        medications: Sequence[Medication],
        request_medications: Sequence[Mapping[str, Any]],
    ) -> DdiCheckResult:
        if not isinstance(raw, Mapping) or raw.get("schemaVersion") != SCHEMA_VERSION:
            raise _InvalidDdiResponse("unsupported DDI response schema")
        if raw.get("medicationSetHash") != medication_set_hash:
            raise _InvalidDdiResponse("DDI response does not match the submitted medication set")
        check_id = self._required_text(raw, "checkId")
        knowledge_base = raw.get("knowledgeBase")
        if knowledge_base is not None and not isinstance(knowledge_base, Mapping):
            raise _InvalidDdiResponse("knowledgeBase must be an object")
        knowledge_base = knowledge_base or {}
        kb_id = raw.get("knowledgeBaseId", knowledge_base.get("id"))
        kb_version = raw.get(
            "knowledgeBaseVersion",
            raw.get("knowledgeVersion", knowledge_base.get("version")),
        )
        try:
            parsed_kb_id = UUID(str(kb_id))
        except ValueError as exc:
            raise _InvalidDdiResponse("knowledgeBaseId must be a UUID") from exc
        if parsed_kb_id.int == 0 or str(parsed_kb_id) != kb_id:
            raise _InvalidDdiResponse("knowledgeBaseId must be a canonical non-nil UUID")
        if not isinstance(kb_version, str) or not _SEMVER.fullmatch(kb_version):
            raise _InvalidDdiResponse("knowledgeBaseVersion must be semantic version metadata")
        required_fields = {
            "schemaVersion", "checkId", "medicationSetHash", "knowledgeBaseId",
            "knowledgeBaseVersion", "knowledgeBaseContentHash", "coverageStatus",
            "resolvedMedications", "unresolvedMedications", "pairsChecked", "alerts", "checkedAt",
        }
        if set(raw) != required_fields:
            raise _InvalidDdiResponse("DDI response fields do not match schema 1.0.0")
        normalized_raw = self._required_list(raw, "resolvedMedications")
        unresolved_raw = self._required_list(raw, "unresolvedMedications")
        pairs = self._required_list(raw, "pairsChecked")
        alerts = self._required_list(raw, "alerts")
        if raw.get("coverageStatus") != ("incomplete" if unresolved_raw else "complete"):
            raise _InvalidDdiResponse("DDI coverageStatus conflicts with medication resolution")
        if not isinstance(raw.get("knowledgeBaseContentHash"), str) or not _SHA256.fullmatch(raw["knowledgeBaseContentHash"]):
            raise _InvalidDdiResponse("DDI knowledgeBaseContentHash is invalid")
        try:
            parsed_check_id = UUID(str(check_id))
            checked_at = datetime.fromisoformat(str(raw["checkedAt"]).replace("Z", "+00:00"))
        except ValueError as exc:
            raise _InvalidDdiResponse("DDI check identity or timestamp is invalid") from exc
        if parsed_check_id.int == 0 or str(parsed_check_id) != check_id:
            raise _InvalidDdiResponse("DDI checkId must be a canonical non-nil UUID")
        if checked_at.tzinfo is None or checked_at.utcoffset() != timezone.utc.utcoffset(checked_at):
            raise _InvalidDdiResponse("DDI checkedAt must be UTC")

        normalized = tuple(
            self._identity(item, medications, request_medications, unresolved=False)
            for item in normalized_raw
        )
        unresolved = tuple(
            self._identity(item, medications, request_medications, unresolved=True)
            for item in unresolved_raw
        )
        covered = [item.input_index for item in (*normalized, *unresolved)]
        if len(covered) != len(set(covered)) or set(covered) != set(range(len(medications))):
            raise _InvalidDdiResponse("normalized and unresolved identities must cover every input exactly once")
        pairs_checked = tuple(self._mapping_copy(item, "pairsChecked item") for item in pairs)
        if not unresolved:
            self._validate_pair_coverage(pairs_checked, len(medications))
        interactions = tuple(self._interaction(item, len(medications)) for item in alerts)
        return DdiCheckResult(
            plan_hash,
            medication_set_hash,
            check_id,
            kb_id,
            kb_version,
            normalized,
            unresolved,
            pairs_checked,
            interactions,
        )

    def _identity(
        self,
        raw: Any,
        medications: Sequence[Medication],
        request_medications: Sequence[Mapping[str, Any]],
        *,
        unresolved: bool,
    ) -> DdiMedicationIdentity:
        details = self._mapping_copy(raw, "medication identity")
        index = details.get("inputIndex")
        if not isinstance(index, int) or isinstance(index, bool) or not 0 <= index < len(medications):
            raise _InvalidDdiResponse("medication identity inputIndex is invalid")
        concept_id = details.get("conceptId")
        status = details.get("status")
        expected_fields = (
            {"inputIndex", "status", "originalText", "reason", "candidates"}
            if unresolved else
            {"inputIndex", "status", "originalText", "conceptId", "codeSystem", "display"}
        )
        if set(details) != expected_fields:
            raise _InvalidDdiResponse("medication identity fields do not match schema 1.0.0")
        if details.get("originalText") != medications[index].original_text:
            raise _InvalidDdiResponse("medication identity originalText conflicts with the request")
        if unresolved and status not in {"ambiguous", "unknown"}:
            raise _InvalidDdiResponse("unresolved medication status is invalid")
        if not unresolved and status != "resolved":
            raise _InvalidDdiResponse("resolved medication status is invalid")
        if not unresolved and (not isinstance(concept_id, str) or not concept_id.strip()):
            raise _InvalidDdiResponse("normalized medication conceptId is required")
        if not unresolved and any(not isinstance(details.get(field), str) or not details[field].strip() for field in ("codeSystem", "display")):
            raise _InvalidDdiResponse("resolved medication codeSystem and display are required")
        if unresolved and (not isinstance(details.get("reason"), str) or not details["reason"].strip()):
            raise _InvalidDdiResponse("unresolved medication reason is required")
        candidates_raw = details.get("candidates", [])
        if not isinstance(candidates_raw, list):
            raise _InvalidDdiResponse("unresolved medication candidates must be an array")
        candidates = tuple(self._mapping_copy(item, "candidate") for item in candidates_raw)
        if any(set(item) != {"conceptId", "codeSystem", "display"} for item in candidates):
            raise _InvalidDdiResponse("unresolved medication candidate is invalid")
        if any(any(not isinstance(item.get(field), str) or not item[field].strip() for field in ("conceptId", "codeSystem", "display")) for item in candidates):
            raise _InvalidDdiResponse("unresolved medication candidate fields are required")
        if unresolved and ((status == "ambiguous" and len(candidates) < 2) or (status == "unknown" and candidates)):
            raise _InvalidDdiResponse("unresolved medication candidates conflict with status")
        requested = request_medications[index]
        return DdiMedicationIdentity(
            index,
            str(requested["source"]),
            medications[index].original_text,
            concept_id if isinstance(concept_id, str) else None,
            details.get("codeSystem") if isinstance(details.get("codeSystem"), str) else None,
            details.get("display") if isinstance(details.get("display"), str) else None,
            details.get("reason") if isinstance(details.get("reason"), str) else None,
            candidates,
            details,
        )

    @classmethod
    def _validate_pair_coverage(
        cls,
        pairs: Sequence[Mapping[str, Any]],
        medication_count: int,
    ) -> None:
        actual: set[tuple[int, int]] = set()
        for pair in pairs:
            if set(pair) != {"medicationInputIndexes"}:
                raise _InvalidDdiResponse("pairsChecked fields do not match schema 1.0.0")
            indexes = pair["medicationInputIndexes"]
            if not isinstance(indexes, list) or len(indexes) != 2:
                raise _InvalidDdiResponse("pairsChecked medicationInputIndexes must contain two inputs")
            left, right = indexes
            if (
                not isinstance(left, int)
                or isinstance(left, bool)
                or not isinstance(right, int)
                or isinstance(right, bool)
                or left == right
                or not 0 <= left < medication_count
                or not 0 <= right < medication_count
            ):
                raise _InvalidDdiResponse("pairsChecked input indexes are invalid")
            actual.add(tuple(sorted((left, right))))
        if len(actual) != len(pairs):
            raise _InvalidDdiResponse("pairsChecked contains duplicate medication pairs")
        expected = {
            (left, right)
            for left in range(medication_count)
            for right in range(left + 1, medication_count)
        }
        if actual != expected:
            raise _InvalidDdiResponse("pairsChecked does not cover every normalized medication pair")

    def _interaction(self, raw: Any, medication_count: int) -> DdiInteraction:
        details = self._mapping_copy(raw, "alert")
        indexes = details.get("medicationInputIndexes")
        if (
            not isinstance(indexes, list)
            or len(indexes) < 2
            or any(not isinstance(item, int) or isinstance(item, bool) or not 0 <= item < medication_count for item in indexes)
        ):
            raise _InvalidDdiResponse("alert medicationInputIndexes are invalid")
        severity = self._required_text(details, "severity")
        recommended_action = details.get("recommendedAction", details.get("recommendation"))
        if not isinstance(recommended_action, str) or not recommended_action.strip():
            raise _InvalidDdiResponse("alert recommendedAction is required")
        evidence_raw = details.get("evidence")
        if not isinstance(evidence_raw, list) or not evidence_raw:
            raise _InvalidDdiResponse("alert evidence must be a non-empty array")
        return DdiInteraction(
            self._required_text(details, "alertId"),
            tuple(indexes),
            severity,
            details.get("mechanism") if isinstance(details.get("mechanism"), str) else None,
            tuple(self._mapping_copy(item, "evidence") for item in evidence_raw),
            recommended_action,
            details,
        )

    @staticmethod
    def _required_text(raw: Mapping[str, Any], key: str) -> str:
        value = raw.get(key)
        if not isinstance(value, str) or not value.strip():
            raise _InvalidDdiResponse(f"{key} must be a non-empty string")
        return value

    @staticmethod
    def _required_list(raw: Mapping[str, Any], key: str) -> list[Any]:
        value = raw.get(key)
        if not isinstance(value, list):
            raise _InvalidDdiResponse(f"{key} must be an array")
        return value

    @staticmethod
    def _mapping_copy(raw: Any, field: str) -> dict[str, Any]:
        if not isinstance(raw, Mapping):
            raise _InvalidDdiResponse(f"{field} must be an object")
        return json.loads(json.dumps(dict(raw), sort_keys=True))

