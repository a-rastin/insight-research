"""Shared diagnosis assessment evaluation and compatibility translation."""
from __future__ import annotations

from .criteria import evaluate

SCHEMA_VERSION = "2.0.0"
RULE_VERSION = "diagnosis-rules-1.0.0"


def evaluate_checked(checked: list[str]) -> dict:
    """Return the one authoritative criteria evaluation representation."""
    return evaluate(checked).to_dict()


def legacy_decision_to_v2(decision: str | None) -> str | None:
    return "bypass" if decision == "definite" else decision


def v2_decision_to_legacy(decision: str | None) -> str | None:
    return "definite" if decision == "bypass" else decision


def present_assessment(assessment: dict) -> dict:
    """Build the versioned assessment snapshot persisted in the audit log."""
    result = evaluate_checked(assessment["checkedCriteria"])
    status = "decided" if assessment["clinicianDecision"] else (
        "in-progress" if assessment["checkedCriteria"] else "initialized"
    )
    return {
        "assessmentId": assessment["assessmentId"],
        "patientId": assessment["patientId"],
        "encounterId": assessment["encounterId"],
        "checkedCriteria": assessment["checkedCriteria"],
        "evaluation": {
            "met": result["met"],
            "aCount": result["a_count"],
            "coreCount": result["core_count"],
            "failures": result["failures"],
            "reason": result["reason"],
            "checkedCriteria": result["checked"],
            "ruleVersion": RULE_VERSION,
        },
        "clinicianDecision": assessment["clinicianDecision"],
        "ruleVersion": RULE_VERSION,
        "schemaVersion": SCHEMA_VERSION,
        "status": status,
        "resourceVersion": assessment["resourceVersion"],
        "createdAt": assessment["createdAt"],
        "updatedAt": assessment["updatedAt"],
        "provenance": {
            "sourceModule": "diagnosis",
            "createdByUserId": assessment["createdByUserId"],
            "lastUpdatedByUserId": assessment["lastUpdatedByUserId"],
        },
    }


__all__ = [
    "SCHEMA_VERSION",
    "RULE_VERSION",
    "evaluate_checked",
    "legacy_decision_to_v2",
    "v2_decision_to_legacy",
    "present_assessment",
]
