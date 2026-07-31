import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPERATIONS = ROOT / "deploy/operations.py"
MODULES = [
    "authentication", "dashboard", "add-new-patient", "diagnosis", "severity",
    "medical-history", "ddi-checker", "bn-manager", "suicide-risk", "treatment-plan",
]


class ModuleBackupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.storage = self.root / "storage"
        self.storage.mkdir()
        configs = []
        for index, module_id in enumerate(MODULES):
            kind = "registry" if module_id in {"ddi-checker", "bn-manager"} else "sqlite"
            source = self.storage / module_id
            if kind == "sqlite":
                source = source.with_suffix(".db")
                with sqlite3.connect(source) as connection:
                    connection.execute("CREATE TABLE records (id INTEGER PRIMARY KEY, value TEXT NOT NULL)")
                    connection.execute("INSERT INTO records(value) VALUES (?)", (f"synthetic-{index}",))
            else:
                source.mkdir()
                (source / "registry.json").write_text(json.dumps({"synthetic": index}), encoding="utf-8")
            configs.append({
                "id": module_id, "moduleVersion": "1.0.0", "dataSchemaVersion": "1.0.0",
                "kind": kind, "sourceEnv": f"TEST_{index}", "source": str(source),
                "readinessUrl": "http://127.0.0.1:1/readyz",
            })
        self.policy = self.root / "policy.json"
        self.policy.write_text(json.dumps({
            "schemaVersion": "1.0.0", "manifestSchemaVersion": "1.0.0",
            "backupFormatVersion": "1.0.0", "metadataRetentionDays": 30,
            "migrationPolicy": "module-owned-forward-only-on-startup",
            "automaticDownMigration": False, "modules": configs,
        }), encoding="utf-8")
        self.key = self.root / "key"
        self.key.write_bytes(b"k" * 32)
        self.key.chmod(0o600)
        self.wrong_key = self.root / "wrong-key"
        self.wrong_key.write_bytes(b"w" * 32)
        self.wrong_key.chmod(0o600)
        self.backups = self.root / "backups"

    def tearDown(self):
        self.temporary.cleanup()

    def run_operations(self, *arguments, success=True):
        result = subprocess.run(
            [sys.executable, str(OPERATIONS), "--policy", str(self.policy), *arguments],
            capture_output=True, text=True, check=False,
        )
        if success and result.returncode:
            self.fail(result.stderr)
        if not success and not result.returncode:
            self.fail("operation unexpectedly succeeded")
        return result

    def create_backup(self):
        result = self.run_operations("backup", "--destination", str(self.backups), "--key-file", str(self.key))
        return Path(json.loads(result.stdout)["manifest"])

    def test_every_database_and_registry_round_trips_through_isolated_verification(self):
        manifest = self.create_backup()
        value = json.loads(manifest.read_text(encoding="utf-8"))
        self.assertEqual(set(MODULES), {entry["moduleId"] for entry in value["modules"]})
        self.assertEqual(len(MODULES), len(list(self.backups.glob("*.backup"))))
        report = self.root / "restore-report.json"
        staging = self.root / "staging"
        self.run_operations(
            "restore", "--manifest", str(manifest), "--key-file", str(self.key),
            "--staging", str(staging), "--report", str(report), "--verify-only",
        )
        restored = json.loads(report.read_text(encoding="utf-8"))
        self.assertTrue(restored["success"])
        self.assertTrue(all(not item["activated"] and item["verified"] for item in restored["modules"]))
        self.assertEqual([], list(staging.iterdir()))

        for config in json.loads(self.policy.read_text(encoding="utf-8"))["modules"]:
            source = Path(config["source"])
            if source.is_dir():
                for child in source.iterdir():
                    child.unlink()
            else:
                source.unlink()
        active_report = self.root / "active-report.json"
        self.run_operations(
            "restore", "--manifest", str(manifest), "--key-file", str(self.key),
            "--staging", str(staging), "--report", str(active_report), "--skip-readiness",
        )
        for config in json.loads(self.policy.read_text(encoding="utf-8"))["modules"]:
            source = Path(config["source"])
            if config["kind"] == "sqlite":
                with sqlite3.connect(source) as connection:
                    self.assertEqual(1, connection.execute("SELECT COUNT(*) FROM records").fetchone()[0])
            else:
                self.assertTrue((source / "registry.json").is_file())

    def test_corruption_wrong_key_wrong_version_and_missing_module_fail_closed(self):
        manifest = self.create_backup()
        value = json.loads(manifest.read_text(encoding="utf-8"))
        artifact = self.backups / value["modules"][0]["artifactName"]
        original = artifact.read_bytes()
        artifact.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
        common = ["restore", "--manifest", str(manifest), "--key-file", str(self.key),
                  "--staging", str(self.root / "stage"), "--report", str(self.root / "report.json"), "--verify-only"]
        self.assertIn("artifact integrity failed", self.run_operations(*common, success=False).stderr)
        artifact.write_bytes(original)
        wrong_key = common.copy()
        wrong_key[wrong_key.index(str(self.key))] = str(self.wrong_key)
        self.assertIn("backup authentication failed", self.run_operations(*wrong_key, success=False).stderr)
        changed = json.loads(self.policy.read_text(encoding="utf-8"))
        changed["modules"][0]["dataSchemaVersion"] = "2.0.0"
        self.policy.write_text(json.dumps(changed), encoding="utf-8")
        self.assertIn("incompatible", self.run_operations(*common, success=False).stderr)
        changed["modules"] = changed["modules"][1:]
        self.policy.write_text(json.dumps(changed), encoding="utf-8")
        self.assertIn("unknown", self.run_operations(*common, success=False).stderr)

    def test_retention_removes_only_approved_expired_aggregate_metadata(self):
        metadata = self.root / "metadata"
        metadata.mkdir()
        old = metadata / "manifest_00000000-0000-4000-8000-000000000000.json"
        old.write_text("{}", encoding="utf-8")
        os.utime(old, (time.time() - 40 * 86400,) * 2)
        denied = self.run_operations("retain", "--metadata", str(metadata), success=False)
        self.assertIn("approved retention policy", denied.stderr)
        result = self.run_operations("retain", "--metadata", str(metadata), "--approved-policy")
        self.assertEqual({"removedAggregateMetadata": 1, "moduleArtifactsRemoved": 0, "ownerRecordsRemoved": 0}, json.loads(result.stdout))

    def test_declared_forward_migration_runs_only_against_staged_storage(self):
        manifest = self.create_backup()
        changed = json.loads(self.policy.read_text(encoding="utf-8"))
        marker = self.root / "migration-marker"
        changed["modules"][0]["dataSchemaVersion"] = "2.0.0"
        changed["modules"][0]["migrations"] = [{
            "from": "1.0.0", "to": "2.0.0",
            "command": [sys.executable, "-c", "import os,pathlib; pathlib.Path(os.environ['INSIGHT_STAGED_STORAGE']).is_file() or (_ for _ in ()).throw(SystemExit(1)); pathlib.Path(r'" + str(marker) + "').write_text('migrated')"],
        }]
        self.policy.write_text(json.dumps(changed), encoding="utf-8")
        self.run_operations(
            "restore", "--manifest", str(manifest), "--key-file", str(self.key),
            "--staging", str(self.root / "stage"), "--report", str(self.root / "report.json"), "--verify-only",
        )
        self.assertEqual("migrated", marker.read_text(encoding="utf-8"))

    def test_restart_and_image_rollback_never_down_migrate(self):
        schemas = {module_id: "1.0.0" for module_id in MODULES}
        current = self.root / "current.json"
        current.write_text(json.dumps({"moduleDataSchemas": schemas}), encoding="utf-8")
        releases = self.root / "releases.json"
        releases.write_text(json.dumps({"releases": [
            {"image": "compatible", "digest": "sha256:" + "1" * 64,
             "supportedDataSchemas": {key: [value] for key, value in schemas.items()}},
            {"image": "old", "digest": "sha256:" + "2" * 64,
             "supportedDataSchemas": {key: ["0.9.0"] for key in schemas}},
        ]}), encoding="utf-8")
        result = self.run_operations(
            "rollback", "--releases", str(releases), "--current-state", str(current), "--image", "compatible",
        )
        self.assertFalse(json.loads(result.stdout)["downMigrationsRun"])
        denied = self.run_operations(
            "rollback", "--releases", str(releases), "--current-state", str(current), "--image", "old", success=False,
        )
        self.assertIn("cannot read current module schemas", denied.stderr)


if __name__ == "__main__":
    unittest.main()
