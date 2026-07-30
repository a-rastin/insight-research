"""Fresh, race-safe safety recomputation and immutable finalization (TP-16)."""
from __future__ import annotations

import hashlib
import inspect
import json
import re
from dataclasses import asdict, dataclass, replace
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping, Protocol
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

from .ddi_check import DdiCheckResult, DdiMedicationChecker, Medication, ReviewedMedicationPlan
from .observability import current_observability
from .edit_ledger import (
    PlanEditLedger,
    PlanFinalized,
    PlanView,
    PreconditionFailed,
    PreconditionRequired,
)
from .safety_policy import (
    Disposition,
    ProbabilisticRecommendation,
    SafetyFacts,
    SafetyOutcome,
    SafetyPolicy,
    SafetyPolicyDecision,
)


class FinalizationError(ValueError):
    pass


class SafetyRecalculationFailed(FinalizationError):
    pass


class IdempotencyConflict(FinalizationError):
    pass


class AuthoritativeContextUnavailable(FinalizationError):
    pass


_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._~-]{16,128}$")
_SEMANTIC_VERSION = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)$")
_CONTENT_HASH = re.compile(r"^sha256:[a-f0-9]{64}$")
_SOURCE_MODULES = frozenset({
    "add-new-patient", "diagnosis", "severity", "medical-history", "ddi-checker", "bn-manager",
})


@dataclass(frozen=True)
class SourceVersion:
    """One exact, current upstream representation used to sign the plan."""

    module: str
    resource_id: str
    schema_version: str
    retrieved_at: str
    content_hash: str
    status: str = "current"
    etag: str | None = None


@dataclass(frozen=True)
class MedicationSafetyCandidate:
    """A deterministic candidate bound to its exact dose-sensitive medication fields."""

    medication: Medication
    recommendation: ProbabilisticRecommendation


@dataclass(frozen=True)
class FinalizationContext:
    """Authoritative server-side medication and deterministic safety inputs."""

    current_medications: tuple[Medication, ...]
    safety_candidates: tuple[MedicationSafetyCandidate, ...]
    safety_facts: SafetyFacts
    sources: tuple[SourceVersion, ...]


class FinalizationContextProvider(Protocol):
    """Server-owned seam; browser input must never implement this interface."""

    async def load(
        self, plan_id: str, patient_id: str, encounter_id: str
    ) -> FinalizationContext: ...


@dataclass(frozen=True)
class FinalizationCommand:
    actor_id: str
    session_id: str
    attestation: str
    request_id: str
    correlation_id: str
    idempotency_key: str


@dataclass(frozen=True)
class SafetyPreview:
    plan_id: str
    source_etag: str
    review_semantic_hash: str
    safety_input_hash: str
    medication_set_hash: str
    ddi: DdiCheckResult
    safety: SafetyPolicyDecision
    stale: bool = False


