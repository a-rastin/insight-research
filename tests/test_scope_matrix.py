import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADR = ROOT / "context/architecture-decisions/0006-treatment-plan-scope-gates.md"
MATRIX_PATH = ROOT / "contracts/scope-matrix-v1.json"
SCHEMA_PATH = ROOT / "contracts/scope-matrix.schema.json"
FIXTURES_PATH = ROOT / "tests/fixtures/scope-matrix-negative.json"


def evaluate(matrix, diagnosis_state, population_state):
    reasons = []
    required = matrix["diagnosisGate"]["requiredState"]
    if diagnosis_state != required:
        reasons.append(matrix["reasonCodes"][diagnosis_state])
    reasons.append(matrix["reasonCodes"][population_state])
    return matrix["observableUnsupportedCase"]["state"], reasons


class ScopeMatrixContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matrix = json.loads(MATRIX_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.fixtures = json.loads(FIXTURES_PATH.read_text(encoding="utf-8"))

    def test_adr_schema_and_links(self):
        text = ADR.read_text(encoding="utf-8")
        for field in ("Status", "Date", "Decision owners", "Scope"):
            self.assertRegex(text, rf"(?m)^- {re.escape(field)}: \S+")
        for heading in ("Context", "Decision", "Alternatives", "Consequences", "Verification", "Rollback"):
            self.assertIn(f"## {heading}", text)
        for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
            self.assertNotIn("://", target)
            self.assertTrue((ADR.parent / target).resolve().is_file(), target)

    def test_matrix_matches_versioned_schema_contract(self):
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        for field in self.schema["required"]:
            self.assertIn(field, self.matrix)
        self.assertEqual(self.matrix["contractId"], "insight.scope-matrix")
        self.assertEqual(self.matrix["schemaVersion"], "1.0.0")
        self.assertEqual(self.matrix["scope"], "INS-008")

    def test_intended_use_preserves_psychiatrist_authority(self):
        intended_use = self.matrix["intendedUse"]
        self.assertEqual(intended_use["releaseStatus"], "research-only")
        self.assertFalse(intended_use["clinicalDeploymentAllowed"])
        self.assertTrue(intended_use["advisoryOnly"])
        self.assertTrue(intended_use["psychiatristFinalAuthorityRequired"])
        self.assertFalse(intended_use["autonomousDiagnosisAllowed"])
        self.assertFalse(intended_use["prescribingOrOrderingAllowed"])

    def test_scope_gates_fail_closed(self):
        diagnosis = self.matrix["diagnosisGate"]
        self.assertEqual(diagnosis["supportedPathway"], "psychiatrist-confirmed-schizophrenia")
        self.assertEqual(diagnosis["requiredState"], "confirmed-schizophrenia")
        population = self.matrix["populationGate"]
        self.assertEqual(population["approvalStatus"], "unresolved")
        self.assertEqual(population["supportedPopulations"], [])
        self.assertFalse(population["inferenceAllowed"])
        unsupported = self.matrix["observableUnsupportedCase"]
        self.assertEqual(unsupported["code"], "TP_SCOPE_UNSUPPORTED")
        self.assertFalse(unsupported["recommendationRunCreated"])
        self.assertFalse(unsupported["primaryTreatmentPlanCreated"])

    def test_negative_diagnosis_and_population_fixtures(self):
        self.assertEqual(
            {fixture["id"] for fixture in self.fixtures},
            {"excluded-diagnosis", "unknown-diagnosis", "excluded-population", "unknown-population"},
        )
        for fixture in self.fixtures:
            state, reasons = evaluate(
                self.matrix,
                fixture["diagnosisState"],
                fixture["populationState"],
            )
            self.assertEqual(state, fixture["expectedState"], fixture["id"])
            self.assertEqual(reasons, fixture["expectedReasonCodes"], fixture["id"])


if __name__ == "__main__":
    unittest.main()
