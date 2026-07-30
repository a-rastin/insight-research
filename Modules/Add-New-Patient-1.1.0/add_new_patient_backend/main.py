from __future__ import annotations

import base64
import hashlib
import re
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4, uuid5, NAMESPACE_URL

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse

from .auth import AuthSessionError, fetch_auth_identity, PSYCHIATRIST_ROLE
from .config import ROOT, settings
from .csrf import CSRF_COOKIE_NAME, CSRF_WRITE_METHODS, csrf_error, generate_csrf_token, request_has_valid_csrf, sign_csrf_token
from .db import SQLiteAdapter
from .models import (
    PatientCodeResolveV2,
    PatientEncounterCreateV2,
    PatientIntake,
    PatientPatchV2,
    PatientSearchV2,
    generate_patient_code,
)
from .repository import AliasCollisionError, IdempotencyConflictError, PatientRepository, StaleResourceError, now_iso

repo = PatientRepository(SQLiteAdapter(settings.db_path))
repo.initialize()

app = FastAPI(title="Add New Patient Backend")

MODULE_ID = "add-new-patient"
MODULE_TITLE = "Add New Patient"
MODULE_HREF = f"/modules/{MODULE_ID}"
MODULE_ROUTE = {"moduleId": MODULE_ID, "title": MODULE_TITLE, "href": MODULE_HREF}
V2_PREFIX = "/api/add-new-patient/v2"
V2_SCHEMA_VERSION = "2.0.0"
IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._~-]{16,128}$")
CSRF_EXEMPT_POST_PATHS = {
    f"{V2_PREFIX}/patients/search",
    f"{V2_PREFIX}/patient-code-aliases/resolve",
}

PUBLIC_FILES = {"index.html", "styles.css", "app.js"}
EMBEDDED_ASSET_PATHS = {
    "styles.css": "styles.css",
    "app.js": "app.js",
    f"{MODULE_ID}/styles.css": "styles.css",
    f"{MODULE_ID}/app.js": "app.js",
}

# ponytail: in-memory mock — matches Dashboard. Persists only for the process.
MOCK_AUTH_USERS = {
    "psy-1": {"id": str(uuid5(NAMESPACE_URL, "insight:mock-user:psy-1")), "role": "psychiatrist", "username": "psy-1"},
}
MOCK_AUTH_SESSIONS: dict[str, str] = {}


def public_file_response(filename: str) -> FileResponse:
    if filename not in PUBLIC_FILES:
        raise HTTPException(status_code=404, detail={"message": "Not found."})
    full = ROOT / filename
    if not full.is_file():
        raise HTTPException(status_code=404, detail={"message": "Not found."})
    return FileResponse(full)


def json_error(status_code: int, error: str, detail: str | None = None) -> HTTPException:
    payload: dict[str, Any] = {"error": error}
    if detail:
        payload["detail"] = detail
    return HTTPException(status_code=status_code, detail=payload)


def validation_error_key(loc: tuple[Any, ...]) -> str:
    parts = [str(part) for part in loc if part != "body" and isinstance(part, (str, int))]
    return ".".join(parts)


