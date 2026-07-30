from __future__ import annotations

from dataclasses import asdict
from datetime import UTC, datetime
from hashlib import sha256
import json
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import Body, Depends, FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse

from clinical_graph_models import (
    DECISION_IDS,
    ERROR_CODES,
    MODULE_ID,
    XmlBifCompileError,
    compile_xmlbif,
    contract_payload,
    error_response,
    evaluate_posterior,
    ok_response,
    validate_model,
)
from clinical_graph_models.model import ClinicalGraphModel

from .auth_adapter import AuthenticationRestAdapter, CsrfError, SessionAdapter, SessionState, assert_csrf_token
from .config import BnManagerSettings, get_settings
from .model_registry import get_registry_entry, list_registry_entries, read_registry_model, read_registry_schema

EVALUATION_ROLES = frozenset({"psychiatrist", "admin"})
ADMIN_ROLES = frozenset({"admin"})
DASHBOARD_DISCOVERY_PATH = "/internal/dashboard/module-routes/bn-manager"


class BnManagerHttpError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}


def create_app(
    settings: BnManagerSettings | None = None,
    session_adapter: SessionAdapter | None = None,
) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title=settings.app_name,
        version=contract_payload()["contract_version"],
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
    )
    app.state.session_adapter = session_adapter or AuthenticationRestAdapter(
        settings.auth_session_url,
        settings.auth_timeout_seconds,
    )
    app.state.evaluation_idempotency = {}

    @app.exception_handler(BnManagerHttpError)
    def bn_manager_error(request: Request, exc: BnManagerHttpError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(
                exc.code,
                exc.message,
                request_id=request.headers.get("x-request-id"),
                details=exc.details,
            ),
        )

    def require_verified_session(request: Request) -> SessionState:
        adapter: SessionAdapter = request.app.state.session_adapter
        session = adapter.fetch_session(request)
        if session.expired:
            raise BnManagerHttpError(401, ERROR_CODES["unauthorized"], "Authentication session expired.")
        if not session.active:
            details = {"reason": session.blocked_reason} if session.blocked_reason else {}
            code = ERROR_CODES["forbidden"] if session.blocked_reason else ERROR_CODES["unauthorized"]
            status = 403 if session.blocked_reason else 401
            message = "Authentication session is blocked." if session.blocked_reason else "Authentication session is missing or invalid."
            raise BnManagerHttpError(status, code, message, details)
        return session

    def require_roles(allowed_roles: frozenset[str]):
        def dependency(request: Request, session: SessionState = Depends(require_verified_session)) -> SessionState:
            try:
                assert_csrf_token(request, session, settings.csrf_header_name)
            except CsrfError as exc:
                raise BnManagerHttpError(403, ERROR_CODES["forbidden"], "CSRF token missing or invalid.") from exc
            if session.roles.isdisjoint(allowed_roles):
                raise BnManagerHttpError(
                    403,
                    ERROR_CODES["forbidden"],
                    "Authenticated user does not have a required BN Manager role.",
                    {"required_roles": sorted(allowed_roles), "roles": sorted(session.roles)},
                )
            return session

        return dependency

    @app.get(f"{settings.api_prefix}/health")
    def health() -> dict[str, Any]:
        return ok_response(
            {
                "status": "healthy",
                "module_id": MODULE_ID,
            }
        )

    @app.get(f"{settings.api_prefix}/ready")
    def ready() -> dict[str, Any]:
        static_index = settings.static_dir / "index.html"
        return ok_response(
            {
                "status": "ready",
                "module_id": MODULE_ID,
                "static_ui": static_index.exists(),
                "contract_loaded": contract_payload()["module_id"] == MODULE_ID,
            }
        )

    @app.get("/api/bn-manager/v1/contract")
    def contract() -> dict[str, Any]:
        return ok_response(contract_payload())

    @app.get("/api/bn-manager/v1/models")
    def model_registry_list() -> dict[str, Any]:
        return ok_response(
            {
                "models": list_registry_entries(),
                "schema": {
                    "format": "XML",
                    "version": "0.3",
                    "path": "schemas/XSD.xml",
                },
            }
        )

    @app.get("/api/bn-manager/v3/models")
    def model_registry_list_v3() -> dict[str, Any]:
        return ok_response(
            {
                "interface_version": "3.0.0",
                "models": list_registry_entries(),
                "schema": {"format": "XML", "version": "BIF-0.3"},
            }
        )

    @app.get("/api/bn-manager/v3/models/{stable_id}")
    def model_registry_detail_v3(stable_id: str) -> dict[str, Any]:
        entry = get_registry_entry(stable_id)
        if entry is None:
            raise BnManagerHttpError(404, ERROR_CODES["model_not_found"], "BN Manager registry model not found.")
        return ok_response({"interface_version": "3.0.0", "model": entry.payload()})

    @app.get("/api/bn-manager/v1/models/schema/xml-0.3")
    def model_registry_schema() -> dict[str, Any]:
        return ok_response(
            {
                "format": "XML",
                "version": "0.3",
                "mime_type": "application/xml",
                "text": read_registry_schema(),
            }
        )

    @app.get("/api/bn-manager/v1/models/{stable_id}")
    def model_registry_detail(stable_id: str) -> dict[str, Any]:
        try:
            entry, text = read_registry_model(stable_id)
        except KeyError as exc:
            raise BnManagerHttpError(
                404,
                ERROR_CODES["model_not_found"],
                "BN Manager registry model not found.",
                {"stable_id": stable_id},
            ) from exc
        except ValueError as exc:
            raise BnManagerHttpError(404, ERROR_CODES["invalid_request"], "BN Manager registry file not found.") from exc
        return ok_response(
            {
                "model": entry.payload(),
                "format": "XML",
                "version": "0.3",
                "mime_type": "application/xml",
                "text": text,
            }
        )

    @app.get(DASHBOARD_DISCOVERY_PATH)
    def dashboard_module_route_discovery() -> dict[str, Any]:
        return {
            "module_id": MODULE_ID,
            "name": settings.app_name,
            "routes": [
                {
                    "id": MODULE_ID,
                    "label": settings.app_name,
                    "path": settings.ui_mount_path,
                    "kind": "module-placeholder",
                    "embed": True,
                    "requires_verified_session": True,
                }
            ],
        }

    @app.post("/api/bn-manager/v1/dashboard/evaluate")
    def dashboard_evaluate(
        payload: dict[str, Any] = Body(...),
        session: SessionState = Depends(require_roles(EVALUATION_ROLES)),
    ) -> dict[str, Any]:
        return _evaluate_payload(payload, "Dashboard", session)

    @app.post("/api/bn-manager/v1/add-new-patient/evaluate")
    def add_new_patient_evaluate(
        payload: dict[str, Any] = Body(...),
        session: SessionState = Depends(require_roles(EVALUATION_ROLES)),
    ) -> dict[str, Any]:
        return _evaluate_payload(payload, "Add New Patient", session)

    @app.post("/api/bn-manager/v1/follow-up/evaluate")
    def follow_up_evaluate(
        payload: dict[str, Any] = Body(...),
        session: SessionState = Depends(require_roles(EVALUATION_ROLES)),
    ) -> dict[str, Any]:
        return _evaluate_payload(payload, "Follow-up", session)

    @app.post("/api/bn-manager/v3/evaluations")
    def evaluate_v3(
        request: Request,
        payload: dict[str, Any] = Body(...),
        session: SessionState = Depends(require_roles(EVALUATION_ROLES)),
    ) -> dict[str, Any]:
        key = request.headers.get("idempotency-key", "").strip()
        if not key:
            raise BnManagerHttpError(400, ERROR_CODES["invalid_request"], "Idempotency-Key is required.")
        request_hash = sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        cache_key = (session.subject, key)
        cached = request.app.state.evaluation_idempotency.get(cache_key)
        if cached:
            if cached["request_hash"] != request_hash:
                raise BnManagerHttpError(409, ERROR_CODES["invalid_request"], "Idempotency-Key was reused with a different request.")
            return cached["response"]
        response = _evaluate_payload_v3(payload, session)
        request.app.state.evaluation_idempotency[cache_key] = {
            "request_hash": request_hash,
            "response": response,
        }
        return response

    @app.post("/api/bn-manager/v1/models/validate")
    def model_validate(
        payload: dict[str, Any] = Body(...),
        session: SessionState = Depends(require_roles(ADMIN_ROLES)),
    ) -> dict[str, Any]:
        model = _load_model(payload)
        target_node_ids = _validate_targets(payload)
        messages = [
            asdict(message)
            for message in validate_model(model, target_node_ids=target_node_ids)
        ]
        return ok_response(
            {
                "valid": not any(message["severity"] == "error" for message in messages),
                "messages": messages,
                "checked_by": session.subject,
            }
        )

    index_path = settings.static_dir / "index.html"

    @app.get(settings.ui_mount_path, include_in_schema=False)
    def ui_index(session: SessionState = Depends(require_verified_session)) -> FileResponse:
        return FileResponse(index_path)

    @app.get(f"{settings.ui_mount_path}/{{asset_path:path}}", include_in_schema=False)
    def ui_asset(asset_path: str, session: SessionState = Depends(require_verified_session)) -> FileResponse:
        static_dir = Path(settings.static_dir).resolve()
        if not asset_path:
            return FileResponse(index_path)
        path = (static_dir / asset_path).resolve()
        if static_dir not in (path, *path.parents) or not path.is_file():
            raise BnManagerHttpError(404, ERROR_CODES["invalid_request"], "BN Manager UI asset not found.")
        return FileResponse(path)

    return app


