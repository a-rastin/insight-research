"""Medication-set DDI checking through the DDI Checker REST seam (TP-13)."""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Mapping, Protocol, Sequence

from .primary_plan import PrimaryTreatmentPlan
from .observability import current_observability


SCHEMA_VERSION = "1.0.0"


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
    async def check(self, request: Mapping[str, Any]) -> Mapping[str, Any]: ...


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
            raw = await self._port.check(request)
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
        if not isinstance(kb_id, str) or not kb_id.strip():
            raise _InvalidDdiResponse("knowledgeBaseId must be a non-empty string")
        if not isinstance(kb_version, str) or not kb_version.strip():
            raise _InvalidDdiResponse("knowledgeBaseVersion must be a non-empty string")
        normalized_raw = self._required_list(raw, "normalizedMedications")
        unresolved_raw = self._required_list(raw, "unresolvedMedications")
        pairs = self._required_list(raw, "pairsChecked")
        alerts = self._required_list(raw, "alerts")

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
        if not unresolved and (not isinstance(concept_id, str) or not concept_id.strip()):
            raise _InvalidDdiResponse("normalized medication conceptId is required")
        candidates_raw = details.get("candidates", [])
        if not isinstance(candidates_raw, list):
            raise _InvalidDdiResponse("unresolved medication candidates must be an array")
        candidates = tuple(self._mapping_copy(item, "candidate") for item in candidates_raw)
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
            if "medicationInputIndexes" in pair:
                indexes = pair["medicationInputIndexes"]
                if not isinstance(indexes, list) or len(indexes) != 2:
                    raise _InvalidDdiResponse("pairsChecked medicationInputIndexes must contain two inputs")
                left, right = indexes
            else:
                left = pair.get("leftInputIndex")
                right = pair.get("rightInputIndex")
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

