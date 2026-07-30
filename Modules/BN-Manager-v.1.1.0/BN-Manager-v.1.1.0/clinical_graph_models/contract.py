from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

MODULE_ID = "bn-manager"
CONTRACT_VERSION = "3.0.0"
PYTHON_PACKAGE = "clinical_graph_models"
ROUTE_PREFIX = "/api/bn-manager/v1"
V3_ROUTE_PREFIX = "/api/bn-manager/v3"

CLINICAL_SAFETY_WORDING = (
    "BN Manager output is clinical decision support, not a diagnosis, prescription, "
    "or treatment order. A licensed clinician must review patient context, source "
    "evidence, contraindications, and local policy before clinical action."
)


@dataclass(frozen=True, slots=True)
class XmlBifTarget:
    format_id: str
    version: str
    extension: str
    mime_type: str
    encoding: str
    root_element: str
    network_element: str
    variable_types: tuple[str, ...]
    table_element: str
    compatibility_note: str


@dataclass(frozen=True, slots=True)
class RouteContract:
    surface: str
    method: str
    path: str
    permission: str
    purpose: str


@dataclass(frozen=True, slots=True)
class TargetNodeContract:
    decision_id: str
    node_id: str
    kind: str
    required_for_surfaces: tuple[str, ...]


XMLBIF_TARGET = XmlBifTarget(
    format_id="XML",
    version="0.3",
    extension=".xml",
    mime_type="application/xml",
    encoding="utf-8",
    root_element="BIF",
    network_element="NETWORK",
    variable_types=("nature",),
    table_element="TABLE",
    compatibility_note=(
        "The supplied XSD.xml and the four module-owned .xml networks are canonical. "
        "Legacy .net and .xmlbif inputs are not accepted by the BN Manager API."
    ),
)

_SURFACES = ("Dashboard", "Add New Patient", "Follow-up")
TARGET_NODES: tuple[TargetNodeContract, ...] = (
    TargetNodeContract("pharmacotherapy", "management_recommendation", "chance", _SURFACES),
    TargetNodeContract("treatment_setting", "management_recommendation", "chance", _SURFACES),
    TargetNodeContract(
        "involuntary_treatment_considerations",
        "management_recommendation",
        "chance",
        _SURFACES,
    ),
    TargetNodeContract("clozapine_suicide_risk", "Clinical_Action_Pattern", "chance", _SURFACES),
)

# Retained as the request/response key for API compatibility. The identifiers now
# select one of the four XML BN targets rather than influence-diagram decisions.
DECISION_IDS: dict[str, str] = {target.decision_id: target.node_id for target in TARGET_NODES}
TARGET_NODE_IDS: tuple[str, ...] = tuple(dict.fromkeys(target.node_id for target in TARGET_NODES))

PERMISSIONS = {
    "read_contract": "bnm:contract:read",
    "evaluate_dashboard": "bnm:dashboard:evaluate",
    "evaluate_add_new_patient": "bnm:add-new-patient:evaluate",
    "evaluate_follow_up": "bnm:follow-up:evaluate",
    "validate_model": "bnm:model:validate",
}

ROLE_PERMISSIONS: dict[str, tuple[str, ...]] = {
    "Psychiatrist": (
        PERMISSIONS["read_contract"],
        PERMISSIONS["evaluate_dashboard"],
        PERMISSIONS["evaluate_add_new_patient"],
        PERMISSIONS["evaluate_follow_up"],
    ),
    "Clinician": (
        PERMISSIONS["read_contract"],
        PERMISSIONS["evaluate_dashboard"],
        PERMISSIONS["evaluate_add_new_patient"],
        PERMISSIONS["evaluate_follow_up"],
    ),
    "CareTeam": (
        PERMISSIONS["read_contract"],
        PERMISSIONS["evaluate_dashboard"],
        PERMISSIONS["evaluate_follow_up"],
    ),
    "IntakeClinician": (
        PERMISSIONS["read_contract"],
        PERMISSIONS["evaluate_add_new_patient"],
    ),
    "ModelManager": (
        PERMISSIONS["read_contract"],
        PERMISSIONS["validate_model"],
    ),
    "Admin": tuple(PERMISSIONS.values()),
}