@app.middleware("http")
async def csrf_middleware(request: Request, call_next: Any) -> JSONResponse:
    request.state.request_id = trace_id(request.headers.get("x-request-id"))
    request.state.correlation_id = trace_id(
        request.headers.get("x-correlation-id"),
        fallback=request.state.request_id,
    )
    if (
        request.method in CSRF_WRITE_METHODS
        and request.url.path not in CSRF_EXEMPT_POST_PATHS
        and not request_has_valid_csrf(request)
    ):
        if request.url.path.startswith(V2_PREFIX):
            try:
                identity = await fetch_auth_identity(request)
            except AuthSessionError:
                response = problem_response(
                    request,
                    502,
                    "AUTHENTICATION_SESSION_UNAVAILABLE",
                    "Authentication service is unavailable.",
                )
            else:
                if not identity:
                    response = problem_response(
                        request,
                        401,
                        "AUTHENTICATION_SESSION_REQUIRED",
                        "Authentication is required.",
                    )
                elif identity["user"]["role"] != PSYCHIATRIST_ROLE:
                    response = problem_response(
                        request,
                        403,
                        "AUTHORIZATION_ROLE_REQUIRED",
                        "A psychiatrist session is required.",
                    )
                else:
                    response = problem_response(request, 403, "CSRF_TOKEN_INVALID", "CSRF validation failed.")
        else:
            response = csrf_error()
    else:
        response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Correlation-ID"] = request.state.correlation_id
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    if request.url.path.startswith(V2_PREFIX):
        legacy_error = exc.detail.get("error") if isinstance(exc.detail, dict) else None
        code = {
            "authentication_session_required": "AUTHENTICATION_SESSION_REQUIRED",
            "authentication_session_unavailable": "AUTHENTICATION_SESSION_UNAVAILABLE",
            "psychiatrist_or_admin_required": "AUTHORIZATION_ROLE_REQUIRED",
            "psychiatrist_required": "AUTHORIZATION_ROLE_REQUIRED",
        }.get(legacy_error, "COMMON_HTTP_ERROR")
        title = {
            401: "Authentication is required.",
            403: "The authenticated user is not authorized.",
            404: "Resource was not found.",
            405: "Method is not allowed.",
        }.get(exc.status_code, "Request could not be completed.")
        return problem_response(request, exc.status_code, code, title)
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    if isinstance(exc.detail, dict):
        return JSONResponse(status_code=exc.status_code, content=exc.detail)
    return JSONResponse(status_code=exc.status_code, content={"message": str(exc.detail)})


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors: dict[str, str] = {}
    for err in exc.errors():
        loc = err.get("loc") or ()
        field = validation_error_key(tuple(loc))
        if field:
            msg = err.get("msg", "Invalid value.")
            msg = msg.replace("Value error, ", "")
            errors[field] = msg
    if request.url.path.startswith(V2_PREFIX):
        problem_errors = [
            {"code": "PATIENT_FIELD_INVALID", "field": field, "message": message}
            for field, message in errors.items()
        ]
        return problem_response(
            request,
            422,
            "PATIENT_CONTRACT_VALIDATION_FAILED",
            "Request failed validation.",
            problem_errors,
        )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={"message": "Patient data failed validation.", "errors": errors},
    )


async def require_authenticated_session(request: Request) -> dict[str, Any]:
    try:
        identity = await fetch_auth_identity(request)
    except AuthSessionError as error:
        raise json_error(502, "authentication_session_unavailable", str(error)) from error
    if not identity:
        raise json_error(401, "authentication_session_required")
    return identity


async def require_psychiatrist_or_admin_session(request: Request) -> dict[str, Any]:
    try:
        identity = await fetch_auth_identity(request)
    except AuthSessionError as error:
        raise json_error(502, "authentication_session_unavailable", str(error)) from error
    if not identity:
        raise json_error(401, "authentication_session_required")
    role = (identity.get("user") or {}).get("role")
    if role not in (PSYCHIATRIST_ROLE, "admin"):
        raise json_error(403, "psychiatrist_or_admin_required")
    return identity


async def require_psychiatrist_session(request: Request) -> dict[str, Any]:
    try:
        identity = await fetch_auth_identity(request, require_psychiatrist=True)
    except AuthSessionError as error:
        raise json_error(502, "authentication_session_unavailable", str(error)) from error
    if not identity:
        raise json_error(401, "authentication_session_required")
    return identity


async def require_v2_psychiatrist_session(request: Request) -> dict[str, Any]:
    identity = await require_authenticated_session(request)
    if identity["user"]["role"] != PSYCHIATRIST_ROLE:
        raise json_error(403, "psychiatrist_required")
    return identity


def trace_id(supplied: str | None, *, fallback: str | None = None) -> str:
    try:
        return str(UUID(supplied or ""))
    except ValueError:
        return fallback or str(uuid4())


def request_id(request: Request) -> str:
    return getattr(request.state, "request_id", trace_id(request.headers.get("x-request-id")))


def v2_headers(**extra: str) -> dict[str, str]:
    return {"X-Schema-Version": V2_SCHEMA_VERSION, **extra}


