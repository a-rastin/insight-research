from __future__ import annotations

import unittest

from bn_manager_backend.model_registry import MODEL_REGISTRY, read_registry_model, read_registry_schema
from clinical_graph_models import XmlBifCompileError, compile_xmlbif, validate_model
from clinical_graph_models.tables import expected_probability_value_count


class XmlBifCompilerTests(unittest.TestCase):
    def test_compiles_and_semantically_validates_all_registered_xml_files(self) -> None:
        self.assertEqual(len(MODEL_REGISTRY), 4)
        for entry in MODEL_REGISTRY:
            with self.subTest(stable_id=entry.stable_id):
                _, text = read_registry_model(entry.stable_id)
                model = compile_xmlbif(text, schema_text=read_registry_schema())

                self.assertIn(entry.target_node, model.node_map())
                self.assertEqual(len(model.nodes), len(model.potentials))
                errors = [message for message in validate_model(model) if message.severity == "error"]
                self.assertEqual(errors, [])

    def test_compact_conditional_rows_are_broadcast_to_all_parent_combinations(self) -> None:
        expected_broadcasts = {
            "bnm.treatment-setting": {
                "inpatient_care_priority",
                "inpatient_service_priority",
                "less_restrictive_care_priority",
                "management_recommendation",
            },
            "bnm.involuntary-treatment-considerations": {
                "immediate_treatment_path",
                "management_recommendation",
            },
        }
        for stable_id, expected_children in expected_broadcasts.items():
            with self.subTest(stable_id=stable_id):
                _, text = read_registry_model(stable_id)
                model = compile_xmlbif(text, schema_text=read_registry_schema())
                broadcast = {
                    potential.child
                    for potential in model.potentials
                    if potential.attributes.get("table_broadcast")
                }
                self.assertEqual(broadcast, expected_children)
                for potential in model.potentials:
                    child = model.node_map()[potential.child]
                    self.assertEqual(
                        len(potential.data),
                        expected_probability_value_count(model, child, potential.parents),
                    )

    def test_full_conditional_tables_are_not_rewritten(self) -> None:
        _, text = read_registry_model("bnm.pharmacotherapy")
        model = compile_xmlbif(text, schema_text=read_registry_schema())
        target = model.potential_map()["management_recommendation"]

        self.assertNotIn("table_broadcast", target.attributes)
        self.assertEqual(len(target.data), 320)

    def test_malformed_xml_returns_structured_error_messages(self) -> None:
        with self.assertRaises(XmlBifCompileError) as raised:
            compile_xmlbif("<BIF><NETWORK></BIF>", schema_text=read_registry_schema())

        details = raised.exception.details()
        self.assertIn("XML parsing failed", str(raised.exception))
        self.assertEqual(details["messages"][0]["severity"], "error")
        self.assertIn("line:", details["messages"][0]["path"])

    def test_xsd_validation_rejects_missing_version_and_single_outcome(self) -> None:
        invalid = """<?xml version="1.0" encoding="utf-8"?>
<BIF>
  <NETWORK>
    <NAME>Invalid</NAME>
    <VARIABLE TYPE="nature"><NAME>A</NAME><OUTCOME>Yes</OUTCOME></VARIABLE>
    <DEFINITION><FOR>A</FOR><TABLE>1</TABLE></DEFINITION>
  </NETWORK>
</BIF>
"""
        with self.assertRaises(XmlBifCompileError) as raised:
            compile_xmlbif(invalid, schema_text=read_registry_schema())

        self.assertIn("XSD validation failed", str(raised.exception))
        self.assertTrue(raised.exception.details()["messages"][0]["message"])

    def test_compiler_rejects_multiple_networks_even_when_schema_allows_them(self) -> None:
        _, text = read_registry_model("bnm.clozapine-suicide-risk")
        second = text.replace("<NETWORK>", "<NETWORK>", 1)
        network = second[second.index("<NETWORK>") : second.index("</NETWORK>") + len("</NETWORK>")]
        multi = second.replace("</BIF>", network + "\n</BIF>")

        with self.assertRaises(XmlBifCompileError) as raised:
            compile_xmlbif(multi, schema_text=read_registry_schema())

        self.assertIn("element count", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