app = create_app()


def _evaluate_payload(payload: dict[str, Any], surface: str, session: SessionState) -> dict[str, Any]:
    model = _load_model(payload, allow_text=False)
    messages = [asdict(message) for message in validate_model(model)]
    if any(message["severity"] == "error" for message in messages):
        raise BnManagerHttpError(
            422,
            ERROR_CODES["model_validation_failed"],
            "Model parsed but failed validation.",
            {"messages": messages},
        )

    target = _target_node(payload)
    try:
        result = evaluate_posterior(model, target, payload.get("evidence") or {})
    except KeyError as exc:
        raise BnManagerHttpError(
            404,
            ERROR_CODES["unknown_target_node"],
            str(exc),
            {"target": target},
        ) from exc
    except ValueError as exc:
        raise BnManagerHttpError(
            422,
            ERROR_CODES["evaluation_failed"],
            str(exc),
            {"target": target},
        ) from exc

    return ok_response(
        {
            "surface": surface,
            "target": result.target,
            "values": result.values,
            "rankings": [
                {"state": state, "probability": value}
                for state, value in sorted(result.values.items(), key=lambda item: item[1], reverse=True)
            ],
            "warnings": messages,
            "evaluated_by": session.subject,
        }
    )


def _load_model(payload: dict[str, Any], *, allow_text: bool = True) -> ClinicalGraphModel:
    model_payload = payload.get("model") if isinstance(payload.get("model"), dict) else payload
    text = str(model_payload.get("text") or model_payload.get("model_text") or "").strip()
    stable_id = str(model_payload.get("stable_id") or model_payload.get("model_id") or "").strip()
    if text and not allow_text:
        raise BnManagerHttpError(
            400,
            ERROR_CODES["invalid_request"],
            "Clinical evaluation accepts registry stable_id only; caller model text is prohibited.",
        )
    if not text and stable_id:
        try:
            _, text = read_registry_model(stable_id)
        except KeyError as exc:
            raise BnManagerHttpError(
                404,
                ERROR_CODES["model_not_found"],
                "BN Manager registry model not found.",
                {"stable_id": stable_id},
            ) from exc
    if not text:
        raise BnManagerHttpError(400, ERROR_CODES["invalid_request"], "XML model text or model_id is required.")

    format_name = str(model_payload.get("format") or model_payload.get("model_format") or "XML").strip().lower()
    if format_name not in {"xml", ".xml", "bif-0.3", "application/xml"}:
        raise BnManagerHttpError(
            415,
            ERROR_CODES["unsupported_format"],
            "Model format must be XML using the module XSD.xml schema.",
            {"format": format_name},
        )
    try:
        return compile_xmlbif(text, schema_text=read_registry_schema())
    except XmlBifCompileError as exc:
        raise BnManagerHttpError(
            400,
            ERROR_CODES["model_parse_failed"],
            str(exc),
            exc.details(),
        ) from exc


