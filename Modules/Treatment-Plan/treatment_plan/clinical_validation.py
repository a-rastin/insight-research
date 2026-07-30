"""Clinical validation metrics and fail-closed safety-case release decision (TP-21)."""

from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Iterable, Mapping, Sequence


_ID = re.compile(r"^[A-Z][A-Z0-9-]{2,63}$")
_CLINICIAN_ROLES = frozenset({"psychiatrist", "clinicalSafetyOfficer"})
_REQUIRED_APPROVALS = frozenset({"independentPsychiatrist", "clinicalSafetyOfficer"})


class CaseKind(StrEnum):
    REFERENCE = "reference"
    EDGE = "edge"
    COUNTERFACTUAL = "counterfactual"
    SUBGROUP = "subgroup"
    FAILURE_INJECTION = "failureInjection"
    OVERRIDE_WORKFLOW = "overrideWorkflow"


@dataclass(frozen=True)
class ValidationProtocol:
    evidence_ref: str
    max_unsafe_omission_rate: float
    max_unsafe_commission_rate: float
    min_concordance: float
    max_alerts_per_case: float
    min_task_completion_rate: float
    max_use_error_rate: float
    max_brier_score: float | None = None

    def __post_init__(self) -> None:
        if not self.evidence_ref.strip():
            raise ValueError("validation protocol requires a controlled evidence reference")
        for name in (
            "max_unsafe_omission_rate", "max_unsafe_commission_rate", "min_concordance",
            "min_task_completion_rate", "max_use_error_rate",
        ):
            value = getattr(self, name)
            if not 0 <= value <= 1:
                raise ValueError(f"{name} must be between zero and one")
        if self.max_alerts_per_case < 0:
            raise ValueError("max_alerts_per_case cannot be negative")
        if self.max_brier_score is not None and not 0 <= self.max_brier_score <= 1:
            raise ValueError("max_brier_score must be between zero and one")


@dataclass(frozen=True)
class ClinicalCase:
    case_id: str
    kind: CaseKind
    author_role: str
    author_evidence_ref: str
    expected_actions: frozenset[str] = frozenset()
    prohibited_actions: frozenset[str] = frozenset()
    expected_unresolved: frozenset[str] = frozenset()
    subgroup: str | None = None
    expected_override: bool | None = None
    calibration_outcomes: tuple[tuple[str, bool], ...] = ()

    def __post_init__(self) -> None:
        if not _ID.fullmatch(self.case_id):
            raise ValueError("case_id must be a stable uppercase identifier")
        if self.author_role not in _CLINICIAN_ROLES or not self.author_evidence_ref.strip():
            raise ValueError("each case requires attributable clinician authorship evidence")
        if self.kind is CaseKind.SUBGROUP and not (self.subgroup and self.subgroup.strip()):
            raise ValueError("subgroup cases must name the evaluated subgroup")
        if self.expected_actions & self.prohibited_actions:
            raise ValueError("an action cannot be both expected and prohibited")


@dataclass(frozen=True)
class CaseObservation:
    case_id: str
    actions: frozenset[str]
    unresolved: frozenset[str]
    alerts: tuple[str, ...]
    task_completed: bool
    use_errors: int
    completion_seconds: float | None
    override_used: bool | None = None
    override_authorized: bool | None = None
    probabilities: tuple[tuple[str, float], ...] = ()

    def __post_init__(self) -> None:
        if self.use_errors < 0:
            raise ValueError("use_errors cannot be negative")
        if self.completion_seconds is not None and self.completion_seconds < 0:
            raise ValueError("completion_seconds cannot be negative")
        if any(not 0 <= probability <= 1 for _, probability in self.probabilities):
            raise ValueError("probabilities must be between zero and one")


@dataclass(frozen=True)
class Mitigation:
    mitigation_id: str
    description: str
    test_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        if not _ID.fullmatch(self.mitigation_id) or not self.description.strip():
            raise ValueError("mitigations require stable identifiers and descriptions")
        if not self.test_refs or any(not ref.strip() for ref in self.test_refs):
            raise ValueError("every mitigation must trace to at least one test")


