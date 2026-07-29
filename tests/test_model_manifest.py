import copy
import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKSPACE = ROOT.parent
MANIFEST_PATH = ROOT / "contracts/model-manifest-v1.json"
SCHEMA_PATH = ROOT / "contracts/model-manifest-v1.schema.json"
MODEL_COPY_DIRS = (
    "Modules/acute_dystonia_anticholinergic_bn",
    "Modules/clozapine_aggressive_behavior",
    "Modules/clozapine_suicide_risk_bn",
    "Modules/clozapine_trs_bn",
    "Modules/long acting",
    "Modules/schizophrenia_maintenance_antipsychotic_bn",
    "Modules/statement_6_continuing_same_antipsychotic",
)
REGISTRY_DIR = "Modules/BN-Manager-v.1.1.0/BN-Manager-v.1.1.0/bn_manager_backend/model_registry"


def validate_manifest(manifest):
    artifacts = manifest["artifacts"]
    artifact_ids = [artifact["id"] for artifact in artifacts]
    if len(artifact_ids) != len(set(artifact_ids)):
        raise ValueError("duplicate artifact ID")

    stable_ids = [artifact["stableId"] for artifact in artifacts if artifact["stableId"]]
    if len(stable_ids) != len(set(stable_ids)):
        raise ValueError("duplicate stable ID")

    by_id = {artifact["id"]: artifact for artifact in artifacts}
    for artifact in artifacts:
        if artifact["allowedRuntimeUse"] and artifact["format"] != "xml-bif-0.3-schema":
            if not can_admit(artifact, by_id, manifest["admissionPolicy"]):
                raise ValueError(f"invalid runtime admission: {artifact['id']}")


def can_admit(artifact, by_id, policy):
    source_id = artifact.get("sourceArtifactId")
    source = by_id.get(source_id)
    return (
        artifact["location"] == "registry"
        and artifact["format"] == "xml"
        and artifact["stableId"] is not None
        and artifact["approvalState"] == policy["requiredApprovalState"]
        and source is not None
        and source["sha256"] == artifact["sha256"]
    )


class ModelManifestTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_manifest_matches_versioned_schema_contract(self):
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        for field in self.schema["required"]:
            self.assertIn(field, self.manifest)
        self.assertEqual(self.manifest["contractId"], "insight.model-manifest")
        self.assertEqual(self.manifest["schemaVersion"], "1.0.0")
        self.assertEqual(self.manifest["scope"], "INS-007")
        validate_manifest(self.manifest)

    def test_inventory_is_complete_and_hashes_reconcile(self):
        expected = set()
        for suffix in ("*.xml", "*.net"):
            expected.update(path.relative_to(WORKSPACE).as_posix() for path in (WORKSPACE / "BNs").rglob(suffix))
            for directory in MODEL_COPY_DIRS:
                expected.update(path.relative_to(WORKSPACE).as_posix() for path in (WORKSPACE / directory).rglob(suffix))
        expected.update(
            path.relative_to(WORKSPACE).as_posix()
            for path in (WORKSPACE / REGISTRY_DIR).rglob("*.xml")
        )

        artifacts = self.manifest["artifacts"]
        self.assertEqual({artifact["path"] for artifact in artifacts}, expected)
        for artifact in artifacts:
            digest = hashlib.sha256((WORKSPACE / artifact["path"]).read_bytes()).hexdigest()
            self.assertEqual(digest, artifact["sha256"], artifact["id"])

        by_id = {artifact["id"]: artifact for artifact in artifacts}
        for group in self.manifest["duplicateGroups"]:
            self.assertGreaterEqual(len(group["artifactIds"]), 2)
            self.assertEqual({by_id[item]["sha256"] for item in group["artifactIds"]}, {group["sha256"]})

    def test_exactly_one_runtime_owner_and_non_registry_assets_are_blocked(self):
        self.assertEqual(self.manifest["runtimeOwner"], "bn-manager")
        for topic in self.manifest["topics"]:
            self.assertFalse(topic["allowedRuntimeUse"], topic["id"])
        for artifact in self.manifest["artifacts"]:
            if artifact["format"] == "net" or (artifact["format"] == "xml" and artifact["location"] != "registry"):
                self.assertFalse(artifact["allowedRuntimeUse"], artifact["id"])

    def test_duplicate_stable_id_is_rejected(self):
        changed = copy.deepcopy(self.manifest)
        registry_models = [artifact for artifact in changed["artifacts"] if artifact["stableId"]]
        registry_models[1]["stableId"] = registry_models[0]["stableId"]
        with self.assertRaisesRegex(ValueError, "duplicate stable ID"):
            validate_manifest(changed)

    def test_missing_source_or_approval_blocks_runtime_admission(self):
        policy = self.manifest["admissionPolicy"]
        artifacts = self.manifest["artifacts"]
        by_id = {artifact["id"]: artifact for artifact in artifacts}
        registry_model = next(artifact for artifact in artifacts if artifact["stableId"])

        self.assertFalse(can_admit(registry_model, by_id, policy))
        approved_without_source = {**registry_model, "approvalState": "approved", "sourceArtifactId": None}
        self.assertFalse(can_admit(approved_without_source, by_id, policy))


if __name__ == "__main__":
    unittest.main()
