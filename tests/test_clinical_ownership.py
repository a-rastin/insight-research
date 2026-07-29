import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADR = ROOT / "context/architecture-decisions/0003-follow-up-risk-ownership.md"
CONTRACT = ROOT / "contracts/clinical-ownership-v1.json"


class ClinicalOwnershipContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.contract = json.loads(CONTRACT.read_text(encoding="utf-8"))

    def test_adr_schema_and_links(self):
        text = ADR.read_text(encoding="utf-8")
        for field in ("Status", "Date", "Decision owners", "Scope"):
            self.assertRegex(text, rf"(?m)^- {re.escape(field)}: \S+")
        for heading in ("Context", "Decision", "Alternatives", "Consequences", "Verification", "Rollback"):
            self.assertIn(f"## {heading}", text)
        for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
            self.assertNotIn("://", target)
            self.assertTrue((ADR.parent / target).resolve().is_file(), target)

    def test_every_entity_has_exactly_one_writer(self):
        entities = self.contract["entities"]
        self.assertEqual(len(entities), len({entity["id"] for entity in entities}))
        for entity in entities:
            self.assertEqual(len(entity["writers"]), 1, entity["id"])

    def test_follow_up_and_risk_boundaries(self):
        follow_up = self.contract["flows"]["followUp"]
        self.assertEqual(follow_up["kind"], "orchestration")
        self.assertFalse(follow_up["standaloneOwner"])
        self.assertFalse(follow_up["persistsAuthoritativeRecords"])

        governance = self.contract["instrumentGovernance"]
        self.assertEqual(governance["owner"], "suicide-risk")
        self.assertEqual(governance["sourceLicensingContractStatus"], "unavailable")
        self.assertFalse(governance["questionsDefined"])
        self.assertFalse(governance["scoringDefined"])
        self.assertEqual(set(governance["allowedMissingStates"]), {"unknown", "unavailable"})
        self.assertEqual(governance["missingRiskBehavior"], "block-required-risk-dependent-processing")

    def test_required_examples(self):
        examples = {example["name"]: example for example in self.contract["examples"]}
        self.assertEqual(
            set(examples),
            {"initial-encounter", "follow-up-encounter", "unknown-risk", "unavailable-assessment", "supersession"},
        )
        self.assertEqual(examples["follow-up-encounter"]["deltaWriter"], "add-new-patient")
        for name in ("unknown-risk", "unavailable-assessment"):
            self.assertIsNone(examples[name]["riskScore"])
            self.assertEqual(examples[name]["result"], "blocked")
        self.assertFalse(examples["supersession"]["mutatesPriorEncounter"])
        self.assertFalse(examples["supersession"]["mutatesPriorFinalPlan"])


if __name__ == "__main__":
    unittest.main()
