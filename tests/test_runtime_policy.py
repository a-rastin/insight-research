import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADR = ROOT / "context/architecture-decisions/0001-runtime-matrix.md"
POLICY = ROOT / "deploy/runtime-policy.json"


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

        self.assertEqual(len(ports), len(set(ports)), "duplicate ports")
        self.assertEqual(len(data_dirs), len(set(data_dirs)), "duplicate data dirs")
        self.assertEqual(policy["readiness"]["policy"], "all-required")
        self.assertTrue(all(module["required"] for module in modules))


if __name__ == "__main__":
    unittest.main()
