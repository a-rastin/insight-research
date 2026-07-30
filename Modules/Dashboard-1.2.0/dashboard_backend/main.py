from __future__ import annotations

from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .auth import AuthSessionError, fetch_auth_identity
from .config import ROOT, settings
from .db import SQLiteAdapter
from .repository import DashboardRepository, now_iso

repo = DashboardRepository(SQLiteAdapter(settings.db_path))
repo.initialize()

app = FastAPI(title="Dashboard Backend")

MODULE_BUTTONS = {
    "PSYCHIATRIST": [
        ("add-new-patient", "Add New Patient"),
        ("patient-follow-up", "Patient Follow-up"),
        ("list-of-patients", "List of Patients"),
        ("setting", "Setting"),
    ],
    "ADMIN": [
        ("add-new-user", "Add New User"),
        ("logs", "Logs"),
        ("backup", "Backup"),
        ("list-of-users", "List of Users"),
    ],
}

MOCK_AUTH_USERS = {
    "psy-1": {"id": "psy-1", "role": "PSYCHIATRIST", "fullName": "Mina Rahimi", "title": "Dr."},
    "admin-1": {"id": "admin-1", "role": "ADMIN", "fullName": "Ari Morgan", "title": ""},
}
MOCK_AUTH_SESSIONS: dict[str, str] = {}


def json_error(status_code: int, error: str, detail: str | None = None) -> HTTPException:
    payload: dict[str, Any] = {"error": error}
    if detail:
        payload["detail"] = detail
    return HTTPException(status_code=status_code, detail=payload)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException) -> JSONResponse:
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"error": str(exc.detail)})


async def parse_json_body(request: Request) -> dict[str, Any]:
    if request.headers.get("content-length") in [None, "0"]:
        return {}
    try:
        return await request.json()
    except Exception:
        return {}


