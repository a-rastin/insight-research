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
        self.assertEqual(self.manifest["scope"], "INS-009")
        self.assertEqual({source["domain"] for source in self.manifest["sources"]}, DOMAINS)
        self.assertEqual(self.manifest["profile"]["jurisdiction"], "US")
        self.assertFalse(self.manifest["profile"]["clinicalDeploymentAllowed"])

    def test_authorities_and_versions_are_selected(self):
        sources = {source["domain"]: source for source in self.manifest["sources"]}
        self.assertEqual(sources["formulary"]["authorityStatus"], "not-applicable")
        self.assertFalse(sources["formulary"]["allowedResearchUse"])
        for domain in ("medication-dosing", "medication-contraindications", "medication-monitoring"):
            self.assertEqual(sources[domain]["authorityName"], "FDA-approved product labeling indexed by Drugs@FDA")
            self.assertEqual(sources[domain]["pinnedVersion"], "snapshot-2026-07-28")
        self.assertEqual(sources["diagnosis-terminology"]["authorityName"], "ICD-10-CM")
        self.assertEqual(sources["diagnosis-terminology"]["pinnedVersion"], "2026")
        self.assertEqual(sources["medication-terminology"]["authorityName"], "RxNorm Current Prescribable Content Full Monthly Release")
        self.assertEqual(sources["medication-terminology"]["pinnedVersion"], "2026-07-06")

    def test_update_cadence_and_change_gates(self):
        cadence = self.manifest["updateCadence"]
        self.assertEqual(cadence["drugsAtFda"]["checkSchedule"], "weekdays")
        self.assertEqual(cadence["rxNorm"]["checkSchedule"], "weekly")
        self.assertEqual(cadence["icd10cm"]["checkSchedule"], "every-30-days")
        self.assertEqual(cadence["governanceReviewIntervalDays"], 90)
        self.assertTrue(cadence["changeRequiresValidation"])
        self.assertTrue(cadence["changeRequiresClinicalReview"])
        self.assertFalse(self.manifest["authorityPolicy"]["sourceUpdatesAutoActivate"])

    def test_selected_source_without_provenance_is_rejected(self):
        changed = copy.deepcopy(self.manifest)
        changed["sources"][1]["pinnedVersion"] = None
        self.assertTrue(list(self.validator.iter_errors(changed)))

    def test_formulary_claim_cannot_be_enabled(self):
        changed = copy.deepcopy(self.manifest)
        changed["sources"][0]["allowedResearchUse"] = True
        self.assertTrue(list(self.validator.iter_errors(changed)))


if __name__ == "__main__":
    unittest.main()
