import os
import sqlite3
from contextlib import closing
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.verify_deployment import SECURITY_HEADERS, hardened_run_command
from treatment_plan.config import ConfigurationError, Settings
from treatment_plan.deployment import migration_gate, settings_from_environment


ROOT = Path(__file__).parents[1]


class TP22DeploymentTests(unittest.TestCase):
    def test_migration_gate_applies_complete_ordered_schema_and_rejects_drift(self):
        with tempfile.TemporaryDirectory() as directory:
            database = Path(directory) / "runtime.db"
            settings = Settings(environment="test", database_path=database)
            self.assertTrue(migration_gate(settings))
            self.assertEqual((), migration_gate(settings))
            with closing(sqlite3.connect(database)) as connection:
                connection.execute("INSERT INTO schema_migrations(version) VALUES ('9999_unexpected.sql')")
                connection.commit()
            with self.assertRaises(RuntimeError):
                migration_gate(settings)

    def test_secret_file_mount_is_supported_without_allowing_ambiguous_sources(self):
        with tempfile.TemporaryDirectory() as directory:
            secret = Path(directory) / "auth-url"
            secret.write_text("https://authentication.internal/session", encoding="utf-8")
            environment = {
                "TP_ENV": "production",
                "TP_AUTHENTICATION_SESSION_URL_FILE": str(secret),
                "TP_TRUSTED_INTERNAL_ORIGINS": "https://authentication.internal",
            }
            with patch.dict(os.environ, environment, clear=True):
                self.assertEqual("https://authentication.internal/session", settings_from_environment().authentication_session_url)
            environment["TP_AUTHENTICATION_SESSION_URL"] = "https://authentication.internal/other"
            with patch.dict(os.environ, environment, clear=True), self.assertRaises(ConfigurationError):
                settings_from_environment()

    def test_production_allows_only_loopback_http_internal_origin(self):
        environment = {
            "TP_ENV": "production",
            "TP_TRUSTED_INTERNAL_ORIGINS": "http://127.0.0.1:8101",
            "TP_AUTHENTICATION_SESSION_URL": "http://127.0.0.1:8101/api/auth/v2/session",
        }
        with patch.dict(os.environ, environment, clear=True):
            self.assertEqual(environment["TP_AUTHENTICATION_SESSION_URL"], Settings.from_env().authentication_session_url)
        environment["TP_TRUSTED_INTERNAL_ORIGINS"] = "http://authentication.internal:8101"
        environment["TP_AUTHENTICATION_SESSION_URL"] = "http://authentication.internal:8101/api/auth/v2/session"
        with patch.dict(os.environ, environment, clear=True), self.assertRaises(ConfigurationError):
            Settings.from_env()

    def test_release_packaging_is_non_root_pinned_loopback_and_resource_bounded(self):
        dockerfile = (ROOT / "Dockerfile.release").read_text(encoding="utf-8")
        requirements = (ROOT / "requirements.lock").read_text(encoding="utf-8")
        compose = (ROOT / "compose.release.yaml").read_text(encoding="utf-8")
        self.assertIn("USER 10001:10001", dockerfile)
        self.assertIn("npm ci", dockerfile)
        self.assertNotIn(">=", requirements)
        self.assertTrue(all("==" in line for line in requirements.splitlines() if line.strip()))
        for required in ("127.0.0.1:", "read_only: true", "cap_drop: [ALL]", "mem_limit: 512m", "pids_limit: 256", "sbom: true", '"/tmp:size=32m,mode=1777"'):
            self.assertIn(required, compose)

    def test_vps_assets_keep_systemd_on_container_only_and_nginx_on_tls_routes(self):
        unit = (ROOT / "deployment" / "treatment-plan-container.service").read_text(encoding="utf-8")
        nginx = (ROOT / "deployment" / "nginx-vps.conf").read_text(encoding="utf-8").lower()
        self.assertIn("/usr/bin/docker run", unit)
        self.assertNotIn("uvicorn", unit)
        self.assertIn("127.0.0.1:8000:8000", unit)
        for header in SECURITY_HEADERS:
            self.assertIn(header, nginx)
        self.assertIn("proxy_pass http://127.0.0.1:8000", nginx)

    def test_independent_container_verifier_injects_runtime_hardening(self):
        command = hardened_run_command("image@sha256:digest", "name", "volume", 8123)
        joined = " ".join(command)
        for required in ("--user 10001:10001", "--read-only", "--cap-drop ALL", "no-new-privileges", "--memory 512m", "--pids-limit 256", "127.0.0.1:8123:8000"):
            self.assertIn(required, joined)


if __name__ == "__main__":
    unittest.main()




