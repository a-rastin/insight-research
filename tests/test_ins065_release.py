import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy"


class ReleaseModeTests(unittest.TestCase):
    def test_release_policy_is_research_only_and_fail_closed(self):
        policy = json.loads((DEPLOY / "release-policy.json").read_text(encoding="utf-8"))
        self.assertEqual("INS-065", policy["packet"])
        self.assertEqual("research-build", policy["releaseMode"])
        self.assertEqual("blocked", policy["status"])
        self.assertIn("tls-health-and-readiness", policy["requiredGates"])
        self.assertIn("backup-and-restore-verification", policy["requiredGates"])
        self.assertIn("rollback-compatibility", policy["requiredGates"])
        self.assertTrue(any("DDI readiness" in item for item in policy["limitations"]))
        self.assertTrue(any("controlled-clinical" in item for item in policy["limitations"]))

    def test_release_compose_requires_digest_and_keeps_gateway_private(self):
        compose = (DEPLOY / "compose.release.yaml").read_text(encoding="utf-8")
        self.assertIn("${INSIGHT_IMAGE:?set a registry image pinned by sha256 digest}", compose)
        self.assertNotIn("build:", compose)
        self.assertIn('"127.0.0.1:8080:8080"', compose)
        self.assertIn("pull_policy: always", compose)
        self.assertIn("read_only: true", compose)
        self.assertIn("cap_drop: [ALL]", compose)
        self.assertIn("/run/secrets/backup-key:ro", compose)

    def test_host_nginx_terminates_modern_tls(self):
        nginx = (DEPLOY / "nginx-tls.conf.template").read_text(encoding="utf-8")
        self.assertIn("return 308 https://$host$request_uri", nginx)
        self.assertIn("ssl_protocols TLSv1.2 TLSv1.3", nginx)
        self.assertIn("proxy_pass http://127.0.0.1:8080", nginx)
        self.assertIn("proxy_set_header X-Forwarded-Proto https", nginx)
        self.assertNotIn("access_log", nginx)

    def test_release_gate_covers_required_live_rehearsals(self):
        script = (DEPLOY / "release.sh").read_text(encoding="utf-8")
        for evidence in (
            "@sha256:", "deploy/module-tests.sh", "unittest discover -s tests", "/healthz", "/readyz",
            "tests.test_ins058_gateway_e2e", "tests.test_ins059_gateway_e2e",
            "operations.py backup", "operations.py restore", "operations.py rollback",
            "restart insight",
        ):
            self.assertIn(evidence, script)
        self.assertLess(script.index("operations.py rollback"), script.index("up -d"))
        self.assertLess(script.index("/readyz"), script.index("tests.test_ins058_gateway_e2e"))


if __name__ == "__main__":
    unittest.main()
