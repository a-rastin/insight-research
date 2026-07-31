from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import os
from pathlib import Path


MODEL_REGISTRY_DIR = Path(os.environ.get("BN_REGISTRY_ROOT", Path(__file__).resolve().parent / "model_registry"))
XML_SCHEMA_PATH = "schemas/XSD.xml"


@dataclass(frozen=True, slots=True)
class ModelRegistryEntry:
    stable_id: str
    title: str
    file_path: str
    target_node: str
    active_version: str
    status: str
    artifact_id: str
    source_artifact_id: str
    source_path: str
    manifest_sha256: str
    source_sha256: str
    approval_state: str = "approved"
    allowed_runtime_use: bool = True
    lifecycle_status: str = "reviewed"
    clinical_use_status: str = "approved-for-runtime"
    mapping_version: str = "1.0.0"
    engine_version: str = "clinical-graph-models/3.0.0"
    schema_path: str = XML_SCHEMA_PATH
    calibration_status: str | None = None
    clinical_recommendation_use: str | None = None
    mapping_path: str | None = None

    def payload(self, lifecycle_status: str | None = None) -> dict[str, str | bool]:
        payload = asdict(self)
        for key in (
            "artifact_id", "source_artifact_id", "source_path", "manifest_sha256",
            "source_sha256", "approval_state", "allowed_runtime_use",
        ):
            payload.pop(key)
        model_bytes = resolve_owned_registry_file(self.file_path).read_bytes()
        schema_bytes = resolve_owned_registry_file(self.schema_path).read_bytes()
        payload.update(
            {
                "semantic_version": self.active_version,
                "content_hash": f"sha256:{sha256(model_bytes).hexdigest()}",
                "schema_version": "BIF-0.3",
                "schema_content_hash": f"sha256:{sha256(schema_bytes).hexdigest()}",
            }
        )
        if self.mapping_path is not None:
            mapping_bytes = resolve_owned_registry_file(self.mapping_path).read_bytes()
            payload["mapping_hash"] = f"sha256:{sha256(mapping_bytes).hexdigest()}"
        else:
            payload.pop("mapping_path")
        if self.calibration_status is None:
            payload.pop("calibration_status")
        if self.clinical_recommendation_use is None:
            payload.pop("clinical_recommendation_use")
        payload["lifecycle_status"] = lifecycle_status or self.lifecycle_status
        payload["status"] = payload["lifecycle_status"]
        return payload

    def manifest_payload(self) -> dict[str, str | bool]:
        return {
            "artifact_id": self.artifact_id,
            "source_artifact_id": self.source_artifact_id,
            "source_path": self.source_path,
            "source_sha256": self.source_sha256,
            "registry_path": self.file_path,
            "registry_sha256": self.manifest_sha256,
            "approval_state": self.approval_state,
            "allowed_runtime_use": self.allowed_runtime_use,
            "source_status": "runtime-registry-copy",
            "canonical_owner": "bn-manager",
        }


