"""Idempotent recommendation-run lifecycle orchestration for INS-050."""

from __future__ import annotations

import hashlib
import json
import re
import threading
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Callable, Mapping, Protocol
from uuid import UUID, uuid4

from .bn_evaluation import BnEvaluationBundle, BnEvaluationOrchestrator, BnModel, NormalizedSnapshotFacts
from .clinical_context import ClinicalContext, OutboundRequestContext
from .ddi_check import DdiCheckResult, DdiMedicationChecker, Medication
from .edit_ledger import PlanEditLedger
from .eligibility import EligibilityDecision
from .primary_plan import PrimaryPlanSynthesizer, PrimaryTreatmentPlan, SourceFact
from .repository import Repository, RuntimeRecord
from .safety_policy import ProbabilisticRecommendation, SafetyFacts, SafetyPolicy


POLICY_VERSION = "schizophrenia-research-v1"
SCHEMA_VERSION = "1.1.0"
_IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._~-]{16,128}$")
_TERMINAL = frozenset({"inputs-incomplete", "generated", "generation-failed"})
_TRANSITIONS = {
    "requested": frozenset({"gathering-inputs"}),
    "gathering-inputs": frozenset({"inputs-incomplete", "evaluating", "generation-failed"}),
    "evaluating": frozenset({"generated", "generation-failed"}),
}


class RecommendationRunError(ValueError):
    pass


class RecommendationRunNotFound(RecommendationRunError):
    pass


class RecommendationRunIdempotencyConflict(RecommendationRunError):
    pass


class RecommendationRunUnavailable(RecommendationRunError):
    pass


@dataclass(frozen=True)
class RecommendationRunRequest:
    patient_id: str
    encounter_id: str
    severity_assessment_id: str
    timezone: str

    def canonical(self) -> dict[str, str]:
        return {
            "patientId": self.patient_id,
            "encounterId": self.encounter_id,
            "severityAssessmentId": self.severity_assessment_id,
            "timezone": self.timezone,
        }


@dataclass(frozen=True)
class RecommendationRunFinding:
    code: str
    source: str
    detail: str
    retryable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "source": self.source,
            "detail": self.detail,
            "retryable": self.retryable,
        }


