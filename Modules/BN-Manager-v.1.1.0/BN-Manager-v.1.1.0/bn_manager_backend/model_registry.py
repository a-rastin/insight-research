from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from pathlib import Path


MODEL_REGISTRY_DIR = Path(__file__).resolve().parent / "model_registry"
XML_SCHEMA_PATH = "schemas/XSD.xml"


@dataclass(frozen=True, slots=True)
class ModelRegistryEntry:
    stable_id: str
    title: str
    file_path: str
    target_node: str
    active_version: str
    status: str
    lifecycle_status: str = "active"
    clinical_use_status: str = "research-only"
    mapping_version: str = "1.0.0"
    engine_version: str = "clinical-graph-models/3.0.0"
    schema_path: str = XML_SCHEMA_PATH

    def payload(self) -> dict[str, str]:
        payload = asdict(self)
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
        return payload


MODEL_REGISTRY: tuple[ModelRegistryEntry, ...] = (
    ModelRegistryEntry(
        stable_id="bnm.pharmacotherapy",
        title="Pharmacotherapy",
        file_path="xml/BN-Pharmacotherapy.xml",
        target_node="management_recommendation",
        active_version="1.0.0",
        status="active",
    ),
    ModelRegistryEntry(
        stable_id="bnm.treatment-setting",
        title="Treatment Setting",
        file_path="xml/BN-Treatment-Setting.xml",
        target_node="management_recommendation",
        active_version="1.0.0",
        status="active",
    ),
    ModelRegistryEntry(
        stable_id="bnm.involuntary-treatment-considerations",
        title="Involuntary Treatment Considerations",
        file_path="xml/BN-Involuntary-Treatment-Considerations.xml",
        target_node="management_recommendation",
        active_version="1.0.0",
        status="active",
    ),
    ModelRegistryEntry(
        stable_id="bnm.clozapine-suicide-risk",
        title="Clozapine in Suicide Risk",
        file_path="xml/BN-Clozapine-in-Suicide-Risk.xml",
        target_node="Clinical_Action_Pattern",
        active_version="1.0.0",
        status="active",
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
