from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping


MAPPING_VERSION = "2.0.0"
REQUIRED_EVIDENCE = (
    "schizophrenia_diagnostic_context",
    "candidate_specific_hard_contraindication",
    "prior_antipsychotic_experience",
    "patient_preference_and_acceptability",
    "side_effect_and_physical_health_fit",
    "interaction_and_pharmacokinetic_fit",
    "formulation_fit",
)
EVIDENCE_STATES = {
    "schizophrenia_diagnostic_context": frozenset(
        {"schizophrenia_confirmed", "diagnosis_not_confirmed", "unknown"}
    ),
    "candidate_specific_hard_contraindication": frozenset({"present", "absent", "unknown"}),
    "prior_antipsychotic_experience": frozenset(
        {"effective_and_tolerable", "ineffective_or_intolerable", "no_prior_trial", "unknown"}
    ),
    "patient_preference_and_acceptability": frozenset(
        {"accepts_candidate", "prefers_alternative", "declines_antipsychotic", "unknown"}
    ),
    "side_effect_and_physical_health_fit": frozenset({"favorable", "concerning", "unknown"}),
    "interaction_and_pharmacokinetic_fit": frozenset({"favorable", "concerning", "unknown"}),
    "formulation_fit": frozenset(
        {"acceptable_formulation_available", "formulation_mismatch", "unknown"}
    ),
}


@dataclass(frozen=True, slots=True)
class CandidateGateResult:
    candidate_id: str
    disposition: str
    reason_code: str
    mapping_version: str
    review_signals: tuple[str, ...]


def evaluate_candidate_gates(candidate_id: str, evidence: Mapping[str, str]) -> CandidateGateResult:
    """Evaluate only source-backed gates for one candidate; never rank candidates."""
    if not isinstance(candidate_id, str) or not candidate_id.strip():
        raise ValueError("candidate_id is required")
    unknown_nodes = sorted(set(evidence) - set(REQUIRED_EVIDENCE))
    if unknown_nodes:
        raise ValueError("unsupported evidence nodes: " + ", ".join(unknown_nodes))
    invalid = sorted(
        node for node, state in evidence.items() if state not in EVIDENCE_STATES[node]
    )
    if invalid:
        raise ValueError("unsupported evidence states for: " + ", ".join(invalid))

    missing = tuple(node for node in REQUIRED_EVIDENCE if node not in evidence)
    if evidence.get("candidate_specific_hard_contraindication") == "present":
        return CandidateGateResult(
            candidate_id.strip(), "excluded", "candidate-absolute-contraindication", MAPPING_VERSION, ()
        )
    if evidence.get("schizophrenia_diagnostic_context") == "diagnosis_not_confirmed":
        return CandidateGateResult(
            candidate_id.strip(), "blocked", "diagnosis-not-confirmed", MAPPING_VERSION, ()
        )
    unknown = tuple(node for node in REQUIRED_EVIDENCE if evidence.get(node) == "unknown")
    if missing or unknown:
        signals = tuple(f"missing:{node}" for node in missing) + tuple(
            f"unknown:{node}" for node in unknown
        )
        return CandidateGateResult(
            candidate_id.strip(), "blocked", "required-information-unavailable", MAPPING_VERSION, signals
        )

    review_signals = tuple(
        f"{node}:{evidence[node]}"
        for node in REQUIRED_EVIDENCE[2:]
        if evidence[node]
        not in {"effective_and_tolerable", "accepts_candidate", "favorable", "acceptable_formulation_available"}
    )
    return CandidateGateResult(
        candidate_id.strip(),
        "eligible-for-clinician-comparison",
        "hard-gates-cleared",
        MAPPING_VERSION,
        review_signals,
    )