def problem_response(
    request: Request,
    status_code: int,
    code: str,
    title: str,
    errors: list[dict[str, str]] | None = None,
) -> JSONResponse:
    body: dict[str, Any] = {
        "type": f"urn:insight:problem:{code.lower().replace('_', '-')}",
        "title": title,
        "status": status_code,
        "code": code,
        "requestId": request_id(request),
    }
    if errors:
        body["errors"] = errors
    return JSONResponse(
        status_code=status_code,
        content=body,
        headers=v2_headers(),
        media_type="application/problem+json",
    )


def require_uuid(value: str) -> str | None:
    try:
        parsed = UUID(value)
    except ValueError:
        return None
    canonical = str(parsed)
    return canonical if value == canonical else None


def require_v2_request_schema(request: Request) -> JSONResponse | None:
    version = request.headers.get("x-schema-version")
    if not version or version.split(".", 1)[0] != "2":
        return problem_response(
            request,
            400,
            "COMMON_UNSUPPORTED_SCHEMA_MAJOR",
            "X-Schema-Version must declare a supported v2 schema.",
        )
    return None


def resource_etag(resource_type: str, resource_id: str, version: int) -> str:
    digest = hashlib.sha256(f"{resource_type}:{resource_id}:{version}".encode("ascii")).hexdigest()
    return f'"{digest}"'


def decode_page_token(token: str | None) -> int | None:
    if token is None:
        return 0
    try:
        raw = base64.urlsafe_b64decode(token + "=" * (-len(token) % 4)).decode("ascii")
        offset = int(raw)
    except (ValueError, UnicodeDecodeError):
        return None
    return offset if offset >= 0 else None


def encode_page_token(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode("ascii")).decode("ascii").rstrip("=")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"module": "Add New Patient", "status": "ok"}


@app.get("/internal/dashboard/module-routes/add-new-patient")
async def dashboard_module_route() -> dict[str, str]:
    return MODULE_ROUTE


@app.get("/api/auth/v2/session")
async def mock_auth_session(request: Request) -> JSONResponse:
    if not settings.use_mock_auth:
        return JSONResponse(status_code=404, content={"error": "not_found"})

    requested_user = request.headers.get("x-demo-auth-user")
    if requested_user:
        user = MOCK_AUTH_USERS.get(requested_user)
        if not user:
            return JSONResponse(status_code=401, content={"authenticated": False})
        session_id = str(uuid5(NAMESPACE_URL, f"insight:mock-session:{user['id']}"))
        MOCK_AUTH_SESSIONS[session_id] = requested_user
        return JSONResponse(content={
            "authenticated": True,
            "authorized": True,
            "interfaceVersion": "2.0.0",
            "session": {"id": session_id, "active": True, "expiresAt": "2999-01-01T00:00:00Z"},
            "user": user,
            "gates": {"passwordChangeRequired": False, "disclaimerRequired": False, "disclaimerVersion": "mock-v1"},
            "compatibility": {"legacyUserId": 1, "legacyRole": "user"},
        }, headers={"X-Schema-Version": "2.0.0"})

    session_id = request.headers.get("x-auth-session") or request.headers.get("x-auth-session-id")
    user_id = MOCK_AUTH_SESSIONS.get(session_id or "")
    user = MOCK_AUTH_USERS.get(user_id or "")
    if not user:
        return JSONResponse(status_code=401, content={"authenticated": False})
    return JSONResponse(content={
        "authenticated": True,
        "authorized": True,
        "interfaceVersion": "2.0.0",
        "session": {"id": session_id, "active": True, "expiresAt": "2999-01-01T00:00:00Z"},
        "user": user,
        "gates": {"passwordChangeRequired": False, "disclaimerRequired": False, "disclaimerVersion": "mock-v1"},
        "compatibility": {"legacyUserId": 1, "legacyRole": "user"},
    }, headers={"X-Schema-Version": "2.0.0"})