MODEL_REGISTRY: tuple[ModelRegistryEntry, ...] = (
    ModelRegistryEntry(
        stable_id="bnm.pharmacotherapy",
        title="Pharmacotherapy",
        file_path="xml/BN-Pharmacotherapy.xml",
        target_node="management_recommendation",
        active_version="1.0.0",
        status="draft",
        artifact_id="registry.pharmacotherapy.xml",
        source_artifact_id="source.pharmacotherapy.xml",
        source_path="BNs/Pharmacotherapy/BN-Pharmacotherapy.xml",
        manifest_sha256="ead00b30d6c832c91d3085ffdc58aea68073bf98786e177a4c05bbd878fecfd3",
        source_sha256="ead00b30d6c832c91d3085ffdc58aea68073bf98786e177a4c05bbd878fecfd3",
        mapping_version="2.0.0",
        calibration_status="qualitative-uncalibrated",
        clinical_recommendation_use="allowed-research-runtime",
        mapping_path="governance/pharmacotherapy-mapping-v2.json",
    ),
    ModelRegistryEntry(
        stable_id="bnm.treatment-setting",
        title="Treatment Setting",
        file_path="xml/BN-Treatment-Setting.xml",
        target_node="management_recommendation",
        active_version="1.0.0",
        status="draft",
        artifact_id="registry.treatment-setting.xml",
        source_artifact_id="source.treatment-setting.xml",
        source_path="BNs/Treatment-Setting/BN-Treatment-Setting.xml",
        manifest_sha256="0282bbb4c1b4378728c4f8429a9bc71396d8cd94e61dd508aaef19c08d92ee65",
        source_sha256="0282bbb4c1b4378728c4f8429a9bc71396d8cd94e61dd508aaef19c08d92ee65",
    ),
    ModelRegistryEntry(
        stable_id="bnm.involuntary-treatment-considerations",
        title="Involuntary Treatment Considerations",
        file_path="xml/BN-Involuntary-Treatment-Considerations.xml",
        target_node="management_recommendation",
        active_version="1.0.0",
        status="draft",
        artifact_id="registry.involuntary-treatment.xml",
        source_artifact_id="source.involuntary-treatment.xml",
        source_path="BNs/Involuntary-Treatment-Considerations/BN-Involuntary-Treatment-Considerations.xml",
        manifest_sha256="6c42ea3f0f2491e7f15a7624d60dcb6b84055a5545bd258cf67b0ad8b211cd0d",
        source_sha256="6c42ea3f0f2491e7f15a7624d60dcb6b84055a5545bd258cf67b0ad8b211cd0d",
    ),
    ModelRegistryEntry(
        stable_id="bnm.clozapine-suicide-risk",
        title="Clozapine in Suicide Risk",
        file_path="xml/BN-Clozapine-in-Suicide-Risk.xml",
        target_node="Clinical_Action_Pattern",
        active_version="1.0.0",
        status="draft",
        artifact_id="registry.clozapine-suicide-risk.xml",
        source_artifact_id="source.clozapine-suicide-risk.xml",
        source_path="BNs/Clozapine in Suicide Risk/BN-Clozapine-in-Suicide-Risk.xml",
        manifest_sha256="90f633bee7da1625ca4d44d35ace5acace5ca51ee7d597541ee7a5d0089acf3a",
        source_sha256="90f633bee7da1625ca4d44d35ace5acace5ca51ee7d597541ee7a5d0089acf3a",
    ),
)


def list_registry_entries() -> list[dict[str, str]]:
    resolve_owned_registry_file(XML_SCHEMA_PATH)
    for entry in MODEL_REGISTRY:
        resolve_owned_registry_file(entry.file_path)
    return [entry.payload() for entry in MODEL_REGISTRY]


def get_registry_entry(stable_id: str) -> ModelRegistryEntry | None:
    return next((entry for entry in MODEL_REGISTRY if entry.stable_id == stable_id), None)


def read_registry_model(stable_id: str) -> tuple[ModelRegistryEntry, str]:
    entry = get_registry_entry(stable_id)
    if entry is None:
        raise KeyError(stable_id)
    return entry, read_owned_registry_file(entry.file_path)


def read_registry_schema() -> str:
    return read_owned_registry_file(XML_SCHEMA_PATH)


def read_owned_registry_file(relative_path: str) -> str:
    path = resolve_owned_registry_file(relative_path)
    return path.read_text(encoding="utf-8")


def resolve_owned_registry_file(relative_path: str) -> Path:
    requested = Path(relative_path)
    if requested.is_absolute():
        raise ValueError("Registry file path must be relative.")

    base = MODEL_REGISTRY_DIR.resolve()
    path = (base / requested).resolve()
    if base not in (path, *path.parents) or not path.is_file():
        raise ValueError("Registry file path escapes BN Manager model registry.")
    return path
