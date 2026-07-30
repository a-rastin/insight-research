"""Fail-closed TP-21 clinical validation and safety-case gate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parents[1]))

from treatment_plan.clinical_validation import (
    Approval,
    CaseKind,
    CaseObservation,
    ClinicalCase,
    ClinicalSafetyCase,
    Hazard,
    Mitigation,
    ValidationProtocol,
)


ROOT = Path(__file__).parents[1]
DEFAULT_DIR = ROOT / "governance" / "clinical-validation"


def evaluate_payloads(cases_payload: dict[str, Any], observations_payload: dict[str, Any], hazard_payload: dict[str, Any], approvals_payload: dict[str, Any]):
    raw_protocol = cases_payload.get("protocol") or {}
    protocol = ValidationProtocol(
        evidence_ref=str(raw_protocol.get("evidenceRef") or ""),
        max_unsafe_omission_rate=float(raw_protocol["maxUnsafeOmissionRate"]),
        max_unsafe_commission_rate=float(raw_protocol["maxUnsafeCommissionRate"]),
        min_concordance=float(raw_protocol["minConcordance"]),
        max_alerts_per_case=float(raw_protocol["maxAlertsPerCase"]),
        min_task_completion_rate=float(raw_protocol["minTaskCompletionRate"]),
        max_use_error_rate=float(raw_protocol["maxUseErrorRate"]),
        max_brier_score=(float(raw_protocol["maxBrierScore"]) if raw_protocol.get("maxBrierScore") is not None else None),
    )
    cases = [
        ClinicalCase(
            case_id=item["caseId"], kind=CaseKind(item["kind"]), author_role=item["authorRole"],
            author_evidence_ref=item["authorEvidenceRef"],
            expected_actions=frozenset(item.get("expectedActions", [])),
            prohibited_actions=frozenset(item.get("prohibitedActions", [])),
            expected_unresolved=frozenset(item.get("expectedUnresolved", [])),
            subgroup=item.get("subgroup"), expected_override=item.get("expectedOverride"),
            calibration_outcomes=tuple((entry["label"], bool(entry["outcome"])) for entry in item.get("calibrationOutcomes", [])),
        )
        for item in cases_payload.get("cases", [])
    ]
    observations = [
        CaseObservation(
            case_id=item["caseId"], actions=frozenset(item.get("actions", [])),
            unresolved=frozenset(item.get("unresolved", [])), alerts=tuple(item.get("alerts", [])),
            task_completed=bool(item.get("taskCompleted", False)), use_errors=int(item.get("useErrors", 0)),
            completion_seconds=item.get("completionSeconds"), override_used=item.get("overrideUsed"),
            override_authorized=item.get("overrideAuthorized"),
            probabilities=tuple((entry["label"], float(entry["probability"])) for entry in item.get("probabilities", [])),
        )
        for item in observations_payload.get("observations", [])
    ]
    hazards = [
        Hazard(
            hazard_id=item["hazardId"], unsafe_condition=item["unsafeCondition"],
            severity=item["severity"], status=item["status"],
            mitigations=tuple(
                Mitigation(entry["mitigationId"], entry["description"], tuple(entry.get("testRefs", [])))
                for entry in item.get("mitigations", [])
            ),
        )
        for item in hazard_payload.get("hazards", [])
    ]
    approvals = [
        Approval(
            role=item["role"], reviewer_id=item["reviewerId"], independent=bool(item.get("independent", False)),
            signed_at=item["signedAt"], evidence_ref=item["evidenceRef"], report_sha256=item["reportSha256"],
        )
        for item in approvals_payload.get("approvals", [])
    ]
    safety_case = ClinicalSafetyCase()
    report = safety_case.evaluate(protocol, cases, observations, hazards)
    return report, safety_case.release_decision(report, approvals)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    try:
        payloads = [
            json.loads((args.evidence_dir / name).read_text(encoding="utf-8"))
            for name in ("cases.v1.json", "observations.v1.json", "hazard-log.v1.json", "approvals.v1.json")
        ]
        report, decision = evaluate_payloads(*payloads)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        print("TP-21 CLINICAL SAFETY GATE: BLOCKED")
        print(f"- invalid or incomplete controlled evidence: {exc}")
        return 1
    if args.as_json:
        print(json.dumps({**report.canonical_payload(), "reportSha256": report.sha256, "approved": decision.approved, "releaseFailures": list(decision.failures)}, indent=2))
    else:
        print("TP-21 CLINICAL SAFETY GATE: " + ("PASSED" if decision.approved else "BLOCKED"))
        print(f"- report sha256: {report.sha256}")
        for failure in decision.failures:
            print(f"- {failure}")
    return 0 if decision.approved else 1


if __name__ == "__main__":
    raise SystemExit(main())



