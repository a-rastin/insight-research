import configparser
import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "deploy"
POLICY = json.loads((DEPLOY / "runtime-policy.json").read_text(encoding="utf-8"))


def load_readiness():
    spec = importlib.util.spec_from_file_location("unified_readiness", DEPLOY / "readiness.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class UnifiedImageTests(unittest.TestCase):
    def test_supervisor_matches_policy_and_stops_process_groups(self):
        parser = configparser.ConfigParser(interpolation=None)
        parser.read(DEPLOY / "supervisord.conf")
        programs = {section.removeprefix("program:"): parser[section] for section in parser.sections() if section.startswith("program:")}
        self.assertEqual({module["id"] for module in POLICY["modules"]} | {"readiness", "gateway"}, set(programs))
        for name, program in programs.items():
            self.assertEqual("true", program["stopasgroup"], name)
            self.assertEqual("true", program["killasgroup"], name)
            self.assertEqual("TERM", program["stopsignal"], name)
            self.assertEqual("30", program["stopwaitsecs"], name)
        self.assertIn("PROCESS_STATE_FATAL", parser["eventlistener:failfast"]["events"])

    def test_gateway_exposes_only_8080_and_routes_every_module(self):
        nginx = (DEPLOY / "nginx.conf").read_text(encoding="utf-8")
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        compose = (DEPLOY / "compose.yaml").read_text(encoding="utf-8")
        self.assertEqual(["8080"], [line.split()[1] for line in dockerfile.splitlines() if line.startswith("EXPOSE ")])
        self.assertIn('"8080:8080"', compose)
        for module in POLICY["modules"]:
            self.assertIn(module["basePath"], nginx, module["id"])
            self.assertNotIn(f'EXPOSE {module["port"]}', dockerfile)

        self.assertIn("location = /modules/add-new-patient { return 308 /modules/add-new-patient/; }", nginx)

    def test_image_is_non_root_locked_and_has_distinct_volumes(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        compose = (DEPLOY / "compose.yaml").read_text(encoding="utf-8")
        lock = (DEPLOY / "requirements.lock").read_text(encoding="utf-8")
        self.assertIn("USER 10001:10001", dockerfile)
        self.assertIn("--require-hashes", dockerfile)
        self.assertIn("npm ci", dockerfile)
        self.assertNotIn(">=", lock)
        for module in POLICY["modules"]:
            self.assertIn(f':{module["dataDir"]}', compose, module["id"])

    def test_readiness_reports_only_unavailable_module_ids(self):
        readiness = load_readiness()
        failed_port = POLICY["modules"][2]["port"]

        def probe(url, _timeout):
            return f":{failed_port}/" not in url

        status, payload = readiness.aggregate(POLICY, probe)
        self.assertEqual(503, status)
        self.assertEqual([POLICY["modules"][2]["id"]], payload["unavailableModules"])
        self.assertNotIn("127.0.0.1", json.dumps(payload))

    def test_ddi_runtime_exposes_protected_rest_seam_and_kb_gated_readiness(self):
        source = (DEPLOY / "ddi-static-server.mjs").read_text(encoding="utf-8")
        supervisor = (DEPLOY / "supervisord.conf").read_text(encoding="utf-8")
        self.assertIn('pathname === "/readyz"', source)
        self.assertIn('pathname === `${API_PREFIX}/checks`', source)
        self.assertIn("serviceAuthorized", source)
        self.assertIn("currentPsychiatrist", source)
        self.assertIn("validateKnowledgeBase(knowledgeBase, { clinicalActive: true })", source)
        self.assertIn('status: "ready"', source)
        self.assertNotIn("production-rest-seam-unavailable", source)
        for setting in (
            'TP_DDI_BASE_URL="http://127.0.0.1:8107"',
            'TP_DDI_SERVICE_AUTH_KEY_ID="tp-ddi-v1"',
            'TP_DDI_SERVICE_AUTH_SECRET="%(ENV_DDI_SERVICE_AUTH_SECRET)s"',
        ):
            self.assertIn(setting, supervisor)

    def test_image_contains_module_backup_operations(self):
        dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
        entrypoint = (DEPLOY / "entrypoint.sh").read_text(encoding="utf-8")
        supervisor = (DEPLOY / "supervisord.conf").read_text(encoding="utf-8")
        policy = json.loads((DEPLOY / "backup-policy.json").read_text(encoding="utf-8"))
        self.assertIn("openssl", dockerfile)
        self.assertFalse(policy["automaticDownMigration"])
        self.assertEqual({module["id"] for module in POLICY["modules"]}, {module["id"] for module in policy["modules"]})
        for module_id, variable in (("ddi-checker", "DDI_REGISTRY_ROOT"), ("bn-manager", "BN_REGISTRY_ROOT")):
            module = next(item for item in policy["modules"] if item["id"] == module_id)
            self.assertIn(module["source"], entrypoint)
            self.assertIn(f'{variable}="{module["source"]}"', supervisor)


if __name__ == "__main__":
    unittest.main()