@dataclass(frozen=True)
class Hazard:
    hazard_id: str
    unsafe_condition: str
    severity: str
    status: str
    mitigations: tuple[Mitigation, ...]

    def __post_init__(self) -> None:
        if not _ID.fullmatch(self.hazard_id) or not self.unsafe_condition.strip():
            raise ValueError("hazards require stable identifiers and an unsafe condition")
        if self.severity not in {"minor", "major", "critical", "catastrophic"}:
            raise ValueError("hazard severity is invalid")
        if self.status not in {"open", "mitigated", "accepted"}:
            raise ValueError("hazard status is invalid")
        if not self.mitigations:
            raise ValueError("hazards require traced mitigations")


@dataclass(frozen=True)
class Approval:
    role: str
    reviewer_id: str
    independent: bool
    signed_at: str
    evidence_ref: str
    report_sha256: str


@dataclass(frozen=True)
class ValidationReport:
    protocol_ref: str
    case_count: int
    metrics: Mapping[str, float | int | None]
    failures: tuple[str, ...]
    covered_case_kinds: tuple[str, ...]
    hazard_ids: tuple[str, ...]

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "protocolRef": self.protocol_ref,
            "caseCount": self.case_count,
            "metrics": dict(self.metrics),
            "failures": list(self.failures),
            "coveredCaseKinds": list(self.covered_case_kinds),
            "hazardIds": list(self.hazard_ids),
        }

    @property
    def sha256(self) -> str:
        canonical = json.dumps(self.canonical_payload(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ReleaseDecision:
    approved: bool
    failures: tuple[str, ...]


class ClinicalSafetyCase:
    """Evaluate a complete case set and bind human approvals to the resulting report."""

    def evaluate(
        self,
        protocol: ValidationProtocol,
        cases: Sequence[ClinicalCase],
        observations: Sequence[CaseObservation],
        hazards: Sequence[Hazard],
    ) -> ValidationReport:
        failures: list[str] = []
        case_by_id = _unique(cases, lambda item: item.case_id, "case")
        observation_by_id = _unique(observations, lambda item: item.case_id, "observation")
        required_kinds = set(CaseKind)
        covered_kinds = {case.kind for case in cases}
        missing_kinds = sorted(kind.value for kind in required_kinds - covered_kinds)
        if missing_kinds:
            failures.append("missing case kinds: " + ", ".join(missing_kinds))
        missing_results = sorted(set(case_by_id) - set(observation_by_id))
        unexpected_results = sorted(set(observation_by_id) - set(case_by_id))
        if missing_results:
            failures.append("missing case observations: " + ", ".join(missing_results))
        if unexpected_results:
            failures.append("observations without authored cases: " + ", ".join(unexpected_results))
        if not hazards:
            failures.append("hazard log is empty")
        open_hazards = sorted(hazard.hazard_id for hazard in hazards if hazard.status == "open")
        if open_hazards:
            failures.append("open hazards: " + ", ".join(open_hazards))

        omissions = commissions = required_total = prohibited_total = 0
        concordances: list[float] = []
        unresolved_count = alert_count = completed = use_errors = 0
        completion_times: list[float] = []
        brier_terms: list[float] = []
        override_failures = 0

        for case_id in sorted(set(case_by_id) & set(observation_by_id)):
            case = case_by_id[case_id]
            observed = observation_by_id[case_id]
            omissions += len(case.expected_actions - observed.actions)
            commissions += len(case.prohibited_actions & observed.actions)
            required_total += len(case.expected_actions)
            prohibited_total += len(case.prohibited_actions)
            union = case.expected_actions | observed.actions
            concordances.append(len(case.expected_actions & observed.actions) / len(union) if union else 1.0)
            unresolved_count += len(observed.unresolved)
            alert_count += len(observed.alerts)
            completed += int(observed.task_completed)
            use_errors += observed.use_errors
            if observed.completion_seconds is not None:
                completion_times.append(observed.completion_seconds)
            if observed.override_used and observed.override_authorized is not True:
                override_failures += 1
            if case.expected_override is not None and observed.override_used is not case.expected_override:
                override_failures += 1
            expected_probability = dict(case.calibration_outcomes)
            for label, probability in observed.probabilities:
                if label in expected_probability:
                    brier_terms.append((probability - int(expected_probability[label])) ** 2)

        evaluated = len(set(case_by_id) & set(observation_by_id))
        omission_rate = omissions / required_total if required_total else 0.0
        commission_rate = commissions / prohibited_total if prohibited_total else 0.0
        concordance = statistics.fmean(concordances) if concordances else 0.0
        alerts_per_case = alert_count / evaluated if evaluated else math.inf
        completion_rate = completed / evaluated if evaluated else 0.0
        use_error_rate = use_errors / evaluated if evaluated else math.inf
        brier_score = statistics.fmean(brier_terms) if brier_terms else None
        metrics: dict[str, float | int | None] = {
            "unsafeOmissionCount": omissions,
            "unsafeOmissionRate": omission_rate,
            "unsafeCommissionCount": commissions,
            "unsafeCommissionRate": commission_rate,
            "concordance": concordance,
            "brierScore": brier_score,
            "unresolvedDataCount": unresolved_count,
            "alertsPerCase": alerts_per_case,
            "taskCompletionRate": completion_rate,
            "useErrorRate": use_error_rate,
            "medianCompletionSeconds": statistics.median(completion_times) if completion_times else None,
            "overrideWorkflowFailures": override_failures,
        }
        comparisons = (
            (omission_rate > protocol.max_unsafe_omission_rate, "unsafe omission threshold exceeded"),
            (commission_rate > protocol.max_unsafe_commission_rate, "unsafe commission threshold exceeded"),
            (concordance < protocol.min_concordance, "clinical concordance threshold not met"),
            (alerts_per_case > protocol.max_alerts_per_case, "alert burden threshold exceeded"),
            (completion_rate < protocol.min_task_completion_rate, "human-factors completion threshold not met"),
            (use_error_rate > protocol.max_use_error_rate, "human-factors use-error threshold exceeded"),
            (override_failures > 0, "override workflow failures observed"),
            (
                protocol.max_brier_score is not None
                and (brier_score is None or brier_score > protocol.max_brier_score),
                "calibration threshold not met",
            ),
        )
        failures.extend(message for failed, message in comparisons if failed)
        return ValidationReport(
            protocol.evidence_ref,
            len(cases),
            metrics,
            tuple(failures),
            tuple(sorted(kind.value for kind in covered_kinds)),
            tuple(sorted(hazard.hazard_id for hazard in hazards)),
        )

    def release_decision(self, report: ValidationReport, approvals: Sequence[Approval]) -> ReleaseDecision:
        failures = list(report.failures)
        by_role: dict[str, Approval] = {}
        for approval in approvals:
            if approval.role in by_role:
                failures.append(f"duplicate approval role: {approval.role}")
            by_role[approval.role] = approval
        missing = sorted(_REQUIRED_APPROVALS - set(by_role))
        if missing:
            failures.append("missing human approvals: " + ", ".join(missing))
        for role in sorted(_REQUIRED_APPROVALS & set(by_role)):
            approval = by_role[role]
            if not all((approval.reviewer_id.strip(), approval.signed_at.strip(), approval.evidence_ref.strip())):
                failures.append(f"{role} approval is incomplete")
            if approval.report_sha256 != report.sha256:
                failures.append(f"{role} approval is not bound to this report")
        psychiatrist = by_role.get("independentPsychiatrist")
        safety_officer = by_role.get("clinicalSafetyOfficer")
        if psychiatrist and not psychiatrist.independent:
            failures.append("psychiatrist review is not independent")
        if psychiatrist and safety_officer and psychiatrist.reviewer_id == safety_officer.reviewer_id:
            failures.append("psychiatrist reviewer and Clinical Safety Officer must be distinct")
        return ReleaseDecision(not failures, tuple(dict.fromkeys(failures)))


def _unique(items: Iterable[Any], key: Any, label: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for item in items:
        identifier = key(item)
        if identifier in result:
            raise ValueError(f"duplicate {label} identifier: {identifier}")
        result[identifier] = item
    return result
