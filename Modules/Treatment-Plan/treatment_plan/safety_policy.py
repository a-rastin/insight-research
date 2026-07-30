"""Deterministic safety overlay for probabilistic recommendations (TP-11)."""
from __future__ import annotations

import json
import math
from dataclasses import dataclass
from enum import Enum
from importlib.resources import files
from typing import Any, Mapping, Sequence

POLICY_ID = "schizophrenia-research-safety"
POLICY_VERSION = "1.0.0"


class Disposition(str, Enum):
    EXCLUDED = "excluded"
    CONDITIONAL = "conditional"
    DEPRIORITIZED = "deprioritized"
    STANDARD = "standard"
    PREFERRED = "preferred"


class SafetyOutcome(str, Enum):
    PROCEED = "proceed"
    REVIEW_REQUIRED = "review-required"
    EMERGENCY_ESCALATION = "emergency-escalation"


@dataclass(frozen=True)
class ProbabilisticRecommendation:
    recommendation_id: str
    probability: float
    substances: tuple[str, ...] = ()
    contraindication_codes: tuple[str, ...] = ()
    monitoring_requirement: str = "none"
    supports_adherence: bool = False


@dataclass(frozen=True)
class SafetyFacts:
    allergies: tuple[str, ...] = ()
    contraindications: tuple[str, ...] = ()
    suicide_risk: str | None = None
    monitoring_capacity: str | None = None
    prior_response: Mapping[str, str] | None = None
    adherence: str | None = None
    emergency_signals: tuple[str, ...] = ()


@dataclass(frozen=True)
class RuleTrace:
    rule_id: str
    priority: int
    severity: str
    summary: str
    evidence: tuple[str, ...]
    recommendation_id: str | None = None
    urgent: bool = False


@dataclass(frozen=True)
class AssessedRecommendation:
    recommendation: ProbabilisticRecommendation
    disposition: Disposition
    trace_rule_ids: tuple[str, ...]


@dataclass(frozen=True)
class EmergencyEscalation:
    required: bool
    required_action: str | None
    action_performed: bool = False


@dataclass(frozen=True)
class SafetyPolicyDecision:
    policy_id: str
    policy_version: str
    policy_status: str
    outcome: SafetyOutcome
    recommendations: tuple[AssessedRecommendation, ...]
    traces: tuple[RuleTrace, ...]
    escalation: EmergencyEscalation

    @property
    def urgent_traces(self) -> tuple[RuleTrace, ...]:
        return tuple(trace for trace in self.traces if trace.urgent)


@dataclass(frozen=True)
class _Rule:
    rule_id: str
    kind: str
    priority: int
    severity: str
    disposition: Disposition | None
    states: frozenset[str]
    levels: tuple[str, ...]
    action: str | None


@dataclass(frozen=True)
class _Definition:
    policy_id: str
    version: str
    status: str
    rules: tuple[_Rule, ...]


_DISPOSITION_STRENGTH = {
    Disposition.PREFERRED: 0,
    Disposition.STANDARD: 1,
    Disposition.DEPRIORITIZED: 2,
    Disposition.CONDITIONAL: 3,
    Disposition.EXCLUDED: 4,
}


def _normalized(value: Any) -> str:
    return "" if value is None else str(value).strip().casefold()


def _normalized_set(values: Sequence[str]) -> frozenset[str]:
    return frozenset(normalized for value in values if (normalized := _normalized(value)))


def _load_bundled_definition() -> _Definition:
    resource = files("treatment_plan.policies").joinpath("safety-policy.schizophrenia-research.v1.json")
    return _parse_definition(json.loads(resource.read_text(encoding="utf-8")))


