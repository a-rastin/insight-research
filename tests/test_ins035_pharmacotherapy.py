import hashlib
import json
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
MODULE = ROOT / "Modules/BN-Manager-v.1.1.0/BN-Manager-v.1.1.0"
POLICY_PATH = MODULE / "bn_manager_backend/model_registry/governance/pharmacotherapy-mapping-v2.json"
SCHEMA_PATH = MODULE / "bn_manager_backend/model_registry/governance/pharmacotherapy-mapping-v2.schema.json"
BN_SCHEMA_PATH = MODULE / "contracts/bn-manager-v3.schema.json"


class Ins035PharmacotherapyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))

    def test_governance_hashes_match_exact_source_and_model_bytes(self):
        source_path = WORKSPACE / self.policy["source"]["path"]
        model_path = MODULE / "bn_manager_backend/model_registry" / self.policy["model"]["path"]
        self.assertEqual(hashlib.sha256(source_path.read_bytes()).hexdigest(), self.policy["source"]["sha256"])
        self.assertEqual(hashlib.sha256(model_path.read_bytes()).hexdigest(), self.policy["model"]["sha256"])

    def test_mapping_validates_against_versioned_schema(self):
        schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        Draft202012Validator(schema).validate(self.policy)

    def test_mapping_covers_exact_xml_nodes_and_preserves_source_line_bounds(self):
        model_path = MODULE / "bn_manager_backend/model_registry" / self.policy["model"]["path"]
        root = ET.fromstring(model_path.read_bytes())
        xml_nodes = {variable.findtext("NAME") for variable in root.findall("./NETWORK/VARIABLE")}
        mappings = self.policy["nodeMappings"]
        self.assertEqual({mapping["node"] for mapping in mappings}, xml_nodes)
        source_line_count = len((WORKSPACE / self.policy["source"]["path"]).read_text(encoding="utf-8").splitlines())
        for mapping in mappings:
            self.assertTrue(mapping["sourceLines"], mapping["node"])
            self.assertTrue(all(1 <= line <= source_line_count for line in mapping["sourceLines"]), mapping["node"])

    def test_uncalibrated_model_is_explicitly_blocked_from_clinical_use(self):
        self.assertEqual(self.policy["calibration"]["label"], "qualitative-uncalibrated")
        self.assertEqual(
            self.policy["calibration"]["clinicalRecommendationUse"],
            "blocked-until-calibrated-and-approved",
        )
        self.assertFalse(self.policy["candidateEvaluation"]["rankingAllowed"])
        self.assertFalse(self.policy["candidateEvaluation"]["automaticSelectionAllowed"])

    def test_v31_contract_requires_candidate_bound_complete_evidence(self):
        schema = json.loads(BN_SCHEMA_PATH.read_text(encoding="utf-8"))
        evidence = {
            "schizophrenia_diagnostic_context": "schizophrenia_confirmed",
            "candidate_specific_hard_contraindication": "absent",
            "prior_antipsychotic_experience": "no_prior_trial",
            "patient_preference_and_acceptability": "accepts_candidate",
            "side_effect_and_physical_health_fit": "favorable",
            "interaction_and_pharmacokinetic_fit": "favorable",
            "formulation_fit": "acceptable_formulation_available",
        }
        request = {
            "stable_id": "bnm.pharmacotherapy",
            "candidate_id": "candidate-a",
            "evidence": evidence,
        }
        full_validator = Draft202012Validator(schema)
        request_validator = full_validator.evolve(schema=schema["$defs"]["evaluationRequest"])
        self.assertEqual(list(request_validator.iter_errors(request)), [])
        self.assertTrue(list(request_validator.iter_errors({"stable_id": "bnm.pharmacotherapy", "evidence": evidence})))
        self.assertTrue(
            list(
                request_validator.iter_errors(
                    {"stable_id": "bnm.treatment-setting", "candidate_id": "candidate-a"}
                )
            )
        )


if __name__ == "__main__":
    unittest.main()