@app.get("/api/add-new-patient/csrf")
async def csrf() -> JSONResponse:
    token = generate_csrf_token()
    response = JSONResponse(content={"csrfToken": token})
    response.set_cookie(
        CSRF_COOKIE_NAME,
        sign_csrf_token(token),
        httponly=True,
        samesite="lax",
        secure=False,
        path="/",
    )
    return response


@app.get("/api/patients")
async def list_patients(_: dict[str, Any] = Depends(require_authenticated_session)) -> dict[str, Any]:
    return {"patients": repo.list_patients()}


@app.post("/api/patients")
async def create_patient(
    payload: PatientIntake,
    identity: dict[str, Any] = Depends(require_psychiatrist_session),
) -> JSONResponse:
    data = payload.to_patient_record()

    if not data.get("patientCode"):
        existing = repo.existing_codes()
        code = generate_patient_code()
        while code in existing:
            code = generate_patient_code()
        data["patientCode"] = code

    try:
        record = repo.create_patient({"id": str(uuid4()), **data}, identity["user"]["id"])
    except Exception:
        if repo.get_patient(data["patientCode"]):
            errors = {"demographics.patientCode": "Patient code already exists. Generate a new code and submit again."}
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={"message": "Patient data failed validation.", "errors": errors},
            )
        raise

    return JSONResponse(status_code=status.HTTP_201_CREATED, content={"patient": record})


@app.get(f"{V2_PREFIX}/contract")
async def patient_encounter_v2_contract() -> JSONResponse:
    return JSONResponse(
        content={
            "moduleId": MODULE_ID,
            "moduleVersion": "1.1.0",
            "interfaceVersion": V2_SCHEMA_VERSION,
            "schemaVersions": [V2_SCHEMA_VERSION],
            "profileVersion": "1.0.0",
            "openapiPath": f"{V2_PREFIX}/openapi.json",
            "idempotencyKeyRetentionSeconds": 86400,
            "time": now_iso(),
        },
        headers=v2_headers(),
    )


@app.get(f"{V2_PREFIX}/openapi.json")
async def patient_encounter_v2_openapi() -> FileResponse:
    return FileResponse(
        ROOT / "schema" / "patient-encounter-v2.openapi.json",
        media_type="application/json",
        headers=v2_headers(),
    )


@app.get(f"{V2_PREFIX}/patient-encounter-v2.schema.json")
async def patient_encounter_v2_schema() -> FileResponse:
    return FileResponse(
        ROOT / "schema" / "patient-encounter-v2.schema.json",
        media_type="application/schema+json",
        headers=v2_headers(),
    )


@app.get(f"{V2_PREFIX}/patients")
async def list_patients_v2(
    request: Request,
    page_size: int = Query(default=50, alias="pageSize", ge=1, le=100),
    page_token: str | None = Query(default=None, alias="pageToken"),
    _: dict[str, Any] = Depends(require_authenticated_session),
) -> JSONResponse:
    offset = decode_page_token(page_token)
    if offset is None:
        return problem_response(request, 400, "PATIENT_PAGE_TOKEN_INVALID", "Page token is invalid.")
    items, has_more = repo.list_patients_v2(offset, page_size)
    next_token = encode_page_token(offset + page_size) if has_more else None
    return JSONResponse(content={"items": items, "nextPageToken": next_token}, headers=v2_headers())


@app.post(f"{V2_PREFIX}/patients/search")
async def search_patients_v2(
    request: Request,
    payload: PatientSearchV2,
    _: dict[str, Any] = Depends(require_authenticated_session),
) -> JSONResponse:
    schema_error = require_v2_request_schema(request)
    if schema_error:
        return schema_error
    offset = decode_page_token(payload.pageToken)
    if offset is None:
        return problem_response(request, 400, "PATIENT_PAGE_TOKEN_INVALID", "Page token is invalid.")
    items, has_more = repo.list_patients_v2(offset, payload.pageSize, payload.query)
    next_token = encode_page_token(offset + payload.pageSize) if has_more else None
    return JSONResponse(content={"items": items, "nextPageToken": next_token}, headers=v2_headers())


