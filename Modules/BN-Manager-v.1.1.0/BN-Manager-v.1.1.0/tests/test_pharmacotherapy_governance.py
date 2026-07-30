from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path

from bn_manager_backend.model_registry import get_registry_entry, resolve_owned_registry_file
from bn_manager_backend.pharmacotherapy import MAPPING_VERSION, evaluate_candidate_gates
from clinical_graph_models import compile_xmlbif
from bn_manager_backend.model_registry import read_registry_model, read_registry_schema


ROOT = Path(__file__).resolve().parent.parent
POLICY_PATH = ROOT / "bn_manager_backend/model_registry/governance/pharmacotherapy-mapping-v2.json"
GOLDEN_PATH = ROOT / "tests/fixtures/pharmacotherapy-golden-v2.json"


class PharmacotherapyGovernanceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.policy = json.loads(POLICY_PATH.read_text(encoding="utf-8"))

    def test_model_and_mapping_hashes_are_locked(self) -> None:
        entry = get_registry_entry("bnm.pharmacotherapy")
        self.assertIsNotNone(entry)
        payload = entry.payload()
        self.assertEqual(payload["mapping_version"], MAPPING_VERSION)
        self.assertEqual(payload["calibration_status"], "qualitative-uncalibrated")
        self.assertEqual(payload["clinical_recommendation_use"], "excluded")
        self.assertEqual(payload["content_hash"], "sha256:" + self.policy["model"]["sha256"])
        self.assertEqual(
            payload["mapping_hash"],
            "sha256:" + hashlib.sha256(POLICY_PATH.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            resolve_owned_registry_file(payload["mapping_path"]), POLICY_PATH.resolve()
        )

    def test_source_mapping_covers_every_xml_node_once(self) -> None:
        _, text = read_registry_model("bnm.pharmacotherapy")
        model = compile_xmlbif(text, schema_text=read_registry_schema())
        mapped = [item["node"] for item in self.policy["nodeMappings"]]
        self.assertEqual(len(mapped), len(set(mapped)))
        self.assertEqual(set(mapped), set(model.node_map()))
        self.assertFalse(self.policy["candidateEvaluation"]["rankingAllowed"])
        self.assertFalse(self.policy["candidateEvaluation"]["classPreferenceAllowed"])
        self.assertFalse(self.policy["candidateEvaluation"]["automaticSelectionAllowed"])

    def test_uniform_placeholder_cpts_remain_explicitly_uncalibrated(self) -> None:
        _, text = read_registry_model("bnm.pharmacotherapy")
        model = compile_xmlbif(text, schema_text=read_registry_schema())
        for child in (
            "individualized_candidate_priority",
            "shared_decision_and_formulation_priority",
            "management_recommendation",
        ):
            potential = model.potential_map()[child]
            width = len(model.node_map()[child].states)
            rows = [potential.data[index:index + width] for index in range(0, len(potential.data), width)]
            self.assertTrue(all(row == rows[0] for row in rows), child)
        self.assertEqual(self.policy["calibration"]["label"], "qualitative-uncalibrated")
        self.assertEqual(self.policy["calibration"]["clinicalRecommendationUse"], "excluded")

    def test_golden_candidate_gate_cases(self) -> None:
        fixture = json.loads(GOLDEN_PATH.read_text(encoding="utf-8"))
        self.assertEqual(fixture["mappingVersion"], MAPPING_VERSION)
        for case in fixture["cases"]:
            with self.subTest(case=case["id"]):
                result = evaluate_candidate_gates(case["candidateId"], case["evidence"])
                self.assertEqual(result.disposition, case["disposition"])
                self.assertEqual(result.reason_code, case["reasonCode"])
                self.assertEqual(list(result.review_signals), case["reviewSignals"])

    def test_candidate_gate_input_is_strict(self) -> None:
        with self.assertRaisesRegex(ValueError, "candidate_id"):
            evaluate_candidate_gates("", {})
        with self.assertRaisesRegex(ValueError, "unsupported evidence nodes"):
            evaluate_candidate_gates("candidate-a", {"not_a_node": "unknown"})
        with self.assertRaisesRegex(ValueError, "unsupported evidence states"):
            evaluate_candidate_gates(
                "candidate-a", {"schizophrenia_diagnostic_context": "assumed_confirmed"}
            )


if __name__ == "__main__":
    unittest.main()
