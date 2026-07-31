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

    def test_ddi_readiness_remains_fail_closed_until_rest_seam_exists(self):
        source = (DEPLOY / "ddi-static-server.mjs").read_text(encoding="utf-8")
        self.assertIn('pathname === "/readyz"', source)
        self.assertIn("production-rest-seam-unavailable", source)
        self.assertNotIn('json(response, 200, { status: "ready"', source)

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
