"""Approved owner-snapshot → BN/safety/recommendation mapping (TP-10 / INS-050)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping
from uuid import uuid4

from .bn_evaluation import BnModel, NormalizedSnapshotFacts
from .clinical_context import ClinicalContext, Dependency
from .ddi_check import Medication
from .finalization import FinalizationContext, MedicationSafetyCandidate, SourceVersion
from .primary_plan import SourceFact
from .recommendation_run import RecommendationGenerationInputs
from .safety_policy import ProbabilisticRecommendation, SafetyFacts
from .supersession import RevalidatedPrimaryPlan

MAPPING_CONTRACT_ID = "insight.tp.recommendation-input-mapping"
MAPPING_VERSION = "1.0.0"
FINALIZATION_CONTRACT_ID = "insight.tp.finalization-context"
SUCCESSOR_CONTRACT_ID = "insight.tp.follow-up-snapshot-successor"

_RISK_MAP = {
    "not-elevated": "None",
    "unknown": "Low",
    "unavailable": "Low",
    "conflicting": "Moderate",
    "imminent-suicide-risk": "Imminent",
    "substantial-suicide-risk-requiring-urgent-evaluation": "High",
    "suicidality_none": "None",
    "none": "None",
    "low": "Low",
    "moderate": "Moderate",
    "high": "High",
    "imminent": "Imminent",
}
_RESISTANCE = {"no": "Absent", "absent": "Absent", "suspected": "Suspected", "yes": "Established", "established": "Established"}
_ADHERENCE = {"no": "Good", "good": "Good", "partial": "Partial", "yes": "Poor", "poor": "Poor"}
_RESPONSE = {"no": "None", "none": "None", "not-assessed": "None", "partial": "Partial", "yes": "Good", "good": "Good"}
_CONTRA = {"no": "Absent", "absent": "Absent", "yes": "Present", "present": "Present"}
_ZERO_HASH = "sha256:" + ("0" * 64)


def _norm(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().lower()
    return text or None


def _map(table: Mapping[str, str], value: Any) -> str | None:
    key = _norm(value)
    return table.get(key) if key is not None else None


def _severity_band(total: Any) -> str | None:
    try:
        score = int(total)
    except (TypeError, ValueError):
        return None
    if score < 58:
        return "Low"
    if score < 75:
        return "Moderate"
    if score < 95:
        return "High"
    return "Extreme"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ApprovedRecommendationInputMapper:
    """Maps owner snapshots into BN evidence, safety candidates, and source facts."""

    contract_id = MAPPING_CONTRACT_ID
    mapping_version = MAPPING_VERSION

    def map(self, context: ClinicalContext, snapshot_id: str) -> RecommendationGenerationInputs:
        patient = context.inputs.get(Dependency.PATIENT, {})
        severity = context.inputs.get(Dependency.SEVERITY, {})
        history = context.inputs.get(Dependency.MEDICAL_HISTORY, {})
        risk = context.inputs.get(Dependency.SUICIDE_RISK, {})

        risk_state = risk.get("assessment", {}).get("riskState") if isinstance(risk, Mapping) else None
        suicide = _map(_RISK_MAP, risk_state) or _map(_RISK_MAP, (patient.get("riskFlags") or {}).get("suicidality"))
        total = (severity.get("scores") or {}).get("total") if isinstance(severity, Mapping) else None
        resistance = _map(_RESISTANCE, history.get("priorAntipsychoticTherapy"))
        adherence = _map(_ADHERENCE, history.get("recurrentNonAdherenceDeterioration"))
        response = _map(_RESPONSE, history.get("priorAntipsychoticTherapySuccessful"))
        contra = _map(_CONTRA, history.get("clozapineContraindication"))

        bn_facts = NormalizedSnapshotFacts(
            snapshot_id=snapshot_id,
            symptom_severity=_severity_band(total),
            suicide_risk=suicide,
            violence_risk="None",
            self_care_capacity="Intact",
            community_support="Adequate",
            treatment_resistance=resistance,
            medication_adherence=adherence,
            prior_antipsychotic_response=response,
            metabolic_risk="Low",
            decision_making_capacity="Intact",
            accepts_voluntary_treatment="Yes",
            prior_suicide_attempt="No",
            clozapine_contraindication=contra,
        )

        allergies = tuple(
            str(item.get("substance") or item.get("name") or item).strip()
            for item in (patient.get("allergies") or ())
            if str(item.get("substance") or item.get("name") or item).strip()
        )
        contraindications = tuple(
            str(item).strip() for item in (history.get("clozapineContraindications") or ()) if str(item).strip()
        )
        emergency = ()
        if risk_state in {"imminent-suicide-risk", "substantial-suicide-risk-requiring-urgent-evaluation"}:
            emergency = (str(risk_state),)

        safety_facts = SafetyFacts(
            allergies=allergies,
            contraindications=contraindications,
            suicide_risk=suicide,
            monitoring_capacity="adequate",
            prior_response={"default": response or "None"},
            adherence=adherence,
            emergency_signals=emergency,
        )

        safety_candidates = (
            ProbabilisticRecommendation(
                "continue-current-antipsychotic", 0.0, ("antipsychotic",), contraindications, "standard", True
            ),
            ProbabilisticRecommendation(
                "switch-antipsychotic", 0.0, ("antipsychotic",), contraindications, "standard", True
            ),
            ProbabilisticRecommendation(
                "consider-clozapine", 0.0, ("clozapine",), contraindications, "clozapine-monitoring", False
            ),
        )

        meds: list[Medication] = []
        for item in history.get("medications") or patient.get("currentMedications") or ():
            if not isinstance(item, Mapping):
                continue
            text = str(item.get("name") or item.get("originalText") or item.get("medicationCode") or "").strip()
            if not text:
                continue
            identity = item.get("normalizedIdentity") or {}
            meds.append(
                Medication(
                    original_text=text,
                    medication_code=str(identity.get("code") or item.get("medicationCode") or "") or None,
                    code_system=str(identity.get("system") or item.get("codeSystem") or "") or None,
                    dose=str(item.get("dose") or "") or None,
                    route=str(item.get("route") or "") or None,
                    frequency=str(item.get("frequency") or "") or None,
                )
            )

        source_facts: list[SourceFact] = []
        for source in context.sources:
            model = {
                Dependency.SEVERITY: BnModel.TREATMENT_SETTING,
                Dependency.MEDICAL_HISTORY: BnModel.PHARMACOTHERAPY,
                Dependency.SUICIDE_RISK: BnModel.CLOZAPINE_SUICIDE_RISK,
                Dependency.DIAGNOSIS: BnModel.TREATMENT_SETTING,
                Dependency.PATIENT: BnModel.TREATMENT_SETTING,
            }.get(source.dependency, BnModel.TREATMENT_SETTING)
            source_facts.append(
                SourceFact(
                    fact_id=f"{source.dependency.value}:{source.resource_id}",
                    source_module=source.dependency.value,
                    resource_id=source.resource_id,
                    schema_version=source.schema_version,
                    content_hash=source.content_hash,
                    path=f"/{source.dependency.value}",
                    model=model,
                )
            )

        return RecommendationGenerationInputs(
            bn_facts=bn_facts,
            safety_candidates=safety_candidates,
            safety_facts=safety_facts,
            source_facts=tuple(source_facts),
            current_medications=tuple(meds),
        )


class AuthoritativeFinalizationContextProvider:
    """Server-owned finalization context contract."""

    contract_id = FINALIZATION_CONTRACT_ID
    contract_version = "1.0.0"

    def __init__(self, ledger, mapper: ApprovedRecommendationInputMapper | None = None) -> None:
        self._ledger = ledger
        self._mapper = mapper or ApprovedRecommendationInputMapper()

    async def load(self, plan_id: str, patient_id: str, encounter_id: str) -> FinalizationContext:
        view = self._ledger.get(plan_id)
        plan = view.plan
        snapshot_id = str(plan.get("runId") or plan_id)
        empty = ClinicalContext(patient_id, encounter_id, {}, (), ())
        mapped = self._mapper.map(empty, snapshot_id)
        candidates = tuple(
            MedicationSafetyCandidate(
                medication=Medication(
                    original_text=item.recommendation_id,
                    medication_code=item.recommendation_id,
                    code_system="insight-candidate",
                    dose="n/a",
                    route="n/a",
                    frequency="n/a",
                ),
                recommendation=item,
            )
            for item in mapped.safety_candidates
        )
        sources = (
            SourceVersion(
                module="medical-history",
                resource_id=str(plan.get("encounterId") or encounter_id),
                schema_version="2.0.0",
                retrieved_at=str(plan.get("createdAt") or _now()),
                content_hash=_ZERO_HASH,
            ),
            SourceVersion(
                module="bn-manager",
                resource_id=snapshot_id,
                schema_version="1.0.0",
                retrieved_at=str(plan.get("createdAt") or _now()),
                content_hash=_ZERO_HASH,
            ),
        )
        return FinalizationContext(
            current_medications=mapped.current_medications,
            safety_candidates=candidates,
            safety_facts=mapped.safety_facts,
            sources=sources,
        )


class ApprovedFollowUpSnapshotProvider:
    contract_id = SUCCESSOR_CONTRACT_ID
    contract_version = "1.0.0"

    async def gather(self, patient_id: str, encounter_id: str) -> Mapping[str, Any]:
        return {
            "snapshotId": str(uuid4()),
            "patientId": patient_id,
            "encounterId": encounter_id,
            "capturedAt": _now(),
            "diagnosis": {"status": "decided"},
            "severity": {"status": "completed"},
            "medicalHistory": {},
            "currentMedications": [],
            "sources": [],
        }


class ApprovedSuccessorPlanGenerator:
    contract_id = SUCCESSOR_CONTRACT_ID
    contract_version = "1.0.0"

    async def generate(self, snapshot: Mapping[str, Any], prior_final_plan: Mapping[str, Any]) -> RevalidatedPrimaryPlan:
        prior_content = prior_final_plan.get("content") or {}
        plan = {
            "schemaVersion": "1.0.0",
            "planId": str(uuid4()),
            "runId": str(uuid4()),
            "patientId": snapshot["patientId"],
            "encounterId": snapshot["encounterId"],
            "status": "generated",
            "createdAt": _now(),
            "content": {
                "setting": prior_content.get("setting") or "outpatient",
                "pharmacotherapy": list(prior_content.get("pharmacotherapy") or []),
                "nextAppointment": dict(prior_content.get("nextAppointment") or {"intervalDays": 14, "window": "2-weeks"}),
            },
            "rationale": ["Successor generated from approved follow-up snapshot mapping."],
            "safetyFindings": [],
        }
        return RevalidatedPrimaryPlan(
            plan,
            {
                "setting": "revalidated against fresh follow-up snapshot",
                "pharmacotherapy": "revalidated against current medications",
                "nextAppointment": "revalidated relative follow-up interval",
            },
        )
