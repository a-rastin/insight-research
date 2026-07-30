import unittest

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


def protocol() -> ValidationProtocol:
    return ValidationProtocol("controlled://protocol/TP-21/v1", 0, 0, 1, 2, 1, 0, 0.1)


def cases() -> list[ClinicalCase]:
    result = []
    for index, kind in enumerate(CaseKind, start=1):
        result.append(
            ClinicalCase(
                f"CASE-TP-{index:03d}", kind, "psychiatrist", f"controlled://case/{index}",
                expected_actions=frozenset({f"action-{index}"}),
                prohibited_actions=frozenset({f"unsafe-{index}"}),
                subgroup="approved-subgroup" if kind is CaseKind.SUBGROUP else None,
                expected_override=True if kind is CaseKind.OVERRIDE_WORKFLOW else None,
                calibration_outcomes=((f"outcome-{index}", True),),
            )
        )
    return result


def observations(source: list[ClinicalCase]) -> list[CaseObservation]:
    return [
        CaseObservation(
            item.case_id, item.expected_actions, frozenset(), ("review",), True, 0, 20,
            override_used=(True if item.kind is CaseKind.OVERRIDE_WORKFLOW else None),
            override_authorized=(True if item.kind is CaseKind.OVERRIDE_WORKFLOW else None),
            probabilities=((item.calibration_outcomes[0][0], 0.9),),
        )
        for item in source
    ]


def hazards(status: str = "mitigated") -> list[Hazard]:
    return [Hazard("HZ-TEST-001", "unsafe output", "critical", status, (Mitigation("MIT-TEST-001", "gate output", ("tests/test_tp21_clinical_validation.py",)),))]


class TP21ClinicalValidationTests(unittest.TestCase):
    def test_measures_required_clinical_and_human_factors_metrics(self):
        authored = cases()
        report = ClinicalSafetyCase().evaluate(protocol(), authored, observations(authored), hazards())
        self.assertEqual(0, report.metrics["unsafeOmissionCount"])
        self.assertEqual(0, report.metrics["unsafeCommissionCount"])
        self.assertEqual(1, report.metrics["concordance"])
        self.assertAlmostEqual(0.01, report.metrics["brierScore"])
        self.assertEqual(1, report.metrics["alertsPerCase"])
        self.assertEqual(1, report.metrics["taskCompletionRate"])
        self.assertEqual(20, report.metrics["medianCompletionSeconds"])
        self.assertEqual((), report.failures)

    def test_unsafe_results_open_hazards_and_incomplete_coverage_block(self):
        authored = cases()[:-1]
        observed = observations(authored)
        first = observed[0]
        observed[0] = CaseObservation(first.case_id, frozenset({"unsafe-1"}), frozenset({"allergy"}), tuple(f"alert-{index}" for index in range(20)), False, 1, 40)
        report = ClinicalSafetyCase().evaluate(protocol(), authored, observed, hazards("open"))
        joined = " ".join(report.failures)
        for expected in ("missing case kinds", "open hazards", "unsafe omission", "unsafe commission", "alert burden", "human-factors"):
            self.assertIn(expected, joined)
        self.assertEqual(1, report.metrics["unresolvedDataCount"])

    def test_release_requires_distinct_external_human_approvals_bound_to_report(self):
        authored = cases()
        safety_case = ClinicalSafetyCase()
        report = safety_case.evaluate(protocol(), authored, observations(authored), hazards())
        blocked = safety_case.release_decision(report, [])
        self.assertFalse(blocked.approved)
        approvals = [
            Approval("independentPsychiatrist", "reviewer-1", True, "2026-07-16T00:00:00Z", "controlled://review/1", report.sha256),
            Approval("clinicalSafetyOfficer", "reviewer-2", False, "2026-07-16T00:00:00Z", "controlled://signoff/1", report.sha256),
        ]
        self.assertTrue(safety_case.release_decision(report, approvals).approved)
        approvals[0] = Approval("independentPsychiatrist", "reviewer-1", True, "2026-07-16T00:00:00Z", "controlled://review/1", "wrong")
        self.assertFalse(safety_case.release_decision(report, approvals).approved)


if __name__ == "__main__":
    unittest.main()


