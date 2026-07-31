"""Fail-closed TP-01 clinical release gate. Uses only the Python standard library."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REQUIRED_ROLES = {"psychiatrist", "clinicalSafetyOfficer", "product", "privacy", "regulatory"}
SCOPE_GATES = {"DG-01", "DG-03", "DG-07"}
POPULATION_CATEGORIES = {"pediatrics", "pregnancy", "older-adults", "renal-impairment", "hepatic-impairment", "emergency-psychiatry"}
RE_REVIEW_TRIGGERS = {"intended-use", "supported-population", "diagnosis-breadth", "knowledge-sources", "deployment-jurisdiction"}


def evaluate(matrix: dict) -> list[str]:
    failures: list[str] = []
    if matrix.get("status") != "approved":
        failures.append("scope matrix is not approved")

    gates = matrix.get("decisionGates", [])
    if len(gates) != 8 or any(g.get("status") != "approved" or not g.get("decision") for g in gates):
        failures.append("all eight decision gates must be approved with decisions")
    target_gates = {gate.get("id"): gate for gate in gates if gate.get("id") in SCOPE_GATES}
    if set(target_gates) != SCOPE_GATES or any(
        not gate.get("decidedBy") or not gate.get("decidedAt") or not gate.get("evidenceRefs")
        for gate in target_gates.values()
    ):
        failures.append("DG-01, DG-03, and DG-07 require attribution and evidence references")

    owners = matrix.get("owners", {})
    missing_owners = sorted(role for role in REQUIRED_ROLES if not owners.get(role))
    if missing_owners:
        failures.append("unnamed accountable owners: " + ", ".join(missing_owners))

    approvals = matrix.get("approvals", [])
    approved_roles = {a.get("role") for a in approvals if a.get("name") and a.get("signedAt") and a.get("signatureRef") and a.get("scopeHash")}
    if REQUIRED_ROLES - approved_roles:
        failures.append("missing valid approvals: " + ", ".join(sorted(REQUIRED_ROLES - approved_roles)))

    intended = matrix.get("intendedUse", {})
    if intended.get("researchOnly") is None or not intended.get("decision") or not intended.get("jurisdictions"):
        failures.append("intended use, research-only decision, and jurisdiction are required")

    scope = matrix.get("clinicalScope", {})
    if not scope.get("supportedDiagnoses") or not scope.get("supportedPopulation"):
        failures.append("supported diagnosis and population are required")
    population_decisions = scope.get("populationDecisions", [])
    if {item.get("category") for item in population_decisions} != POPULATION_CATEGORIES or any(
        item.get("status") == "unresolved" or not item.get("decision") or not item.get("evidenceRefs")
        for item in population_decisions
    ):
        failures.append("all TP-01 population decisions require resolution and evidence")
    if not scope.get("emergencyBehavior"):
        failures.append("emergency behavior is required")

    if not matrix.get("knowledgeAuthority", {}).get("approvedSources"):
        failures.append("at least one approved knowledge source is required")
    if not matrix.get("notSupported"):
        failures.append("explicit not-supported cases are required")

    regulatory = matrix.get("regulatoryAssessment", {})
    if regulatory.get("status") != "completed" or not all(regulatory.get(k) for k in ("classification", "jurisdictionAnalysis", "assessor", "assessedAt", "evidenceRef")):
        failures.append("regulatory assessment is incomplete")
    triggers = regulatory.get("reReviewTriggers", [])
    if {item.get("change") for item in triggers} != RE_REVIEW_TRIGGERS or any(
        item.get("requiredAction") != "regulatory-re-review" for item in triggers
    ):
        failures.append("regulatory re-review triggers are incomplete")

    validation = matrix.get("clinicalValidation", {})
    if validation.get("status") != "completed" or not validation.get("reportRef") or not validation.get("approvedByClinicalSafetyOfficer") or not validation.get("approvedAt"):
        failures.append("clinical validation and Clinical Safety Officer approval are required")
    return failures


def evaluate_scope_case(matrix: dict, diagnosis: str, population: str) -> str | None:
    """Return rejection code; only an approved complete matrix can admit a case."""
    if evaluate(matrix):
        return "scope-unapproved"
    scope = matrix["clinicalScope"]
    if diagnosis not in scope["supportedDiagnoses"]:
        return "unsupported-diagnosis"
    if population not in scope["supportedPopulation"]:
        return "unsupported-population"
    return None


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("matrix", nargs="?", default=str(Path(__file__).parents[1] / "governance" / "scope-matrix.v1.json"))
    args = parser.parse_args()
    data = json.loads(Path(args.matrix).read_text(encoding="utf-8"))
    failures = evaluate(data)
    if failures:
        print("TP-01 RELEASE GATE: BLOCKED")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("TP-01 RELEASE GATE: PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