def _target_node(payload: dict[str, Any]) -> str:
    explicit = payload.get("target_node_id") or payload.get("target")
    if explicit:
        return str(explicit)
    model_payload = payload.get("model") if isinstance(payload.get("model"), dict) else payload
    stable_id = str(model_payload.get("stable_id") or model_payload.get("model_id") or "").strip()
    if stable_id:
        entry = get_registry_entry(stable_id)
        if entry is not None:
            return entry.target_node
    decision_id = str(payload.get("target_decision_id") or payload.get("decision_id") or "pharmacotherapy")
    target = DECISION_IDS.get(decision_id)
    if target is None:
        raise BnManagerHttpError(
            404,
            ERROR_CODES["unknown_target_node"],
            "Unknown BN Manager decision id.",
            {"decision_id": decision_id},
        )
    return target


def _validate_targets(payload: dict[str, Any]) -> list[str] | None:
    """Resolve caller-supplied target nodes for the validate endpoint.

    Returns ``None`` when the caller did not name any target so the semantic
    validator skips the target-node existence check (a caller may be auditing a
    model that is not tied to a known decision). Explicit node ids win; declared
    decision ids resolve through the frozen contract.
    """
    explicit_nodes: list[str] = []
    raw_node = payload.get("target_node_id") or payload.get("target")
    raw_nodes = payload.get("target_node_ids")
    if isinstance(raw_nodes, list):
        explicit_nodes.extend(str(item) for item in raw_nodes if item)
    elif raw_node:
        explicit_nodes.append(str(raw_node))

    decision_ids: list[str] = []
    raw_decision = payload.get("target_decision_id") or payload.get("decision_id")
    raw_decisions = payload.get("target_decision_ids")
    if isinstance(raw_decisions, list):
        decision_ids.extend(str(item) for item in raw_decisions if item)
    elif raw_decision:
        decision_ids.append(str(raw_decision))

    if not explicit_nodes and not decision_ids:
        return None

    targets: list[str] = list(explicit_nodes)
    for decision_id in decision_ids:
        resolved = DECISION_IDS.get(decision_id)
        if resolved is None:
            raise BnManagerHttpError(
                404,
                ERROR_CODES["unknown_target_node"],
                "Unknown BN Manager decision id.",
                {"decision_id": decision_id},
            )
        if resolved not in targets:
            targets.append(resolved)
    return targets or None


