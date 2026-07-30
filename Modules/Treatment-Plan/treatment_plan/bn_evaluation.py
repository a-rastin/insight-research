"""Fail-closed Bayesian-network evidence mapping and orchestration (TP-10).

The public seam is :class:`BnEvaluationOrchestrator`.  Evidence vocabulary
details stay in this module so callers cannot accidentally send normalized
snapshot values directly to BN Manager.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import time
from dataclasses import asdict, dataclass, fields
from enum import Enum
from typing import Any, Mapping, Protocol

import httpx

from .observability import current_observability


MAPPING_VERSION = "1.0.0"
_SHA256 = re.compile(r"^sha256:[a-f0-9]{64}$")


class BnModel(str, Enum):
    TREATMENT_SETTING = "treatment-setting"
    PHARMACOTHERAPY = "pharmacotherapy"
    INVOLUNTARY_TREATMENT = "involuntary-treatment-considerations"
    CLOZAPINE_SUICIDE_RISK = "clozapine-suicide-risk"


class BnFindingCode(str, Enum):
    UNSUPPORTED_EVIDENCE_STATE = "unsupported-evidence-state"
    MODEL_EVALUATION_FAILED = "model-evaluation-failed"
    INVALID_MODEL_RESPONSE = "invalid-model-response"
    STORAGE_FAILED = "storage-failed"


@dataclass(frozen=True)
class NormalizedSnapshotFacts:
    """The normalized, non-inferred facts that the four BN models can consume.

    Values deliberately remain strings rather than Enums: an upstream value
    outside the stable vocabulary must become a typed finding, not an exception
    or an implicit default.
    """

    snapshot_id: str
    symptom_severity: str | None = None
    suicide_risk: str | None = None
    violence_risk: str | None = None
    self_care_capacity: str | None = None
    community_support: str | None = None
    treatment_resistance: str | None = None
    medication_adherence: str | None = None
    prior_antipsychotic_response: str | None = None
    metabolic_risk: str | None = None
    decision_making_capacity: str | None = None
    accepts_voluntary_treatment: str | None = None
    prior_suicide_attempt: str | None = None
    clozapine_contraindication: str | None = None

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "NormalizedSnapshotFacts":
        allowed = {field.name for field in fields(cls)}
        unknown = sorted(set(value) - allowed)
        if unknown:
            raise ValueError("unsupported normalized fact names: " + ", ".join(unknown))
        return cls(**value)


@dataclass(frozen=True)
class BnFinding:
    code: BnFindingCode
    model: BnModel | None
    fact: str | None
    value: Any
    detail: str


@dataclass(frozen=True)
class MappingCoverage:
    model: BnModel
    expected: int
    mapped: int
    missing_facts: tuple[str, ...]
    unsupported_facts: tuple[str, ...]

    @property
    def ratio(self) -> float:
        return self.mapped / self.expected if self.expected else 1.0


@dataclass(frozen=True)
class RawBnEvaluation:
    evaluation_id: str
    model_id: str
    model_version: str
    model_hash: str
    posterior: Mapping[str, float]
    evaluated_at: str | None = None


@dataclass(frozen=True)
class ModelEvaluation:
    evaluation_id: str
    model: BnModel
    model_version: str
    model_hash: str
    evidence: tuple[tuple[str, str], ...]
    posterior: tuple[tuple[str, float], ...]
    evaluated_at: str | None


@dataclass(frozen=True)
class BnEvaluationBundle:
    snapshot_id: str
    mapping_version: str
    evaluations: tuple[ModelEvaluation, ...]
    coverage: tuple[MappingCoverage, ...]
    findings: tuple[BnFinding, ...]

    @property
    def complete(self) -> bool:
        return len(self.evaluations) == len(BnModel) and not self.findings

    def to_dict(self) -> dict[str, Any]:
        def convert(value: Any) -> Any:
            if isinstance(value, Enum):
                return value.value
            if isinstance(value, tuple):
                return [convert(item) for item in value]
            if isinstance(value, dict):
                return {key: convert(item) for key, item in value.items()}
            return value

        return convert(asdict(self))

    @property
    def content_hash(self) -> str:
        canonical = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":")).encode()
        return "sha256:" + hashlib.sha256(canonical).hexdigest()


class BnEvaluator(Protocol):
    async def evaluate(
        self, model: BnModel, evidence: Mapping[str, str], mapping_version: str
    ) -> RawBnEvaluation: ...


class BnEvaluationStore(Protocol):
    def save(self, bundle: BnEvaluationBundle) -> None: ...


class InMemoryBnEvaluationStore:
    """Test/standalone adapter with immutable, idempotent snapshot records."""

    def __init__(self) -> None:
        self._records: dict[str, BnEvaluationBundle] = {}

    def save(self, bundle: BnEvaluationBundle) -> None:
        previous = self._records.get(bundle.snapshot_id)
        if previous is not None and previous != bundle:
            raise ValueError("a different BN bundle is already stored for this snapshot")
        self._records[bundle.snapshot_id] = bundle

    def get(self, snapshot_id: str) -> BnEvaluationBundle | None:
        return self._records.get(snapshot_id)


class BnManagerHttpEvaluator:
    """Production REST adapter for the owned BN Manager seam."""

    def __init__(self, base_url: str, client: httpx.AsyncClient, timeout_seconds: float = 3.0):
        self._base_url = base_url.rstrip("/")
        self._client = client
        self._timeout = timeout_seconds

    async def evaluate(
        self, model: BnModel, evidence: Mapping[str, str], mapping_version: str
    ) -> RawBnEvaluation:
        stable_id = f"bnm.{model.value}"
        request_body = {
            "stable_id": stable_id,
            "evidence": dict(evidence),
        }
        idempotency_key = hashlib.sha256(
            json.dumps(request_body, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        response = await self._client.post(
            f"{self._base_url}/api/bn-manager/v3/evaluations",
            headers={
                "Accept": "application/json",
                "Content-Type": "application/json",
                "Idempotency-Key": idempotency_key,
            },
            json=request_body,
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()["data"]
        model_identity = payload["model"]
        if payload.get("mapping_version") != mapping_version:
            raise ValueError("BN Manager mapping_version does not match the requested mapping")
        return RawBnEvaluation(
            evaluation_id=payload.get("evaluation_id"),
            model_id=str(model_identity.get("stable_id", "")).removeprefix("bnm."),
            model_version=model_identity.get("semantic_version"),
            model_hash=model_identity.get("content_hash"),
            posterior=payload.get("posterior"),
            evaluated_at=payload.get("evaluated_at"),
        )


@dataclass(frozen=True)
class _EvidenceRule:
    fact: str
    node: str
    states: Mapping[str, str]


def _states(*values: str) -> Mapping[str, str]:
    return {value.lower(): value for value in values}


_RISK = _states("None", "Low", "Moderate", "High", "Imminent")
_MODEL_RULES: Mapping[BnModel, tuple[_EvidenceRule, ...]] = {
    BnModel.TREATMENT_SETTING: (
        _EvidenceRule("symptom_severity", "SymptomSeverity", _states("Low", "Moderate", "High", "Extreme")),
        _EvidenceRule("suicide_risk", "SuicideRisk", _RISK),
        _EvidenceRule("violence_risk", "ViolenceRisk", _RISK),
        _EvidenceRule("self_care_capacity", "SelfCareCapacity", _states("Intact", "Impaired", "Unable")),
        _EvidenceRule("community_support", "CommunitySupport", _states("Adequate", "Limited", "None")),
    ),
    BnModel.PHARMACOTHERAPY: (
        _EvidenceRule("treatment_resistance", "TreatmentResistance", _states("Absent", "Suspected", "Established")),
        _EvidenceRule("medication_adherence", "MedicationAdherence", _states("Good", "Partial", "Poor")),
        _EvidenceRule("prior_antipsychotic_response", "PriorAntipsychoticResponse", _states("None", "Partial", "Good")),
        _EvidenceRule("metabolic_risk", "MetabolicRisk", _states("Low", "Moderate", "High")),
    ),
    BnModel.INVOLUNTARY_TREATMENT: (
        _EvidenceRule("suicide_risk", "SuicideRisk", _RISK),
        _EvidenceRule("violence_risk", "ViolenceRisk", _RISK),
        _EvidenceRule("self_care_capacity", "SelfCareCapacity", _states("Intact", "Impaired", "Unable")),
        _EvidenceRule("decision_making_capacity", "DecisionMakingCapacity", _states("Intact", "Impaired", "Absent")),
        _EvidenceRule("accepts_voluntary_treatment", "AcceptsVoluntaryTreatment", _states("Yes", "No")),
    ),
    BnModel.CLOZAPINE_SUICIDE_RISK: (
        _EvidenceRule("treatment_resistance", "TreatmentResistance", _states("Absent", "Suspected", "Established")),
        _EvidenceRule("suicide_risk", "SuicideRisk", _RISK),
        _EvidenceRule("prior_suicide_attempt", "PriorSuicideAttempt", _states("Yes", "No")),
        _EvidenceRule("clozapine_contraindication", "ClozapineContraindication", _states("Absent", "Present")),
    ),
}


class BnEvaluationOrchestrator:
    """Map, evaluate, validate, and store all four BN results through one interface."""

    def __init__(self, evaluator: BnEvaluator, store: BnEvaluationStore):
        self._evaluator = evaluator
        self._store = store

    async def evaluate(self, facts: NormalizedSnapshotFacts) -> BnEvaluationBundle:
        if not isinstance(facts.snapshot_id, str) or not facts.snapshot_id.strip():
            raise ValueError("snapshot_id is required")

        requests: list[tuple[BnModel, dict[str, str]]] = []
        coverage: list[MappingCoverage] = []
        findings: list[BnFinding] = []
        for model, rules in _MODEL_RULES.items():
            evidence: dict[str, str] = {}
            missing: list[str] = []
            unsupported: list[str] = []
            for rule in rules:
                raw = getattr(facts, rule.fact)
                if raw is None:
                    missing.append(rule.fact)
                    continue
                normalized = raw.strip().lower() if isinstance(raw, str) else None
                mapped = rule.states.get(normalized) if normalized is not None else None
                if mapped is None:
                    unsupported.append(rule.fact)
                    findings.append(BnFinding(
                        BnFindingCode.UNSUPPORTED_EVIDENCE_STATE,
                        model,
                        rule.fact,
                        raw,
                        f"state is outside mapping {MAPPING_VERSION}; evidence node was omitted",
                    ))
                    continue
                evidence[rule.node] = mapped
            requests.append((model, evidence))
            coverage.append(MappingCoverage(
                model, len(rules), len(evidence), tuple(missing), tuple(unsupported)
            ))

        raw_results = await asyncio.gather(
            *(self._evaluate_one(model, evidence) for model, evidence in requests)
        )
        evaluations: list[ModelEvaluation] = []
        for (model, evidence), result in zip(requests, raw_results):
            if isinstance(result, BnFinding):
                findings.append(result)
                continue
            try:
                evaluations.append(self._validate(model, evidence, result))
            except ValueError as exc:
                findings.append(BnFinding(
                    BnFindingCode.INVALID_MODEL_RESPONSE, model, None, None, str(exc)
                ))

        observer = current_observability()
        for item in coverage:
            if item.missing_facts:
                observer.metric("tp_missing_input_total", len(item.missing_facts),
                                labels={"kind": "bn-evidence", "model": item.model.value})
        for item in evaluations:
            observer.metric("tp_version_info", labels={"kind": "model", "model": item.model.value, "version": item.model_version})
        observer.metric("tp_generation_total", labels={
            "kind": "bn-evaluation", "outcome": "partial" if findings else "success", "version": MAPPING_VERSION,
        })
        bundle = BnEvaluationBundle(
            facts.snapshot_id,
            MAPPING_VERSION,
            tuple(evaluations),
            tuple(coverage),
            tuple(findings),
        )
        try:
            self._store.save(bundle)
        except Exception as exc:
            bundle = BnEvaluationBundle(
                bundle.snapshot_id,
                bundle.mapping_version,
                bundle.evaluations,
                bundle.coverage,
                bundle.findings + (BnFinding(
                    BnFindingCode.STORAGE_FAILED,
                    None,
                    None,
                    None,
                    f"BN evaluation storage failed: {type(exc).__name__}",
                ),),
            )
        return bundle

    async def _evaluate_one(
        self, model: BnModel, evidence: Mapping[str, str]
    ) -> RawBnEvaluation | BnFinding:
        started = time.monotonic()
        observer = current_observability()
        try:
            result = await self._evaluator.evaluate(model, evidence, MAPPING_VERSION)
        except Exception as exc:
            observer.metric("tp_dependency_latency_ms", (time.monotonic() - started) * 1000,
                            labels={"dependency": "bn-manager", "model": model.value, "outcome": "failure"})
            observer.metric("tp_dependency_failure_total", labels={"dependency": "bn-manager", "model": model.value, "outcome": "failure"})
            return BnFinding(
                BnFindingCode.MODEL_EVALUATION_FAILED,
                model,
                None,
                None,
                f"BN evaluation failed: {type(exc).__name__}",
            )
        observer.metric("tp_dependency_latency_ms", (time.monotonic() - started) * 1000,
                        labels={"dependency": "bn-manager", "model": model.value, "outcome": "success"})
        return result

    @staticmethod
    def _validate(
        model: BnModel, evidence: Mapping[str, str], result: RawBnEvaluation
    ) -> ModelEvaluation:
        if not isinstance(result.evaluation_id, str) or not result.evaluation_id.strip():
            raise ValueError("evaluationId is missing")
        if result.model_id != model.value:
            raise ValueError("modelId does not match the requested model")
        if not isinstance(result.model_version, str) or not result.model_version.strip():
            raise ValueError("exact modelVersion is missing")
        if not isinstance(result.model_hash, str) or not _SHA256.fullmatch(result.model_hash):
            raise ValueError("exact modelHash must be a lowercase sha256 digest")
        if not isinstance(result.posterior, Mapping) or not result.posterior:
            raise ValueError("posterior must be a non-empty distribution")
        posterior: list[tuple[str, float]] = []
        for state, probability in result.posterior.items():
            if not isinstance(state, str) or not state.strip():
                raise ValueError("posterior state names must be non-empty strings")
            if isinstance(probability, bool) or not isinstance(probability, (int, float)):
                raise ValueError("posterior probabilities must be numeric")
            probability = float(probability)
            if not math.isfinite(probability) or not 0.0 <= probability <= 1.0:
                raise ValueError("posterior probabilities must be finite and between zero and one")
            posterior.append((state, probability))
        if not math.isclose(sum(value for _, value in posterior), 1.0, abs_tol=1e-6):
            raise ValueError("posterior probabilities must sum to one")
        return ModelEvaluation(
            result.evaluation_id,
            model,
            result.model_version,
            result.model_hash,
            tuple(sorted(evidence.items())),
            tuple(sorted(posterior)),
            result.evaluated_at,
        )