@dataclass(frozen=True)
class RecommendationRun:
    run_id: str
    actor_id: str
    request_hash: str
    idempotency_key: str
    patient_id: str
    encounter_id: str
    snapshot_id: str
    status: str
    requested_at: str
    updated_at: str
    findings: tuple[RecommendationRunFinding, ...] = ()
    completed_at: str | None = None
    primary_plan_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        value: dict[str, Any] = {
            "schemaVersion": SCHEMA_VERSION,
            "runId": self.run_id,
            "patientId": self.patient_id,
            "encounterId": self.encounter_id,
            "snapshotId": self.snapshot_id,
            "policyVersion": POLICY_VERSION,
            "status": self.status,
            "requestedAt": self.requested_at,
            "updatedAt": self.updated_at,
            "findings": [finding.to_dict() for finding in self.findings],
        }
        if self.completed_at is not None:
            value["completedAt"] = self.completed_at
        if self.primary_plan_id is not None:
            value["primaryPlanId"] = self.primary_plan_id
        return value

    def stored_dict(self) -> dict[str, Any]:
        return {
            **self.to_dict(),
            "actorId": self.actor_id,
            "requestHash": self.request_hash,
            "idempotencyKey": self.idempotency_key,
        }

    @classmethod
    def from_stored(cls, value: Mapping[str, Any]) -> "RecommendationRun":
        try:
            return cls(
                run_id=str(value["runId"]),
                actor_id=str(value["actorId"]),
                request_hash=str(value["requestHash"]),
                idempotency_key=str(value["idempotencyKey"]),
                patient_id=str(value["patientId"]),
                encounter_id=str(value["encounterId"]),
                snapshot_id=str(value["snapshotId"]),
                status=str(value["status"]),
                requested_at=str(value["requestedAt"]),
                updated_at=str(value["updatedAt"]),
                findings=tuple(
                    RecommendationRunFinding(
                        str(item["code"]), str(item["source"]), str(item["detail"]), bool(item["retryable"])
                    )
                    for item in value.get("findings", ())
                ),
                completed_at=str(value["completedAt"]) if "completedAt" in value else None,
                primary_plan_id=str(value["primaryPlanId"]) if "primaryPlanId" in value else None,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise RecommendationRunUnavailable("stored recommendation run is invalid") from exc


class RecommendationRunStore:
    """Repository-backed store with actor-scoped idempotency and monotonic transitions."""

    def __init__(self, repository: Repository) -> None:
        self._repository = repository
        self._lock = threading.Lock()

    def create_or_replay(
        self,
        actor_id: str,
        idempotency_key: str,
        request_hash: str,
        factory: Callable[[], RecommendationRun],
    ) -> tuple[RecommendationRun, bool]:
        lookup_key = self._idempotency_lookup(actor_id, idempotency_key)
        with self._lock:
            prior = self._repository.get(lookup_key)
            if prior is not None:
                run = self._load_json(prior.value)
                if run.request_hash != request_hash:
                    raise RecommendationRunIdempotencyConflict(
                        "Idempotency-Key was already used for a different recommendation request"
                    )
                return run, False
            run = factory()
            encoded = self._dump(run.stored_dict())
            self._repository.put(RuntimeRecord(self._run_key(run.run_id), encoded))
            self._repository.put(RuntimeRecord(lookup_key, encoded))
            return run, True

    def read(self, run_id: str, actor_id: str) -> RecommendationRun:
        record = self._repository.get(self._run_key(run_id))
        if record is None:
            raise RecommendationRunNotFound("recommendation run was not found")
        run = self._load_json(record.value)
        if run.actor_id != actor_id:
            raise RecommendationRunNotFound("recommendation run was not found")
        return run

    def transition(
        self,
        run: RecommendationRun,
        status: str,
        now: str,
        *,
        findings: tuple[RecommendationRunFinding, ...] = (),
        primary_plan_id: str | None = None,
    ) -> RecommendationRun:
        if status == run.status:
            return run
        if status not in _TRANSITIONS.get(run.status, frozenset()):
            raise RecommendationRunUnavailable(f"invalid recommendation-run transition {run.status} -> {status}")
        changed = replace(
            run,
            status=status,
            updated_at=now,
            findings=findings,
            completed_at=now if status in _TERMINAL else None,
            primary_plan_id=primary_plan_id,
        )
        encoded = self._dump(changed.stored_dict())
        with self._lock:
            current = self.read(run.run_id, run.actor_id)
            if current.status != run.status:
                if current == changed:
                    return current
                raise RecommendationRunUnavailable("recommendation run changed concurrently")
            self._repository.put(RuntimeRecord(self._run_key(run.run_id), encoded))
            self._repository.put(RuntimeRecord(self._idempotency_lookup(run.actor_id, run.idempotency_key), encoded))
        return changed

    @staticmethod
    def _run_key(run_id: str) -> str:
        return f"recommendation-run:{run_id}"

    @staticmethod
    def _idempotency_lookup(actor_id: str, key: str) -> str:
        digest = hashlib.sha256(f"{actor_id}\0{key}".encode("utf-8")).hexdigest()
        return f"recommendation-idempotency:{digest}"

    @staticmethod
    def _dump(value: Mapping[str, Any]) -> str:
        return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)

    @classmethod
    def _load_json(cls, value: str) -> RecommendationRun:
        try:
            payload = json.loads(value)
        except (TypeError, ValueError) as exc:
            raise RecommendationRunUnavailable("stored recommendation run is invalid") from exc
        if not isinstance(payload, dict):
            raise RecommendationRunUnavailable("stored recommendation run is invalid")
        return RecommendationRun.from_stored(payload)


class ContextAssembler(Protocol):
    async def assemble(
        self,
        patient_id: str,
        encounter_id: str,
        severity_assessment_id: str,
        request_context: OutboundRequestContext,
    ) -> ClinicalContext: ...


class EligibilityPolicy(Protocol):
    def evaluate(self, context: ClinicalContext, pathway_id: str) -> EligibilityDecision: ...


class RecommendationStages(Protocol):
    """Adapter over normalization, BN evaluation, DDI checking, synthesis, and plan persistence."""

    async def evaluate_bn(self, context: ClinicalContext, snapshot_id: str) -> Any: ...
    def synthesize(
        self, context: ClinicalContext, bn_result: Any, *, timezone: str
    ) -> Any: ...
    async def check_ddi(
        self, context: ClinicalContext, plan: Any, outbound_context: OutboundRequestContext
    ) -> Any: ...
    def persist(self, context: ClinicalContext, run_id: str, plan: Any, ddi_result: Any) -> str: ...


@dataclass(frozen=True)
class RecommendationGenerationInputs:
    bn_facts: NormalizedSnapshotFacts
    safety_candidates: tuple[ProbabilisticRecommendation, ...]
    safety_facts: SafetyFacts
    source_facts: tuple[SourceFact, ...]
    current_medications: tuple[Medication, ...]


