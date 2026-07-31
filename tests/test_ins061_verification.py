import importlib.util
import re
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy"


def tracked_source_files():
    names = subprocess.run(
        ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
    ).stdout.decode().split("\0")
    excluded_parts = {"doc", "node_modules", "graphify-out", ".git", "data", "fixtures"}
    protected_suffixes = {".db", ".sqlite", ".sqlite3", ".log", ".bak", ".xml", ".net"}
    for name in names:
        path = Path(name)
        if not name or excluded_parts.intersection(path.parts) or path.suffix.lower() in protected_suffixes:
            continue
        if path.suffix.lower() in {".py", ".js", ".mjs", ".ts", ".tsx", ".html", ".css", ".json", ".yaml", ".yml", ".conf", ".sh"}:
            yield ROOT / path


class SystemSecurityVerification(unittest.TestCase):
    def test_threat_model_controls_at_public_boundary(self):
        nginx = (DEPLOY / "nginx.conf").read_text(encoding="utf-8")
        proxy = (DEPLOY / "nginx-proxy.conf").read_text(encoding="utf-8")
        compose = (DEPLOY / "compose.yaml").read_text(encoding="utf-8")
        for header in (
            "Content-Security-Policy", "Permissions-Policy", "Referrer-Policy",
            "Strict-Transport-Security", "X-Content-Type-Options", "X-Frame-Options",
        ):
            self.assertIn(f"add_header {header}", nginx)
        self.assertIn("frame-ancestors 'none'", nginx)
        self.assertIn("limit_req_zone", nginx)
        self.assertRegex(nginx, r"location = /api/auth/login \{[\s\S]*limit_req")
        self.assertIn("access_log off", nginx)
        self.assertIn("server_tokens off", nginx)
        self.assertIn("proxy_hide_header Server", proxy)
        self.assertIn("AUTH_SECURE_COOKIE: ${AUTH_SECURE_COOKIE:-true}", compose)
        self.assertIn("ADD_NEW_PATIENT_CSRF_SECURE: ${ADD_NEW_PATIENT_CSRF_SECURE:-true}", compose)
        self.assertIn("DIAGNOSIS_CSRF_SECURE: ${DIAGNOSIS_CSRF_SECURE:-true}", compose)
        self.assertIn("read_only: true", compose)
        self.assertIn("cap_drop: [ALL]", compose)
        self.assertIn("no-new-privileges:true", compose)

    def test_tracked_source_has_no_embedded_private_keys_or_cloud_credentials(self):
        patterns = {
            "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
            "AWS access key": re.compile(r"AKIA[0-9A-Z]{16}"),
            "GitHub token": re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"),
            "credentialed URL": re.compile(r"https?://[^\s/:]+:[^\s/@]+@"),
        }
        findings = []
        for path in tracked_source_files():
            text = path.read_text(encoding="utf-8", errors="ignore")
            for label, pattern in patterns.items():
                if pattern.search(text):
                    findings.append(f"{path.relative_to(ROOT)}: {label}")
        self.assertEqual([], findings)

    def test_no_runtime_phi_artifacts_are_tracked(self):
        names = subprocess.run(
            ["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True
        ).stdout.decode().split("\0")
        forbidden = [
            name for name in names
            if name and Path(name).suffix.lower() in {".db", ".sqlite", ".sqlite3", ".log", ".bak"}
        ]
        self.assertEqual([], forbidden)


class AccessibilityVerification(unittest.TestCase):
    def test_all_clinical_surfaces_honor_reduced_motion_and_focus(self):
        styles = (
            "Modules/Auth/static/index.html",
            "Modules/Dashboard-1.2.0/styles.css",
            "Modules/Add-New-Patient-1.1.0/styles.css",
            "Modules/Diagnosis-1.2.0/diagnosis/static/index.html",
            "Modules/Severity-1.1.0/public/index.html",
            "Modules/Medical-History-1.0.0/public/styles.css",
            "Modules/DDI-Checker-1.2.0/src/styles.css",
            "Modules/Suicide-Risk-1.0.0/public/styles.css",
            "Modules/Treatment-Plan/frontend/src/styles.css",
        )
        for name in styles:
            text = (ROOT / name).read_text(encoding="utf-8")
            with self.subTest(path=name):
                self.assertIn("prefers-reduced-motion", text)
                self.assertTrue(
                    ":focus-visible" in text or "focus:ring-" in text,
                    f"{name} has no visible focus treatment",
                )


class DependencyChaosVerification(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("insight_readiness", DEPLOY / "readiness.py")
        cls.readiness = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.readiness)
        import json
        cls.policy = json.loads((DEPLOY / "runtime-policy.json").read_text(encoding="utf-8"))

    def test_each_required_dependency_failure_is_named_and_fails_closed(self):
        for failed in self.policy["modules"]:
            def probe(url, _timeout, failed_port=failed["port"]):
                return f":{failed_port}/" not in url

            with self.subTest(module=failed["id"]):
                status, payload = self.readiness.aggregate(self.policy, probe)
                self.assertEqual(503, status)
                self.assertEqual([failed["id"]], payload["unavailableModules"])
                self.assertNotIn("127.0.0.1", repr(payload))


if __name__ == "__main__":
    unittest.main()
