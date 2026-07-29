import copy
import json
import re
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
ADR = ROOT / "context/architecture-decisions/0007-knowledge-authority-gates.md"
MANIFEST_PATH = ROOT / "contracts/knowledge-source-manifest-v1.json"
SCHEMA_PATH = ROOT / "contracts/knowledge-source-manifest-v1.schema.json"
DOMAINS = {
    "formulary",
    "medication-dosing",
    "medication-contraindications",
    "medication-monitoring",
    "diagnosis-terminology",
    "medication-terminology",
}


class KnowledgeSourceManifestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.validator = Draft202012Validator(cls.schema)

    def test_adr_schema_and_links(self):
        text = ADR.read_text(encoding="utf-8")
        for field in ("Status", "Date", "Decision owners", "Scope"):
            self.assertRegex(text, rf"(?m)^- {re.escape(field)}: \S+")
        for heading in ("Context", "Decision", "Alternatives", "Consequences", "Verification", "Rollback"):
            self.assertIn(f"## {heading}", text)
        for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
            self.assertNotIn("://", target)
            self.assertTrue((ADR.parent / target).resolve().is_file(), target)

    def test_manifest_matches_source_manifest_schema(self):
        self.validator.validate(self.manifest)
        self.assertEqual(self.manifest["contractId"], "insight.knowledge-source-manifest")
        self.assertEqual(self.manifest["schemaVersion"], "1.0.0")
        self.assertEqual(self.manifest["scope"], "INS-009")
        self.assertEqual({source["domain"] for source in self.manifest["sources"]}, DOMAINS)

    def test_unresolved_authorities_and_cadence_fail_closed(self):
        for source in self.manifest["sources"]:
            self.assertEqual(source["authorityStatus"], "unresolved", source["domain"])
            self.assertFalse(source["allowedClinicalUse"], source["domain"])
            self.assertIsNone(source["authorityName"], source["domain"])
            self.assertIsNone(source["sourceVersion"], source["domain"])
        cadence = self.manifest["updateCadence"]
        self.assertEqual(cadence["status"], "unresolved")
        self.assertFalse(cadence["allowedClinicalUse"])
        self.assertEqual(self.manifest["releaseGate"]["state"], "blocked")

    def test_incomplete_approval_metadata_is_rejected(self):
        changed = copy.deepcopy(self.manifest)
        changed["sources"][0]["authorityStatus"] = "approved"
        errors = list(self.validator.iter_errors(changed))
        self.assertTrue(errors)

    def test_blocked_case_preserves_values_and_uncertainty(self):
        blocked = self.manifest["observableBlockedCase"]
        self.assertEqual(blocked["state"], "knowledge-authority-blocked")
        self.assertEqual(blocked["code"], "KNOWLEDGE_AUTHORITY_UNRESOLVED")
        self.assertTrue(blocked["preserveOriginalClinicianValues"])
        self.assertTrue(blocked["displayUncertainty"])
        self.assertFalse(blocked["authoritativeClinicalClaimAllowed"])


if __name__ == "__main__":
    unittest.main()