ROUTES: tuple[RouteContract, ...] = (
    RouteContract(
        "Shared",
        "GET",
        f"{ROUTE_PREFIX}/contract",
        PERMISSIONS["read_contract"],
        "Return the versioned XML BN Manager contract.",
    ),
    RouteContract(
        "Dashboard",
        "POST",
        f"{ROUTE_PREFIX}/dashboard/evaluate",
        PERMISSIONS["evaluate_dashboard"],
        "Evaluate a supplied XML Bayesian Network for dashboard display.",
    ),
    RouteContract(
        "Add New Patient",
        "POST",
        f"{ROUTE_PREFIX}/add-new-patient/evaluate",
        PERMISSIONS["evaluate_add_new_patient"],
        "Evaluate intake evidence against a supplied XML Bayesian Network.",
    ),
    RouteContract(
        "Follow-up",
        "POST",
        f"{ROUTE_PREFIX}/follow-up/evaluate",
        PERMISSIONS["evaluate_follow_up"],
        "Evaluate follow-up evidence against a supplied XML Bayesian Network.",
    ),
    RouteContract(
        "Model Management",
        "POST",
        f"{ROUTE_PREFIX}/models/validate",
        PERMISSIONS["validate_model"],
        "Validate supplied .xml model text against XSD.xml and BN semantics.",
    ),
)

ERROR_CODES: dict[str, str] = {
    "invalid_request": "BNM_INVALID_REQUEST",
    "unauthorized": "BNM_UNAUTHORIZED",
    "forbidden": "BNM_FORBIDDEN",
    "model_not_found": "BNM_MODEL_NOT_FOUND",
    "model_parse_failed": "BNM_MODEL_PARSE_FAILED",
    "model_validation_failed": "BNM_MODEL_VALIDATION_FAILED",
    "unsupported_format": "BNM_UNSUPPORTED_FORMAT",
    "unknown_target_node": "BNM_UNKNOWN_TARGET_NODE",
    "evaluation_failed": "BNM_EVALUATION_FAILED",
    "safety_review_required": "BNM_SAFETY_REVIEW_REQUIRED",
    "internal_error": "BNM_INTERNAL_ERROR",
}


def contract_payload() -> dict[str, Any]:
    return {
        "module_id": MODULE_ID,
        "contract_version": CONTRACT_VERSION,
        "python_package": PYTHON_PACKAGE,
        "route_prefix": ROUTE_PREFIX,
        "v3_route_prefix": V3_ROUTE_PREFIX,
        "routes": [asdict(route) for route in ROUTES],
        "role_permissions": {role: list(permissions) for role, permissions in ROLE_PERMISSIONS.items()},
        "xml_target": asdict(XMLBIF_TARGET),
        "decision_ids": DECISION_IDS,
        "target_nodes": [asdict(target) for target in TARGET_NODES],
        "response_envelope": {
            "ok": "boolean",
            "data": "object|null",
            "error": "object|null",
            "meta": "object",
        },
        "error_codes": ERROR_CODES,
        "clinical_safety_wording": CLINICAL_SAFETY_WORDING,
        "module_boundary": (
            "Callers pass patient context and evidence through BN Manager routes. "
            "No direct imports or database reads are part of the inter-module contract."
        ),
    }


def ok_response(data: Any, request_id: str | None = None, warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "ok": True,
        "data": data,
        "error": None,
        "meta": _meta(request_id=request_id, warnings=list(warnings or [])),
    }


def error_response(
    code: str,
    message: str,
    *,
    request_id: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if code not in ERROR_CODES.values():
        raise ValueError(f"Unknown BN Manager error code: {code}")
    return {
        "ok": False,
        "data": None,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
        "meta": _meta(request_id=request_id, warnings=[CLINICAL_SAFETY_WORDING]),
    }


def _meta(request_id: str | None, warnings: list[str]) -> dict[str, Any]:
    return {
        "module_id": MODULE_ID,
        "contract_version": CONTRACT_VERSION,
        "request_id": request_id,
        "clinical_safety_wording": CLINICAL_SAFETY_WORDING,
        "warnings": warnings,
    }