@app.post(f"{V2_PREFIX}/patient-code-aliases/resolve")
async def resolve_patient_code_alias_v2(
    request: Request,
    payload: PatientCodeResolveV2,
    _: dict[str, Any] = Depends(require_authenticated_session),
) -> JSONResponse:
    schema_error = require_v2_request_schema(request)
    if schema_error:
        return schema_error
    try:
        alias = repo.get_alias_v2(payload.patientCode)
    except AliasCollisionError:
        return problem_response(request, 409, "PATIENT_ALIAS_COLLISION", "Patient-code alias is ambiguous.")
    if not alias:
        return problem_response(request, 404, "PATIENT_ALIAS_NOT_FOUND", "Patient-code alias was not found.")
    return JSONResponse(content=alias, headers=v2_headers())


@app.post(f"{V2_PREFIX}/patients")
async def create_patient_encounter_v2(
    request: Request,
    payload: PatientEncounterCreateV2,
    identity: dict[str, Any] = Depends(require_v2_psychiatrist_session),
) -> JSONResponse:
    schema_error = require_v2_request_schema(request)
    if schema_error:
        return schema_error
    idempotency_key = request.headers.get("idempotency-key", "")
    if not IDEMPOTENCY_KEY_PATTERN.fullmatch(idempotency_key):
        return problem_response(
            request,
            400,
            "COMMON_IDEMPOTENCY_KEY_INVALID",
            "Idempotency-Key must contain 16-128 allowed characters.",
        )
    data = payload.model_dump(mode="json")
    if not data["patient"].get("patientCode"):
        existing = repo.existing_codes()
        code = generate_patient_code()
        while code in existing:
            code = generate_patient_code()
        data["patient"]["patientCode"] = code
    raw_body = await request.body()
    fingerprint = hashlib.sha256(
        f"POST\n{V2_PREFIX}/patients\n".encode("ascii") + raw_body
    ).hexdigest()
    try:
        body, replayed = repo.create_patient_encounter_v2(
            data,
            identity["user"]["id"],
            idempotency_key,
            fingerprint,
        )
    except IdempotencyConflictError:
        return problem_response(
            request,
            409,
            "COMMON_IDEMPOTENCY_KEY_REUSED",
            "Idempotency key was reused with a different request.",
        )
    except AliasCollisionError:
        return problem_response(request, 409, "PATIENT_ALIAS_COLLISION", "Patient-code alias already exists.")
    headers = v2_headers(**({"Idempotency-Replayed": "true"} if replayed else {}))
    return JSONResponse(status_code=201, content=body, headers=headers)


@app.get(f"{V2_PREFIX}/patients/{{patient_id}}")
async def get_patient_v2(
    request: Request,
    patient_id: str,
    _: dict[str, Any] = Depends(require_authenticated_session),
) -> JSONResponse:
    patient_id = require_uuid(patient_id) or ""
    if not patient_id:
        return problem_response(request, 400, "PATIENT_ID_INVALID", "Patient ID must be a canonical UUID.")
    patient = repo.get_patient_v2(patient_id)
    if not patient:
        return problem_response(request, 404, "PATIENT_NOT_FOUND", "Patient was not found.")
    etag = resource_etag("patient", patient_id, patient["resourceVersion"])
    return JSONResponse(content=patient, headers=v2_headers(ETag=etag))


@app.patch(f"{V2_PREFIX}/patients/{{patient_id}}")
async def update_patient_v2(
    request: Request,
    patient_id: str,
    payload: PatientPatchV2,
    _: dict[str, Any] = Depends(require_v2_psychiatrist_session),
) -> JSONResponse:
    schema_error = require_v2_request_schema(request)
    if schema_error:
        return schema_error
    patient_id = require_uuid(patient_id) or ""
    if not patient_id:
        return problem_response(request, 400, "PATIENT_ID_INVALID", "Patient ID must be a canonical UUID.")
    current = repo.get_patient_v2(patient_id)
    if not current:
        return problem_response(request, 404, "PATIENT_NOT_FOUND", "Patient was not found.")
    if_match = request.headers.get("if-match")
    if not if_match:
        return problem_response(request, 428, "COMMON_PRECONDITION_REQUIRED", "If-Match is required.")
    expected_etag = resource_etag("patient", patient_id, current["resourceVersion"])
    if if_match != expected_etag:
        return problem_response(request, 412, "COMMON_PRECONDITION_FAILED", "Patient resource has changed.")
    try:
        patient = repo.update_patient_v2(
            patient_id,
            current["resourceVersion"],
            payload.model_dump(mode="json", exclude_unset=True),
        )
    except StaleResourceError:
        return problem_response(request, 412, "COMMON_PRECONDITION_FAILED", "Patient resource has changed.")
    assert patient is not None
    etag = resource_etag("patient", patient_id, patient["resourceVersion"])
    return JSONResponse(content=patient, headers=v2_headers(ETag=etag))


