import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADR = ROOT / "context/architecture-decisions/0001-runtime-matrix.md"
POLICY = ROOT / "deploy/runtime-policy.json"
EXPECTED_MODULE_IDS = {
    "authentication",
    "dashboard",
    "add-new-patient",
    "diagnosis",
    "severity",
    "medical-history",
    "ddi-checker",
    "bn-manager",
    "treatment-plan",
}


class RuntimePolicyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = json.loads(POLICY.read_text(encoding="utf-8"))

    def test_adr_schema_and_links(self):
        text = ADR.read_text(encoding="utf-8")
        for field in ("Status", "Date", "Decision owners", "Scope"):
            self.assertRegex(text, rf"(?m)^- {re.escape(field)}: \S+")
        for heading in (
            "Context", "Decision", "Alternatives", "Platform Paths",
            "Consequences", "Verification", "Rollback",
        ):
            self.assertIn(f"## {heading}", text)
        for target in re.findall(r"\[[^]]+\]\(([^)]+)\)", text):
            self.assertFalse("://" in target, f"ADR link must be relative: {target}")
            self.assertTrue((ADR.parent / target).resolve().is_file(), target)

    def test_deployment_policy(self):
        policy = self.policy
        gateway = policy["gateway"]
        supervisor = policy["supervisor"]
        modules = policy["modules"]

        self.assertTrue(gateway["published"])
        self.assertNotIn(gateway["runAsUser"], (0, "0", "root"))
        self.assertEqual(supervisor["pid"], 1)
        self.assertNotIn(supervisor["runAsUser"], (0, "0", "root"))
        self.assertGreater(supervisor["gracePeriodSeconds"], 0)

        ports = [gateway["port"]]
        data_dirs = []
        module_ids = []
        base_paths = []
        for module in modules:
            self.assertFalse(module["published"], module["id"])
            self.assertEqual(module["host"], "127.0.0.1", module["id"])
            self.assertNotIn(module["runAsUser"], (0, "0", "root"))
            self.assertRegex(module["livenessPath"], r"^/")
            self.assertRegex(module["readinessPath"], r"^/")
            self.assertRegex(module["basePath"], r"^/(?!/)")
            self.assertNotRegex(module["basePath"], r"://|localhost")
            ports.append(module["port"])
            data_dirs.append(module["dataDir"])
            module_ids.append(module["id"])
            base_paths.append(module["basePath"])

        self.assertEqual(set(module_ids), EXPECTED_MODULE_IDS)
        self.assertEqual(len(module_ids), len(set(module_ids)), "duplicate module ids")
        self.assertEqual(len(ports), len(set(ports)), "duplicate ports")
        self.assertEqual(len(data_dirs), len(set(data_dirs)), "duplicate data dirs")
        self.assertEqual(len(base_paths), len(set(base_paths)), "duplicate base paths")
        self.assertEqual(policy["readiness"]["policy"], "all-required")
        self.assertTrue(all(module["required"] for module in modules))


if __name__ == "__main__":
    unittest.main()