async def require_auth_identity(request: Request, session: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        identity = await fetch_auth_identity(request, session)
    except AuthSessionError as error:
        raise json_error(502, "authentication_session_unavailable", str(error)) from error
    if not identity:
        raise json_error(401, "authentication_session_required")
    return identity


async def require_session(request: Request) -> dict[str, Any]:
    session_id = request.query_params.get("session") or request.headers.get("x-dashboard-session")
    session = repo.get_session(session_id)
    if not session:
        raise json_error(401, "dashboard_session_required")

    identity = await require_auth_identity(request, session)
    user = identity["user"]
    if user["id"] != session["userId"]:
        raise json_error(401, "authentication_session_mismatch")

    repo.update_session_auth(session["id"], user["id"], user["role"], identity["authSessionId"])
    session["userId"] = user["id"]
    session["role"] = user["role"]
    session["authSessionId"] = identity["authSessionId"]
    session["authUser"] = with_dashboard_fields(user, session)
    return session


def with_dashboard_fields(user: dict[str, Any], session: dict[str, Any]) -> dict[str, Any]:
    return {**user, "disclaimerAcceptedAt": session.get("disclaimerAcceptedAt")}


def display_name_for(user: dict[str, Any]) -> str:
    if user["role"] == "PSYCHIATRIST":
        full_name = user["fullName"]
        return full_name if full_name.startswith("Dr. ") else f"Dr. {full_name}"
    return user["fullName"]


def module_route_discovery(module_id: str) -> dict[str, str]:
    return {"method": "GET", "href": f"/internal/dashboard/module-routes/{module_id}"}


def workspace_buttons(role: str) -> list[dict[str, Any]]:
    return [
        {"id": module_id, "title": title, "routeDiscovery": module_route_discovery(module_id)}
        for module_id, title in MODULE_BUTTONS[role]
    ]


def module_button(role: str, module_id: str) -> tuple[str, str] | None:
    return next((button for button in MODULE_BUTTONS[role] if button[0] == module_id), None)


def workspace_for(session: dict[str, Any]) -> dict[str, Any]:
    user = session.get("authUser")
    if not user:
        raise json_error(401, "authentication_session_required")

    model: dict[str, Any] = {
        "user": {**user, "displayName": display_name_for(user)},
        "displayName": display_name_for(user),
        "currentDateTime": now_iso(),
        "workspace": {
            "kind": user["role"],
            "title": "Workspace",
            "buttons": workspace_buttons(user["role"]),
        },
    }

    if user["role"] == "PSYCHIATRIST":
        model["requiresDisclaimer"] = not user.get("disclaimerAcceptedAt")
        model["disclaimer"] = {
            "acceptedAt": user.get("disclaimerAcceptedAt"),
            "text": "This workspace is a research prototype. It is not a substitute for clinical judgment, emergency care, or licensed guideline review.",
        }

    return model


@app.get("/healthz")
async def healthz() -> dict[str, Any]:
    return {"ok": True}


@app.get("/readyz")
async def readyz() -> Any:
    try:
        repo.ping()
    except Exception as error:
        return JSONResponse(status_code=503, content={"ok": False, "error": str(error)})
    return {"ok": True}


@app.get("/api/auth/session")
async def mock_auth_session(request: Request) -> JSONResponse:
    if not settings.use_mock_auth:
        return JSONResponse(status_code=404, content={"error": "not_found"})

    requested_user = request.headers.get("x-demo-auth-user")
    if requested_user:
        user = MOCK_AUTH_USERS.get(requested_user)
        if not user:
            return JSONResponse(status_code=401, content={"authenticated": False})
        session_id = f"mock-auth-{user['id']}"
        MOCK_AUTH_SESSIONS[session_id] = user["id"]
        return JSONResponse(content={"authenticated": True, "session": {"id": session_id}, "user": user})

    session_id = request.headers.get("x-auth-session") or request.headers.get("x-auth-session-id")
    user_id = MOCK_AUTH_SESSIONS.get(session_id or "")
    user = MOCK_AUTH_USERS.get(user_id or "")
    if not user:
        return JSONResponse(status_code=401, content={"authenticated": False})
    return JSONResponse(content={"authenticated": True, "session": {"id": session_id}, "user": user})


@app.post("/internal/dashboard/session")
async def create_dashboard_session(request: Request) -> JSONResponse:
    await parse_json_body(request)
    identity = await require_auth_identity(request)
    user = identity["user"]
    session = repo.create_session(str(uuid4()), user["id"], user["role"], identity["authSessionId"])
    session["authUser"] = with_dashboard_fields(user, session)
    repo.record_event(session, "session_created")
    return JSONResponse(
        status_code=201,
        content={
            "sessionId": session["id"],
            "dashboardUrl": f"/dashboard/?session={session['id']}",
            "user": session["authUser"],
        },
    )


@app.delete("/internal/dashboard/session")
async def delete_dashboard_session(session: dict[str, Any] = Depends(require_session)) -> dict[str, Any]:
    repo.deactivate_session(session["id"])
    repo.record_event(session, "session_deleted")
    return {"ok": True}


@app.get("/internal/dashboard/workspace")
@app.get("/internal/dashboard/summary")
async def workspace(session: dict[str, Any] = Depends(require_session)) -> dict[str, Any]:
    return workspace_for(session)


@app.get("/internal/dashboard/module-routes/{module_id}")
async def module_route(module_id: str, session: dict[str, Any] = Depends(require_session)) -> dict[str, Any]:
    button = module_button(session["role"], module_id)
    if not button:
        raise json_error(404, "module_route_not_available")
    return {
        "moduleId": button[0],
        "title": button[1],
        "href": f"/modules/{button[0]}",
        "placeholder": True,
    }


@app.post("/internal/dashboard/disclaimer/accept")
async def accept_disclaimer(session: dict[str, Any] = Depends(require_session)) -> dict[str, Any]:
    user = session["authUser"]
    if user["role"] != "PSYCHIATRIST":
        raise json_error(403, "psychiatrist_only")
    accepted_at = repo.accept_disclaimer(session["id"])
    session["disclaimerAcceptedAt"] = accepted_at
    session["authUser"] = with_dashboard_fields(user, session)
    repo.record_event(session, "disclaimer_accepted")
    return workspace_for(session)


@app.get("/")
async def root() -> FileResponse:
    return FileResponse(ROOT / "index.html")


@app.get("/dashboard/")
async def dashboard_index() -> FileResponse:
    return FileResponse(ROOT / "index.html")


app.mount("/dashboard", StaticFiles(directory=Path(ROOT), html=True), name="dashboard-static")