def _parse_definition(payload: Mapping[str, Any]) -> _Definition:
    if payload.get("policyId") != POLICY_ID or payload.get("version") != POLICY_VERSION:
        raise ValueError("safety policy identity does not match the supported version")
    status, raw_rules = payload.get("status"), payload.get("rules")
    if not isinstance(status, str) or not status or not isinstance(raw_rules, list) or not raw_rules:
        raise ValueError("safety policy requires status and rules")
    rules: list[_Rule] = []
    seen: set[str] = set()
    for raw in raw_rules:
        if not isinstance(raw, Mapping):
            raise ValueError("each safety rule must be an object")
        rule_id, kind = raw.get("id"), raw.get("kind")
        priority, severity = raw.get("priority"), raw.get("severity")
        if not isinstance(rule_id, str) or not rule_id or rule_id in seen:
            raise ValueError("safety rule ids must be unique non-empty strings")
        if not isinstance(kind, str) or not kind or isinstance(priority, bool) or not isinstance(priority, int):
            raise ValueError(f"safety rule {rule_id} has invalid kind or priority")
        if severity not in {"info", "low", "moderate", "high", "critical"}:
            raise ValueError(f"safety rule {rule_id} has invalid severity")
        try:
            disposition = Disposition(raw["disposition"]) if "disposition" in raw else None
        except ValueError as exc:
            raise ValueError(f"safety rule {rule_id} has invalid disposition") from exc
        states, levels, action = raw.get("states", []), raw.get("levels", []), raw.get("action")
        if not isinstance(states, list) or not all(isinstance(item, str) for item in states):
            raise ValueError(f"safety rule {rule_id} has invalid states")
        if not isinstance(levels, list) or not all(isinstance(item, str) for item in levels):
            raise ValueError(f"safety rule {rule_id} has invalid levels")
        if action is not None and (not isinstance(action, str) or not action.strip()):
            raise ValueError(f"safety rule {rule_id} has invalid action")
        seen.add(rule_id)
        rules.append(_Rule(rule_id, kind, priority, severity, disposition, _normalized_set(states), tuple(_normalized(item) for item in levels), action))
    return _Definition(POLICY_ID, POLICY_VERSION, status, tuple(sorted(rules, key=lambda rule: (-rule.priority, rule.rule_id))))


