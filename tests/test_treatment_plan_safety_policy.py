import copy
import json
import re
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
ADR = ROOT / "context/architecture-decisions/0008-treatment-plan-safety-policy.md"
POLICY_PATH = ROOT / "contracts/treatment-plan-safety-policy-v1.json"
SCHEMA_PATH = ROOT / "contracts/treatment-plan-safety-policy-v1.schema.json"
SCOPE_PATH = ROOT / "contracts/scope-matrix-v1.json"
SCOPE_SCHEMA_PATH = ROOT / "contracts/scope-matrix.schema.json"


class TreatmentPlanSafetyPolicyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.validator = Draft202012Validator(cls.schema)
        cls.gates = {gate["id"]: gate for gate in cls.policy["gateDecisionTable"]}

    def test_adr_schema_and_links(self):
        text = ADR.read_text(encoding="utf-8")
        for field in ("Status", "Date", "Decision owners", "Scope"):
            self.assertRegex(text, rf"(?m)^- {re.escape(field)}: \S+")
        for heading in ("Context", "Decision", "Alternatives", "Consequences", "Verification", "Rollback"):
            self.assertIn(f"## {heading}", text)
        for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
            self.assertNotIn("://", target)
            self.assertTrue((ADR.parent / target).resolve().is_file(), target)

    def test_policy_and_scope_matrix_validate(self):
        self.validator.validate(self.policy)
        scope = json.loads(SCOPE_PATH.read_text(encoding="utf-8"))
        scope_schema = json.loads(SCOPE_SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator(scope_schema).validate(scope)
        self.assertEqual(scope["populationGate"]["supportedPopulations"], [])
        self.assertEqual(self.policy["releaseGate"]["state"], "blocked")

    def test_plan_breadth_and_scheduling_are_bounded(self):
        breadth = self.policy["planBreadth"]
        self.assertEqual(
            breadth["systemGeneratedSections"],
            ["treatment-setting", "pharmacotherapy", "follow-up"],
        )
        self.assertFalse(breadth["nonPharmacologicalScope"]["systemGenerationAllowed"])
        scheduling = self.policy["schedulingPolicy"]
        self.assertEqual(scheduling["ownershipStatus"], "unresolved")
        self.assertIsNone(scheduling["appointmentOwner"])
        self.assertFalse(scheduling["appointmentBookingAllowed"])
        self.assertFalse(scheduling["exactDateTimeRecommendationAllowed"])
        self.assertTrue(scheduling["relativeIntervalRequiresApprovedSource"])

    def test_emergency_behavior_has_no_integration_claim(self):
        emergency = self.policy["emergencyPolicy"]
        self.assertEqual(emergency["classification"], "hard-blocker")
        self.assertFalse(emergency["routineRecommendationRunAllowed"])
        self.assertFalse(emergency["primaryTreatmentPlanAllowed"])
        self.assertFalse(emergency["finalizationAllowed"])
        self.assertFalse(emergency["overrideAllowed"])
        self.assertTrue(emergency["persistentUntilResolved"])
        integration = emergency["emergencyServicesIntegration"]
        self.assertFalse(integration["implemented"])
        self.assertTrue(integration["mustNotImplyDispatchContactOrBooking"])

    def test_missing_conflicting_allergy_and_suicide_scenarios(self):
        expected = {
            "missing-required-data": ("hard-blocker", "blocked", False),
            "conflicting-required-data": ("hard-blocker", "blocked", False),
            "proposed-medication-allergy": ("hard-blocker", "proposed-item-blocked", False),
            "absolute-contraindication": ("hard-blocker", "proposed-item-blocked", False),
            "suicide-risk-substantial-or-imminent": ("hard-blocker", "emergency-blocked", False),
            "suicide-risk-unknown-or-unavailable": ("hard-blocker", "blocked", False),
            "unresolved-medication-identity": ("hard-blocker", "blocked", False),
            "ddi-service-or-knowledge-unavailable": ("hard-blocker", "blocked", False),
        }
        for gate_id, result in expected.items():
            gate = self.gates[gate_id]
            self.assertEqual(
                (gate["classification"], gate["outcome"], gate["overrideAllowed"]),
                result,
                gate_id,
            )
            self.assertTrue(gate["requiredAction"], gate_id)

    def test_high_ddi_override_is_attributable_and_does_not_bypass_hard_gates(self):
        gate = self.gates["high-severity-ddi"]
        self.assertEqual(gate["classification"], "overridable-blocker")
        self.assertEqual(gate["outcome"], "override-required")
        self.assertTrue(gate["overrideAllowed"])
        override = self.policy["highSeverityDdiOverride"]
        self.assertEqual(override["allowedRole"], "psychiatrist")
        self.assertTrue(override["rationaleRequired"])
        self.assertGreaterEqual(override["rationaleMinLength"], 1)
        self.assertGreater(override["rationaleMaxLength"], override["rationaleMinLength"])
        for field in (
            "actorUserIdRequired",
            "recordedAtRequired",
            "originalFindingPreserved",
            "overrideRecordedInPlanProvenance",
            "serverSafetyRevalidationRequired",
            "finalAttestationRequired",
            "otherHardBlockersStillApply",
        ):
            self.assertTrue(override[field], field)

    def test_schema_rejects_emergency_integration_and_hard_gate_override(self):
        changed = copy.deepcopy(self.policy)
        changed["emergencyPolicy"]["emergencyServicesIntegration"]["implemented"] = True
        self.assertTrue(list(self.validator.iter_errors(changed)))

        changed = copy.deepcopy(self.policy)
        changed["gateDecisionTable"][0]["overrideAllowed"] = True
        self.assertTrue(list(self.validator.iter_errors(changed)))


if __name__ == "__main__":
    unittest.main()
