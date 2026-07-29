import json
import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ADR = ROOT / "context/architecture-decisions/0004-administration-operations-ownership.md"
CONTRACT = ROOT / "contracts/administration-operations-v1.json"


class AdministrationOperationsContractTest(unittest.TestCase):
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

    def test_ownership_and_separation(self):
        resources = {item["id"]: item for item in self.contract["resources"]}
        self.assertEqual(resources["account-administration"]["owner"], "authentication")
        self.assertEqual(resources["security-audit"]["owner"], "authentication")
        self.assertEqual(resources["clinical-provenance"]["owner"], "originating-clinical-module")
        self.assertEqual(resources["operational-log"]["owner"], "emitting-module")
        self.assertFalse(self.contract["dashboard"]["persistsOwnerData"])
        self.assertFalse(self.contract["dashboard"]["proxiesOwnerData"])
        self.assertFalse(self.contract["separation"]["sharedStoreAllowed"])

    def test_admin_and_psychiatrist_permissions(self):
        permissions = {item["capability"]: item for item in self.contract["permissions"]}
        for capability in (
            "manage-accounts",
            "read-security-audit",
            "read-operational-logs",
            "initiate-backup",
            "initiate-restore",
            "manage-retention",
        ):
            self.assertTrue(permissions[capability]["admin"], capability)
            self.assertFalse(permissions[capability]["psychiatrist"], capability)
        provenance = permissions["read-clinical-provenance"]
        self.assertFalse(provenance["admin"])
        self.assertTrue(provenance["psychiatrist"])
        self.assertEqual(provenance["additionalScope"], "authorized-patient-and-encounter")

    def test_manifest_schema_and_phi_safe_filename(self):
        manifest = self.contract["backupManifest"]
        self.assertFalse(manifest["containsModuleData"])
        self.assertEqual(
            set(manifest["requiredEntryFields"]),
            {
                "moduleId",
                "moduleVersion",
                "dataSchemaVersion",
                "backupFormatVersion",
                "createdAt",
                "artifactName",
                "byteCount",
                "sha256",
            },
        )
        pattern = re.compile(manifest["artifactNamePattern"])
        accepted = next(item for item in self.contract["examples"] if item["name"] == "phi-safe-backup")
        self.assertRegex(accepted["artifactName"], pattern)
        self.assertIn("patient identifiers", manifest["forbiddenArtifactNameSources"])
        self.assertIn("timestamps", manifest["forbiddenArtifactNameSources"])

    def test_restore_cannot_cross_write(self):
        restore = self.contract["restore"]
        self.assertEqual(restore["writer"], "target-module-only")
        self.assertFalse(restore["orchestratorMayReadModuleDatabase"])
        self.assertFalse(restore["orchestratorMayWriteModuleDatabase"])
        self.assertFalse(restore["orchestratorMayAccessPrivateDataDirectory"])
        self.assertIn("entry.moduleId equals target configured moduleId", restore["requiredChecks"])
        example = next(item for item in self.contract["examples"] if item["name"] == "cross-module-restore")
        self.assertNotEqual(example["sourceModuleId"], example["targetModuleId"])
        self.assertEqual(example["result"], "denied-before-write")


if __name__ == "__main__":
    unittest.main()