class SafetyPolicy:
    def __init__(self, definition: Mapping[str, Any] | None = None):
        self._definition = _parse_definition(definition) if definition is not None else _load_bundled_definition()

    def apply(self, recommendations: Sequence[ProbabilisticRecommendation], facts: SafetyFacts) -> SafetyPolicyDecision:
        candidates = tuple(recommendations)
        self._validate_inputs(candidates, facts)
        traces: list[RuleTrace] = []
        matched: dict[str, list[_Rule]] = {candidate.recommendation_id: [] for candidate in candidates}
        escalation_actions: list[str] = []
        for rule in self._definition.rules:
            if rule.kind == "emergency-signal" and facts.emergency_signals:
                evidence = tuple(f"emergency signal: {signal}" for signal in facts.emergency_signals)
                traces.append(self._trace(rule, "Emergency evidence requires escalation regardless of model probability.", evidence, urgent=True))
                escalation_actions.append(rule.action or "Emergency escalation is required.")
            elif rule.kind == "suicide-risk" and _normalized(facts.suicide_risk) in rule.states:
                evidence = (f"suicide risk: {facts.suicide_risk}",)
                traces.append(self._trace(rule, "Urgent suicide-risk evidence requires escalation regardless of model probability.", evidence, urgent=True))
                escalation_actions.append(rule.action or "Emergency escalation is required.")
            else:
                for candidate in candidates:
                    evidence = self._candidate_evidence(rule, candidate, facts)
                    if evidence:
                        matched[candidate.recommendation_id].append(rule)
                        traces.append(self._trace(rule, self._summary(rule), evidence, recommendation_id=candidate.recommendation_id))
        assessed = tuple(self._assess(candidate, matched[candidate.recommendation_id]) for candidate in candidates)
        traces.sort(key=lambda trace: (-trace.priority, trace.recommendation_id or "", trace.rule_id))
        escalation_required = bool(escalation_actions)
        if escalation_required:
            outcome = SafetyOutcome.EMERGENCY_ESCALATION
        elif any(item.disposition in {Disposition.EXCLUDED, Disposition.CONDITIONAL} for item in assessed):
            outcome = SafetyOutcome.REVIEW_REQUIRED
        else:
            outcome = SafetyOutcome.PROCEED
        action = " ".join(dict.fromkeys(escalation_actions)) if escalation_actions else None
        return SafetyPolicyDecision(self._definition.policy_id, self._definition.version, self._definition.status, outcome, assessed, tuple(traces), EmergencyEscalation(escalation_required, action))

    @staticmethod
    def _validate_inputs(candidates: tuple[ProbabilisticRecommendation, ...], facts: SafetyFacts) -> None:
        ids: set[str] = set()
        for candidate in candidates:
            if not isinstance(candidate.recommendation_id, str) or not candidate.recommendation_id.strip():
                raise ValueError("recommendation_id is required")
            if candidate.recommendation_id in ids:
                raise ValueError("recommendation_id values must be unique")
            ids.add(candidate.recommendation_id)
            if isinstance(candidate.probability, bool) or not isinstance(candidate.probability, (int, float)):
                raise ValueError("recommendation probability must be numeric")
            if not math.isfinite(float(candidate.probability)) or not 0 <= candidate.probability <= 1:
                raise ValueError("recommendation probability must be finite and between zero and one")
        if facts.prior_response is not None and not isinstance(facts.prior_response, Mapping):
            raise ValueError("prior_response must be a mapping when provided")

    def _candidate_evidence(self, rule: _Rule, candidate: ProbabilisticRecommendation, facts: SafetyFacts) -> tuple[str, ...]:
        candidate_keys = _normalized_set((candidate.recommendation_id, *candidate.substances))
        if rule.kind == "allergy":
            return tuple(f"allergy match: {item}" for item in sorted(candidate_keys & _normalized_set(facts.allergies)))
        if rule.kind == "contraindication":
            keys = _normalized_set((candidate.recommendation_id, *candidate.contraindication_codes))
            return tuple(f"contraindication match: {item}" for item in sorted(keys & _normalized_set(facts.contraindications)))
        if rule.kind == "monitoring-capacity":
            capacity = _normalized(facts.monitoring_capacity)
            required = _normalized(candidate.monitoring_requirement)
            if capacity in rule.levels and required in rule.levels and rule.levels.index(capacity) < rule.levels.index(required):
                return (f"monitoring capacity: {capacity}", f"monitoring required: {required}")
        prior = facts.prior_response or {}
        prior_value = next((value for key, value in prior.items() if _normalized(key) == _normalized(candidate.recommendation_id)), None)
        if rule.kind.startswith("prior-response") and _normalized(prior_value) in rule.states:
            return (f"prior response: {prior_value}",)
        if rule.kind == "adherence" and _normalized(facts.adherence) in rule.states and not candidate.supports_adherence:
            return (f"adherence: {facts.adherence}", "candidate lacks an explicit adherence support feature")
        return ()

    @staticmethod
    def _summary(rule: _Rule) -> str:
        return {
            "allergy": "Recommendation excluded because it matches a recorded allergy.",
            "contraindication": "Recommendation excluded because it matches a recorded contraindication.",
            "monitoring-capacity": "Recommendation excluded because required monitoring exceeds documented capacity.",
            "prior-response-adverse": "Recommendation excluded because prior response was adverse or intolerable.",
            "adherence": "Recommendation requires review because documented adherence is poor and no support feature is identified.",
            "prior-response-beneficial": "Recommendation preferred because prior response was beneficial.",
        }.get(rule.kind, f"Safety rule {rule.rule_id} applied.")

    @staticmethod
    def _trace(rule: _Rule, summary: str, evidence: tuple[str, ...], recommendation_id: str | None = None, urgent: bool = False) -> RuleTrace:
        return RuleTrace(rule.rule_id, rule.priority, rule.severity, summary, evidence, recommendation_id, urgent)

    @staticmethod
    def _assess(candidate: ProbabilisticRecommendation, rules: list[_Rule]) -> AssessedRecommendation:
        applicable = [rule for rule in rules if rule.disposition is not None]
        disposition = max((rule.disposition for rule in applicable), key=lambda value: _DISPOSITION_STRENGTH[value], default=Disposition.STANDARD)
        ordered = sorted(rules, key=lambda item: (-item.priority, item.rule_id))
        return AssessedRecommendation(candidate, disposition, tuple(rule.rule_id for rule in ordered))