class PlanFinalizer:
    """Preview or finalize through one interface; finalization always recomputes."""

    def __init__(
        self,
        ledger: PlanEditLedger,
        ddi_checker: DdiMedicationChecker,
        *,
        safety_policy: SafetyPolicy | None = None,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
        context_provider: FinalizationContextProvider | None = None,
    ) -> None:
        self._ledger = ledger
        self._ddi_checker = ddi_checker
        self._safety_policy = safety_policy or SafetyPolicy()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._id_factory = id_factory or (lambda: str(uuid4()))
        self._context_provider = context_provider
        self._previews: dict[str, SafetyPreview] = {}

    async def preview(self, plan_id: str, context: FinalizationContext) -> SafetyPreview:
        preview = await self._recalculate(self._ledger.get(plan_id), context)
        self._previews[plan_id] = preview
        return preview

    def preview_status(self, plan_id: str, context: FinalizationContext) -> SafetyPreview | None:
        prior = self._previews.get(plan_id)
        if prior is None:
            return None
        view = self._ledger.get(plan_id)
        fingerprint = self._safety_input_hash(view.plan, context)
        return replace(prior, stale=(prior.source_etag != view.etag or prior.safety_input_hash != fingerprint))

    async def finalize(
        self,
        plan_id: str,
        *,
        expected_etag: str | None,
        command: FinalizationCommand,
        context: FinalizationContext | None = None,
        reauthorize: Callable[[], Any] | None = None,
    ) -> Mapping[str, Any]:
        observer = current_observability()
        try:
            result = await self._finalize(
                plan_id, expected_etag=expected_etag, command=command,
                context=context, reauthorize=reauthorize,
            )
        except Exception:
            observer.metric("tp_finalization_total", labels={"outcome": "failure"})
            observer.audit("plan.finalize", "failure", actor_id=command.actor_id, entity_id=plan_id)
            raise
        observer.metric("tp_finalization_total", labels={"outcome": "success"})
        observer.audit("plan.finalize", "success", actor_id=command.actor_id, entity_id=plan_id)
        return result

    async def _finalize(
        self,
        plan_id: str,
        *,
        expected_etag: str | None,
        command: FinalizationCommand,
        context: FinalizationContext | None = None,
        reauthorize: Callable[[], Any] | None = None,
    ) -> Mapping[str, Any]:
        if expected_etag is None or not expected_etag.strip():
            raise PreconditionRequired("If-Match is required")
        self._validate_command(command)
        request_hash = self._request_hash(plan_id, expected_etag, command)
        prior = self._ledger.get_finalization(plan_id)
        if prior is not None:
            return self._idempotent_result(prior, command.idempotency_key, request_hash)
        view = self._ledger.get(plan_id)
        if expected_etag != view.etag:
            raise PreconditionFailed("If-Match does not match the current plan")
        if view.plan.get("status") != "ready-for-review":
            raise FinalizationError("only a ready-for-review plan can be finalized")
        if context is None:
            if self._context_provider is None:
                raise AuthoritativeContextUnavailable("authoritative finalization context is not configured")
            context = await self._context_provider.load(
                plan_id, str(view.plan.get("patientId", "")), str(view.plan.get("encounterId", ""))
            )
        self._validate_required_plan(view.plan)
        self._validate_sources(context.sources)

        # A preview is never trusted here. These calls are mandatory on every attempt.
        fresh = await self._recalculate(view, context)
        self._require_safe_result(view, fresh)
        if reauthorize is not None:
            current = reauthorize()
            if inspect.isawaitable(current):
                current = await current
            if current is not None and (
                str(getattr(current, "user_id", "")) != command.actor_id.strip()
                or str(getattr(current, "session_id", "")) != command.session_id.strip()
                or "psychiatrist" not in getattr(current, "roles", ())
            ):
                raise FinalizationError("the signing psychiatrist session changed before commit")
        finalized_at = self._instant(self._clock())
        final_plan = self._build_final_plan(view, command, context, fresh, finalized_at)
        record = {
            "schemaVersion": "1.0.0",
            "finalPlan": final_plan,
            "sourceEtag": view.etag,
            "sourceEditVersion": view.version,
            "sessionId": command.session_id.strip(),
            "safetyBinding": self._binding_dict(fresh),
            "idempotencyKey": command.idempotency_key.strip(),
            "requestHash": request_hash,
            "sourceVersions": [self._source_record(source) for source in context.sources],
        }
        # The store compares the edit sequence and writes the final record atomically.
        try:
            committed = self._ledger.commit_finalization(plan_id, expected_etag=view.etag, record=record)
        except PlanFinalized:
            prior = self._ledger.get_finalization(plan_id)
            if prior is None:
                raise
            return self._idempotent_result(prior, command.idempotency_key, request_hash)
        self._previews[plan_id] = fresh
        return committed["finalPlan"]

    async def _recalculate(self, view: PlanView, context: FinalizationContext) -> SafetyPreview:
        reviewed = ReviewedMedicationPlan.from_reconstructed(view.plan)
        proposed = tuple(self._medication_key(item) for item in reviewed.proposed_medications)
        candidates = tuple(self._medication_key(item.medication) for item in context.safety_candidates)
        recommendation_ids = tuple(item.recommendation.recommendation_id for item in context.safety_candidates)
        proposed_codes = tuple(item.medication_code for item in reviewed.proposed_medications)
        if (
            len(set(proposed)) != len(proposed)
            or sorted(proposed) != sorted(candidates)
            or sorted(proposed_codes) != sorted(recommendation_ids)
        ):
            raise SafetyRecalculationFailed(
                "deterministic safety candidates must match every proposed medication and dose-sensitive field exactly"
            )
        ddi = await self._ddi_checker.check(reviewed, context.current_medications)
        safety = self._safety_policy.apply(
            tuple(item.recommendation for item in context.safety_candidates), context.safety_facts
        )
        return SafetyPreview(
            str(view.plan.get("planId", "")),
            view.etag,
            reviewed.semantic_hash,
            self._safety_input_hash(view.plan, context),
            ddi.medication_set_hash,
            ddi,
            safety,
        )

    @staticmethod
    def _require_safe_result(view: PlanView, preview: SafetyPreview) -> None:
        if preview.ddi.failure is not None:
            raise SafetyRecalculationFailed("final DDI check failed")
        if preview.ddi.unresolved_medications:
            raise SafetyRecalculationFailed("final DDI check has unresolved medication identities")
        if preview.safety.outcome is SafetyOutcome.EMERGENCY_ESCALATION:
            raise SafetyRecalculationFailed("deterministic safety policy requires emergency escalation")
        if any(item.disposition is Disposition.EXCLUDED for item in preview.safety.recommendations):
            raise SafetyRecalculationFailed("deterministic safety policy excludes a proposed medication")
        findings = view.plan.get("safetyFindings", [])
        for interaction in preview.ddi.interactions:
            severity = interaction.severity.casefold()
            if severity not in {"info", "low", "moderate", "high", "critical"}:
                raise SafetyRecalculationFailed("DDI interaction severity cannot be represented safely")
            PlanFinalizer._required_uuid(interaction.alert_id, "DDI alert ID")
            if severity not in {"high", "critical"}:
                continue
            accepted = False
            for item in findings:
                if not isinstance(item, Mapping) or item.get("findingId") != interaction.alert_id:
                    continue
                actor = str(item.get("overrideActorId", "")).strip()
                rationale = str(item.get("overrideRationale", "")).strip()
                if item.get("status") not in {"overridden", "resolved"} or not rationale:
                    continue
                PlanFinalizer._required_uuid(actor, "override actor ID")
                accepted = any(
                    edit.category.value == "severe-ddi-override"
                    and edit.actor_id == actor
                    and edit.after in {"overridden", "resolved"}
                    and bool(edit.reason and edit.reason.strip() == rationale)
                    for edit in view.edits
                )
                if accepted:
                    break
            if not accepted:
                raise SafetyRecalculationFailed(
                    f"high-severity interaction {interaction.alert_id!r} requires an attributable override"
                )

    def _build_final_plan(
        self,
        view: PlanView,
        command: FinalizationCommand,
        context: FinalizationContext,
        preview: SafetyPreview,
        finalized_at: str,
    ) -> dict[str, Any]:
        required = ("planId", "patientId", "encounterId", "content")
        if any(key not in view.plan for key in required):
            raise FinalizationError("review plan lacks identifiers required by the Final Plan contract")
        final_plan = {
            "schemaVersion": "1.0.0",
            "planId": self._required_uuid(self._id_factory(), "Final Plan ID"),
            "primaryPlanId": self._required_uuid(view.plan["planId"], "Primary Plan ID"),
            "patientId": self._required_uuid(view.plan["patientId"], "patient ID"),
            "encounterId": self._required_uuid(view.plan["encounterId"], "encounter ID"),
            "version": 1,
            "status": "finalized",
            "finalizedAt": finalized_at,
            "finalizedBy": command.actor_id.strip(),
            "attestation": command.attestation.strip(),
            "content": _json_copy(view.plan["content"]),
            "safetyFindings": self._fresh_findings(view.plan, preview, finalized_at),
            "provenance": {
                "schemaVersion": "1.0.0",
                "recordId": self._required_uuid(self._id_factory(), "provenance record ID"),
                "recordedAt": finalized_at,
                "actorId": command.actor_id.strip(),
                "action": "plan.finalized",
                "requestId": command.request_id.strip(),
                "correlationId": command.correlation_id.strip(),
                "sources": [self._source_provenance(source) for source in context.sources],
                "policyVersion": preview.safety.policy_version,
                "knowledgeVersion": preview.ddi.knowledge_base_version,
            },
        }
        final_plan["contentHash"] = _hash_json(final_plan)
        return final_plan

    @staticmethod
    def _fresh_findings(
        plan: Mapping[str, Any], preview: SafetyPreview, detected_at: str
    ) -> list[dict[str, Any]]:
        old = plan.get("safetyFindings", [])
        preserved = [_json_copy(item) for item in old if isinstance(item, Mapping) and item.get("category") == "data-quality"]
        by_id = {item.get("findingId"): item for item in old if isinstance(item, Mapping)}
        for alert in preview.ddi.interactions:
            prior = by_id.get(alert.alert_id, {})
            finding = {
                "schemaVersion": "1.0.0",
                "findingId": alert.alert_id,
                "category": "interaction",
                "severity": alert.severity.casefold(),
                "status": prior.get("status", "open"),
                "summary": alert.recommended_action,
                "detectedAt": detected_at,
                "knowledgeVersion": preview.ddi.knowledge_base_version,
            }
            for key in ("overrideRationale", "overrideActorId"):
                if key in prior:
                    finding[key] = prior[key]
            preserved.append(finding)
        for trace in preview.safety.traces:
            if "allergy" not in trace.rule_id and "contraindication" not in trace.rule_id:
                continue
            category = "allergy" if "allergy" in trace.rule_id else "contraindication"
            preserved.append({
                "schemaVersion": "1.0.0",
                "findingId": str(uuid5(NAMESPACE_URL, f"{preview.review_semantic_hash}:{trace.rule_id}:{trace.recommendation_id}")),
                "category": category,
                "severity": trace.severity,
                "status": "open",
                "summary": trace.summary,
                "detectedAt": detected_at,
            })
        return preserved

    @staticmethod
    def _medication_key(medication: Medication) -> tuple[str | None, ...]:
        return (
            medication.medication_code,
            medication.code_system,
            medication.dose,
            medication.route,
            medication.frequency,
        )

    @staticmethod
    def _safety_input_hash(plan: Mapping[str, Any], context: FinalizationContext) -> str:
        value = {
            "pharmacotherapy": plan.get("content", {}).get("pharmacotherapy"),
            "currentMedications": context.current_medications,
            "safetyCandidates": context.safety_candidates,
            "safetyFacts": context.safety_facts,
            "sources": context.sources,
        }
        return _hash_json(_jsonable(value))

    @staticmethod
    def _binding_dict(preview: SafetyPreview) -> dict[str, Any]:
        return {
            "reviewSemanticHash": preview.review_semantic_hash,
            "safetyInputHash": preview.safety_input_hash,
            "medicationSetHash": preview.medication_set_hash,
            "ddiCheckId": preview.ddi.check_id,
            "ddiKnowledgeBaseId": preview.ddi.knowledge_base_id,
            "ddiKnowledgeBaseVersion": preview.ddi.knowledge_base_version,
            "safetyPolicyId": preview.safety.policy_id,
            "safetyPolicyVersion": preview.safety.policy_version,
            "safetyOutcome": preview.safety.outcome.value,
        }

    @staticmethod
    def _validate_command(command: FinalizationCommand) -> None:
        for name in (
            "actor_id", "session_id", "attestation", "request_id", "correlation_id", "idempotency_key",
        ):
            if not str(getattr(command, name)).strip():
                raise FinalizationError(f"{name} is required")
        for name in ("actor_id", "request_id", "correlation_id"):
            PlanFinalizer._required_uuid(getattr(command, name), name)
        if not _IDEMPOTENCY_KEY.fullmatch(command.idempotency_key.strip()):
            raise FinalizationError("idempotency_key must contain 16-128 transport-safe characters")

    @staticmethod
    def _validate_required_plan(plan: Mapping[str, Any]) -> None:
        for name in ("planId", "patientId", "encounterId"):
            PlanFinalizer._required_uuid(plan.get(name), name)
        if plan.get("schemaVersion") != "1.0.0":
            raise FinalizationError("review plan schemaVersion must be 1.0.0")
        content = plan.get("content")
        if not isinstance(content, Mapping):
            raise FinalizationError("review plan content is required")
        if not isinstance(content.get("setting"), str) or not content["setting"].strip():
            raise FinalizationError("review plan setting is required")
        medications = content.get("pharmacotherapy")
        if not isinstance(medications, list):
            raise FinalizationError("review plan pharmacotherapy must be an array")
        for index, medication in enumerate(medications):
            if not isinstance(medication, Mapping):
                raise FinalizationError(f"pharmacotherapy item {index} must be an object")
            for field in ("medicationCode", "codeSystem", "dose", "route", "frequency"):
                if not isinstance(medication.get(field), str) or not medication[field].strip():
                    raise FinalizationError(f"pharmacotherapy item {index} requires {field}")
        appointment = content.get("nextAppointment")
        if not isinstance(appointment, Mapping):
            raise FinalizationError("review plan nextAppointment is required")
        for field in ("interval", "timezone"):
            if not isinstance(appointment.get(field), str) or not appointment[field].strip():
                raise FinalizationError(f"review plan nextAppointment requires {field}")
        if not isinstance(plan.get("safetyFindings"), list):
            raise FinalizationError("review plan safetyFindings must be an array")

    @staticmethod
    def _validate_sources(sources: tuple[SourceVersion, ...]) -> None:
        if not sources:
            raise FinalizationError("at least one authoritative source version is required")
        identities: set[tuple[str, str]] = set()
        for source in sources:
            if source.module not in _SOURCE_MODULES:
                raise FinalizationError(f"source module {source.module!r} is not supported")
            if not source.resource_id.strip():
                raise FinalizationError("source resource_id is required")
            identity = (source.module, source.resource_id.strip())
            if identity in identities:
                raise FinalizationError("source versions must be unique by module and resource")
            identities.add(identity)
            if not _SEMANTIC_VERSION.fullmatch(source.schema_version.strip()):
                raise FinalizationError("source schema_version must be semantic versioning")
            if source.status != "current":
                raise FinalizationError(f"source {source.module}/{source.resource_id} is not current")
            if not _CONTENT_HASH.fullmatch(source.content_hash.strip()):
                raise FinalizationError("source content_hash must be a sha256 hash")
            PlanFinalizer._parse_instant(source.retrieved_at, "source retrieved_at")
            if source.etag is not None and not source.etag.strip():
                raise FinalizationError("source etag cannot be blank")

    @staticmethod
    def _source_provenance(source: SourceVersion) -> dict[str, Any]:
        value = {
            "module": source.module,
            "resourceId": source.resource_id.strip(),
            "schemaVersion": source.schema_version.strip(),
            "retrievedAt": PlanFinalizer._parse_instant(source.retrieved_at, "source retrieved_at"),
            "contentHash": source.content_hash.strip(),
        }
        if source.etag is not None:
            value["etag"] = source.etag.strip()
        return value

    @staticmethod
    def _source_record(source: SourceVersion) -> dict[str, Any]:
        value = PlanFinalizer._source_provenance(source)
        value["status"] = source.status
        return value

    @staticmethod
    def _request_hash(plan_id: str, expected_etag: str, command: FinalizationCommand) -> str:
        return _hash_json({
            "planId": plan_id,
            "expectedEtag": expected_etag,
            "actorId": command.actor_id.strip(),
            "sessionId": command.session_id.strip(),
            "attestation": command.attestation.strip(),
        })

    @staticmethod
    def _idempotent_result(
        record: Mapping[str, Any], idempotency_key: str, request_hash: str
    ) -> Mapping[str, Any]:
        if record.get("idempotencyKey") != idempotency_key.strip() or record.get("requestHash") != request_hash:
            raise IdempotencyConflict("the finalized plan does not match this idempotent request")
        final_plan = record.get("finalPlan")
        if not isinstance(final_plan, Mapping):
            raise FinalizationError("stored finalization record is invalid")
        return _json_copy(final_plan)

    @staticmethod
    def _parse_instant(value: str, field: str) -> str:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                raise ValueError
        except (AttributeError, ValueError) as exc:
            raise FinalizationError(f"{field} must be an offset-aware instant") from exc
        return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _required_uuid(value: Any, field: str) -> str:
        try:
            return str(UUID(str(value)))
        except (TypeError, ValueError, AttributeError) as exc:
            raise FinalizationError(f"{field} must be a UUID") from exc

    @staticmethod
    def _instant(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _jsonable(value: Any) -> Any:
    if isinstance(value, Enum):
        return value.value
    if hasattr(value, "__dataclass_fields__"):
        return _jsonable(asdict(value))
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    return value


def _json_copy(value: Any) -> Any:
    return json.loads(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False))


def _hash_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return "sha256:" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()