class RecommendationInputMapper(Protocol):
    """Maps only approved, source-backed owner values into existing engine vocabularies."""

    def map(self, context: ClinicalContext, snapshot_id: str) -> RecommendationGenerationInputs: ...


@dataclass(frozen=True)
class _BnStageResult:
    inputs: RecommendationGenerationInputs
    bundle: BnEvaluationBundle


@dataclass(frozen=True)
class _PlanStageResult:
    inputs: RecommendationGenerationInputs
    plan: PrimaryTreatmentPlan


class TreatmentPlanRecommendationStages:
    """Concrete adapter over the existing BN, safety, synthesis, DDI, and ledger seams."""

    def __init__(
        self,
        mapper: RecommendationInputMapper,
        bn_orchestrator: BnEvaluationOrchestrator,
        ddi_checker: DdiMedicationChecker,
        plan_ledger: PlanEditLedger,
        *,
        safety_policy: SafetyPolicy | None = None,
        synthesizer: PrimaryPlanSynthesizer | None = None,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._mapper = mapper
        self._bn = bn_orchestrator
        self._ddi = ddi_checker
        self._ledger = plan_ledger
        self._safety = safety_policy or SafetyPolicy()
        self._synthesizer = synthesizer or PrimaryPlanSynthesizer()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._id_factory = id_factory or (lambda: str(uuid4()))

    async def evaluate_bn(self, context: ClinicalContext, snapshot_id: str) -> _BnStageResult:
        inputs = self._mapper.map(context, snapshot_id)
        if inputs.bn_facts.snapshot_id != snapshot_id:
            raise ValueError("normalized BN facts conflict with the recommendation snapshot")
        return _BnStageResult(inputs, await self._bn.evaluate(inputs.bn_facts))

    def synthesize(
        self, context: ClinicalContext, result: _BnStageResult, *, timezone: str
    ) -> _PlanStageResult:
        medication = next(
            (item for item in result.bundle.evaluations if item.model is BnModel.PHARMACOTHERAPY),
            None,
        )
        if medication is None:
            raise ValueError("pharmacotherapy BN evaluation is unavailable")
        posterior = dict(medication.posterior)
        if {item.recommendation_id for item in result.inputs.safety_candidates} != set(posterior):
            raise ValueError("BN pharmacotherapy candidates lack exact deterministic safety metadata")
        candidates = tuple(
            ProbabilisticRecommendation(
                item.recommendation_id,
                posterior[item.recommendation_id],
                item.substances,
                item.contraindication_codes,
                item.monitoring_requirement,
                item.supports_adherence,
            )
            for item in result.inputs.safety_candidates
            if item.recommendation_id in posterior
        )
        safety = self._safety.apply(candidates, result.inputs.safety_facts)
        return _PlanStageResult(
            result.inputs,
            self._synthesizer.synthesize(
                result.bundle, safety, result.inputs.source_facts, timezone=timezone
            ),
        )

    async def check_ddi(
        self, context: ClinicalContext, result: _PlanStageResult,
        outbound_context: OutboundRequestContext,
    ) -> DdiCheckResult:
        return await self._ddi.check(
            result.plan, result.inputs.current_medications, outbound_context
        )

    def persist(
        self,
        context: ClinicalContext,
        run_id: str,
        result: _PlanStageResult,
        ddi: DdiCheckResult,
    ) -> str:
        if ddi.failure is not None or ddi.unresolved_medications:
            raise ValueError("complete DDI coverage is required before Primary Plan persistence")
        plan_id = self._id_factory()
        UUID(plan_id)
        plan = result.plan
        now = self._clock().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        findings = []
        allowed_severity = {"info", "low", "moderate", "high", "critical"}
        for interaction in ddi.interactions:
            if interaction.severity not in allowed_severity:
                raise ValueError("DDI finding severity is outside the Treatment Plan contract")
            findings.append({
                "schemaVersion": "1.0.0",
                "findingId": self._id_factory(),
                "category": "interaction",
                "severity": interaction.severity,
                "status": "open",
                "summary": interaction.recommended_action,
                "detectedAt": now,
                "knowledgeVersion": ddi.knowledge_base_version,
            })
        primary = {
            "schemaVersion": "1.0.0",
            "planId": plan_id,
            "runId": run_id,
            "patientId": context.patient_id,
            "encounterId": context.encounter_id,
            "status": "generated",
            "createdAt": now,
            "content": {
                "setting": plan.treatment_setting.value["setting"],
                "pharmacotherapy": [dict(plan.pharmacotherapy.value)],
                "nextAppointment": dict(plan.next_appointment.value),
            },
            "rationale": [
                plan.treatment_setting.narrative,
                plan.pharmacotherapy.narrative,
                plan.next_appointment.narrative,
            ],
            "safetyFindings": findings,
        }
        self._ledger.create(plan_id, primary)
        return plan_id


class RecommendationRunWorkflow:
    def __init__(
        self,
        store: RecommendationRunStore,
        assembler: ContextAssembler,
        eligibility: EligibilityPolicy,
        stages: RecommendationStages,
        *,
        clock: Callable[[], datetime] | None = None,
        id_factory: Callable[[], str] | None = None,
    ) -> None:
        self._store = store
        self._assembler = assembler
        self._eligibility = eligibility
        self._stages = stages
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._id_factory = id_factory or (lambda: str(uuid4()))

    async def create(
        self,
        request: RecommendationRunRequest,
        *,
        actor_id: str,
        idempotency_key: str,
        outbound_context: OutboundRequestContext,
    ) -> RecommendationRun:
        self._validate_request(request, idempotency_key)
        request_hash = self._hash(request.canonical())
        now = self._now()
        run, created = self._store.create_or_replay(
            actor_id,
            idempotency_key,
            request_hash,
            lambda: RecommendationRun(
                self._id_factory(), actor_id, request_hash, idempotency_key,
                request.patient_id, request.encounter_id, self._id_factory(),
                "requested", now, now,
            ),
        )
        if not created or run.status in _TERMINAL:
            return run

        run = self._store.transition(run, "gathering-inputs", self._now())
        try:
            context = await self._assembler.assemble(
                request.patient_id,
                request.encounter_id,
                request.severity_assessment_id,
                outbound_context,
            )
            decision = self._eligibility.evaluate(context, POLICY_VERSION)
        except Exception as exc:
            finding = RecommendationRunFinding(
                "context-assembly-failed", "clinical-context", f"authoritative context unavailable: {type(exc).__name__}", True
            )
            return self._store.transition(run, "generation-failed", self._now(), findings=(finding,))

        if not decision.generation_allowed:
            findings = tuple(
                RecommendationRunFinding(item.code, item.fact, item.detail, False)
                for item in decision.findings
            )
            if not findings:
                findings = (RecommendationRunFinding(
                    "eligibility-blocked", "eligibility", "generation is not permitted by the active policy"
                ),)
            return self._store.transition(run, "inputs-incomplete", self._now(), findings=findings)

        run = self._store.transition(run, "evaluating", self._now())
        try:
            bn_result = await self._stages.evaluate_bn(context, run.snapshot_id)
            plan = self._stages.synthesize(
                context, bn_result, timezone=request.timezone
            )
            ddi_result = await self._stages.check_ddi(context, plan, outbound_context)
            plan_id = self._stages.persist(context, run.run_id, plan, ddi_result)
            UUID(plan_id)
        except Exception as exc:
            finding = RecommendationRunFinding(
                "generation-stage-failed", "recommendation-engine",
                f"recommendation generation failed: {type(exc).__name__}", False,
            )
            return self._store.transition(run, "generation-failed", self._now(), findings=(finding,))
        return self._store.transition(run, "generated", self._now(), primary_plan_id=plan_id)

    def read(self, run_id: str, actor_id: str) -> RecommendationRun:
        return self._store.read(run_id, actor_id)

    def _now(self) -> str:
        return self._clock().astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    @staticmethod
    def _hash(value: Mapping[str, Any]) -> str:
        encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
        return "sha256:" + hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _validate_request(request: RecommendationRunRequest, idempotency_key: str) -> None:
        for value in (request.patient_id, request.encounter_id, request.severity_assessment_id):
            try:
                parsed = UUID(value)
            except (TypeError, ValueError) as exc:
                raise RecommendationRunError("clinical identifiers must be canonical UUIDs") from exc
            if parsed.int == 0 or str(parsed) != value:
                raise RecommendationRunError("clinical identifiers must be canonical UUIDs")
        if not isinstance(request.timezone, str) or not re.fullmatch(r"[A-Za-z_]+/[A-Za-z_+-]+", request.timezone):
            raise RecommendationRunError("timezone must be an IANA-style area/location value")
        if not isinstance(idempotency_key, str) or not _IDEMPOTENCY_KEY.fullmatch(idempotency_key):
            raise RecommendationRunError("Idempotency-Key must contain 16 to 128 safe characters")
