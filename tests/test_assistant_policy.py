import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADR = ROOT / "context/architecture-decisions/0005-assistant-v1-disabled.md"
CONTRACT = ROOT / "contracts/assistant-policy-v1.json"


class AssistantPolicyContractTest(unittest.TestCase):
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

    def test_provider_and_ui_are_fail_closed(self):
        assistant = self.contract["assistant"]
        self.assertEqual(assistant["v1Scope"], "rejected")
        self.assertFalse(assistant["enabled"])
        self.assertIsNone(assistant["provider"])
        self.assertEqual(assistant["unsupportedOrIncompletePolicyResult"], "disabled")
        self.assertEqual(self.contract["ui"]["state"], "disabled-provider")
        self.assertFalse(self.contract["ui"]["promptControlVisible"])

    def test_identifiers_are_omitted_then_scrubbed(self):
        boundary = self.contract["providerBoundary"]
        self.assertFalse(boundary["transmissionAllowed"])
        self.assertTrue(boundary["structuralIdentifierOmissionRequiredBeforeScrubbing"])
        self.assertTrue(boundary["defenseInDepthScrubbingRequired"])
        corpus = self.contract["syntheticRedactionCorpus"]
        self.assertEqual({item["class"] for item in corpus}, set(boundary["forbiddenIdentifierClasses"]))
        for item in corpus:
            self.assertNotEqual(item["input"], item["expected"])
            self.assertEqual(item["expected"], "[REDACTED]")

    def test_no_context_tools_or_mutations(self):
        self.assertEqual(self.contract["pageContext"]["allowlist"], [])
        tools = self.contract["tools"]
        self.assertEqual(tools["allowlist"], [])
        self.assertEqual(tools["default"], "deny")
        self.assertEqual(
            set(tools["forbiddenCapabilities"]),
            {"create", "update", "delete", "submit", "sign", "approve", "finalize"},
        )

    def test_no_retention_access_backup_or_workflow_dependency(self):
        conversation = self.contract["conversation"]
        self.assertFalse(conversation["persistenceEnabled"])
        self.assertEqual(conversation["retention"], "none-no-storage")
        self.assertEqual(conversation["authorizedRoles"], [])
        self.assertFalse(conversation["includedInBackup"])
        self.assertFalse(self.contract["providerUsePolicy"]["approved"])
        failure = self.contract["failurePolicy"]
        self.assertFalse(failure["clinicalWorkflowBlocking"])
        self.assertFalse(failure["clinicalWorkflowMutationAllowed"])


if __name__ == "__main__":
    unittest.main()