def _evaluate_payload_v3(payload: dict[str, Any], session: SessionState) -> dict[str, Any]:
    allowed_fields = {"stable_id", "evidence"}
    undeclared_fields = sorted(set(payload) - allowed_fields)
    if undeclared_fields:
        raise BnManagerHttpError(
            400,
            ERROR_CODES["invalid_request"],
            "BN Manager v3 evaluation request contains undeclared fields.",
            {"fields": undeclared_fields},
        )
    stable_id = str(payload.get("stable_id") or "").strip()
    entry = get_registry_entry(stable_id)
    if entry is None:
        raise BnManagerHttpError(
            404, ERROR_CODES["model_not_found"], "BN Manager registry model not found.", {"stable_id": stable_id}
        )
    if entry.clinical_recommendation_use == "excluded":
        raise BnManagerHttpError(
            422,
            ERROR_CODES["safety_review_required"],
            "Pharmacotherapy model evaluation is excluded from clinical recommendation use.",
            {
                "stable_id": entry.stable_id,
                "calibration_status": entry.calibration_status,
                "mapping_version": entry.mapping_version,
            },
        )
    model = _load_model({"stable_id": stable_id}, allow_text=False)
    messages = [
        asdict(message)
        for message in validate_model(model, target_node_ids=[entry.target_node])
    ]
    errors = [message for message in messages if message["severity"] == "error"]
    if errors:
        raise BnManagerHttpError(
            422, ERROR_CODES["model_validation_failed"], "Registry model failed validation.", {"messages": messages}
        )
    evidence = payload.get("evidence") or {}
    if not isinstance(evidence, dict):
        raise BnManagerHttpError(400, ERROR_CODES["invalid_request"], "Evidence must be an object.")
    if any(not isinstance(node_id, str) or not node_id or not isinstance(state, str) or not state for node_id, state in evidence.items()):
        raise BnManagerHttpError(
            400,
            ERROR_CODES["invalid_request"],
            "Evidence names and states must be non-empty strings.",
        )
    node_map = model.node_map()
    accepted = {}
    ignored = {}
    for node_id, state in evidence.items():
        node = node_map.get(node_id)
        if node is None:
            ignored[node_id] = {"value": state, "reason": "unknown-variable"}
        elif state not in node.states:
            ignored[node_id] = {"value": state, "reason": "unknown-state"}
        else:
            accepted[node_id] = state
    try:
        result = evaluate_posterior(model, entry.target_node, accepted)
    except ValueError as exc:
        raise BnManagerHttpError(422, ERROR_CODES["evaluation_failed"], str(exc)) from exc
    evaluated_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    warnings = messages + [
        {"severity": "warning", "code": "BNM_EVIDENCE_IGNORED", "path": key}
        for key in ignored
    ]
    return ok_response(
        {
            "interface_version": "3.0.0",
            "evaluation_id": str(uuid4()),
            "evaluated_at": evaluated_at,
            "model": entry.payload(),
            "target": result.target,
            "accepted_evidence": accepted,
            "ignored_evidence": ignored,
            "warnings": warnings,
            "posterior": result.values,
            "mapping_version": entry.mapping_version,
            "evaluated_by": session.subject,
        }
    )