@app.get(f"{V2_PREFIX}/encounters/{{encounter_id}}")
async def get_encounter_v2(
    request: Request,
    encounter_id: str,
    _: dict[str, Any] = Depends(require_psychiatrist_or_admin_session),
) -> JSONResponse:
    encounter_id = require_uuid(encounter_id) or ""
    if not encounter_id:
        return problem_response(request, 400, "ENCOUNTER_ID_INVALID", "Encounter ID must be a canonical UUID.")
    encounter = repo.get_encounter_v2(encounter_id)
    if not encounter:
        return problem_response(request, 404, "ENCOUNTER_NOT_FOUND", "Encounter was not found.")
    etag = resource_etag("encounter", encounter_id, encounter["resourceVersion"])
    return JSONResponse(content=encounter, headers=v2_headers(ETag=etag))


@app.get(f"{V2_PREFIX}/encounters/{{encounter_id}}/intake-snapshot")
async def get_intake_snapshot_v2(
    request: Request,
    encounter_id: str,
    _: dict[str, Any] = Depends(require_psychiatrist_or_admin_session),
) -> JSONResponse:
    encounter_id = require_uuid(encounter_id) or ""
    if not encounter_id:
        return problem_response(request, 400, "ENCOUNTER_ID_INVALID", "Encounter ID must be a canonical UUID.")
    snapshot = repo.get_intake_snapshot_v2(encounter_id)
    if not snapshot:
        return problem_response(request, 404, "INTAKE_SNAPSHOT_NOT_FOUND", "Intake snapshot was not found.")
    etag = resource_etag("intake-snapshot", snapshot["intakeSnapshotId"], snapshot["resourceVersion"])
    return JSONResponse(content=snapshot, headers=v2_headers(ETag=etag))


@app.get("/api/patients/{id_or_code}/intake", response_model=None)
async def get_patient_intake(
    id_or_code: str,
    _: dict[str, Any] = Depends(require_psychiatrist_or_admin_session),
) -> dict[str, Any] | JSONResponse:
    result = repo.list_intake_records(id_or_code)
    if not result:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Patient was not found."})
    patient, intake_records = result
    return {"patient": patient, "intakeRecords": intake_records}


@app.get("/api/patients/{id_or_code}", response_model=None)
async def get_patient(
    id_or_code: str,
    _: dict[str, Any] = Depends(require_authenticated_session),
) -> dict[str, Any] | JSONResponse:
    patient = repo.get_patient(id_or_code)
    if not patient:
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content={"message": "Patient was not found."})
    return {"patient": patient}


@app.get("/")
async def root() -> FileResponse:
    return public_file_response("index.html")


@app.get("/modules/add-new-patient")
@app.get("/modules/add-new-patient/")
async def embedded_module_shell() -> FileResponse:
    return public_file_response("index.html")


@app.get("/modules/{path:path}")
async def serve_embedded_asset(path: str) -> FileResponse:
    asset = EMBEDDED_ASSET_PATHS.get(path)
    if not asset:
        raise HTTPException(status_code=404, detail={"message": "Not found."})
    return public_file_response(asset)


@app.get("/{path:path}")
async def serve_static(path: str) -> FileResponse:
    # ponytail: allowlist not directory-walk — preserve privacy invariant from old server.
    return public_file_response(path)


# # ponytail: catch-all above handles static allowlist, so no StaticFiles mount.

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=settings.port)
