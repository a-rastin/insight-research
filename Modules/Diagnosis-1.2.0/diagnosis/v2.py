from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict

from .auth import Session
from .assessment_service import RULE_VERSION, SCHEMA_VERSION, evaluate_checked, present_assessment
from .criteria import CRITERIA
from .deps import require_csrf, require_psychiatrist, require_psychiatrist_or_admin, store
from .patient import validate_patient_encounter

INTERFACE_VERSION = SCHEMA_VERSION
PREFIX = "/api/diagnosis/v2"
SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schema"
IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._~-]{16,128}$")
CRITERIA_IDS = frozenset(item["id"] for item in CRITERIA)
router = APIRouter()


class V2Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AssessmentInit(V2Model):
    patientId: str
    encounterId: str


class DecisionInput(V2Model):
    type: Literal["confirmed", "bypass"]


class AssessmentUpdate(V2Model):
    checkedCriteria: list[str]
    clinicianDecision: DecisionInput | None


def trace_ids(request: Request) -> tuple[str, str]:
    if hasattr(request.state, "diagnosis_trace_ids"):
        return request.state.diagnosis_trace_ids

    def valid_uuid(value: str | None) -> str | None:
        try:
            return str(UUID(value)) if value else None
        except ValueError:
            return None

    request_id = str(uuid4())
    correlation_id = (
        valid_uuid(request.headers.get("x-correlation-id"))
        or valid_uuid(request.headers.get("x-request-id"))
        or request_id
    )
    request.state.diagnosis_trace_ids = (request_id, correlation_id)
    return request_id, correlation_id


def problem(request: Request, status: int, code: str, detail: str) -> JSONResponse:
    request_id, _ = trace_ids(request)
    body = {
        "type": f"urn:insight:problem:{code.lower().replace('_', '-')}",
        "title": detail,
        "status": status,
        "code": code,
        "requestId": request_id,
    }
    return JSONResponse(
        status_code=status,
        content=body,
        headers=headers(request),
        media_type="application/problem+json",
    )


def headers(request: Request | None = None, **extra: str) -> dict[str, str]:
    result = {"X-Schema-Version": INTERFACE_VERSION}
    if request is not None:
        request_id, correlation_id = trace_ids(request)
        result.update({"X-Request-ID": request_id, "X-Correlation-ID": correlation_id})
    result.update(extra)
    return result


def canonical_uuid(value: str) -> str | None:
    try:
        canonical = str(UUID(value))
    except ValueError:
        return None
    return canonical if value == canonical else None


def etag(assessment: dict) -> str:
    return f'"diagnosis-assessment:{assessment["assessmentId"]}:{assessment["resourceVersion"]}"'


def present(assessment: dict) -> dict:
    return present_assessment(assessment)


def require_schema(request: Request) -> JSONResponse | None:
    if request.headers.get("x-schema-version") != INTERFACE_VERSION:
        return problem(request, 400, "COMMON_UNSUPPORTED_SCHEMA_MAJOR", "X-Schema-Version 2.0.0 is required.")
    return None


@router.get(f"{PREFIX}/contract")
def contract(request: Request) -> JSONResponse:
    return JSONResponse(content={
        "moduleId": "diagnosis", "moduleVersion": "1.2.0", "interfaceVersion": INTERFACE_VERSION,
        "schemaVersions": [INTERFACE_VERSION], "ruleVersions": [RULE_VERSION], "profileVersion": "1.0.0",
        "openapiPath": f"{PREFIX}/openapi.json", "idempotencyKeyRetentionSeconds": 86400,
    }, headers=headers(request))


@router.get(f"{PREFIX}/openapi.json")
def openapi_contract(request: Request) -> FileResponse:
    return FileResponse(SCHEMA_DIR / "diagnosis-assessment-v2.openapi.json", media_type="application/json", headers=headers(request))


@router.get(f"{PREFIX}/diagnosis-assessment-v2.schema.json")
def schema_contract(request: Request) -> FileResponse:
    return FileResponse(SCHEMA_DIR / "diagnosis-assessment-v2.schema.json", media_type="application/schema+json", headers=headers(request))


@router.post(f"{PREFIX}/assessments")
async def init_assessment(request: Request, body: AssessmentInit, actor: Session = Depends(require_psychiatrist), _: None = Depends(require_csrf)) -> JSONResponse:
    if error := require_schema(request):
        return error
    patient_id, encounter_id = canonical_uuid(body.patientId), canonical_uuid(body.encounterId)
    if not patient_id or not encounter_id:
        return problem(request, 400, "DIAGNOSIS_ID_INVALID", "Patient and encounter IDs must be canonical UUIDs.")
    key = request.headers.get("idempotency-key", "")
    if not IDEMPOTENCY_KEY.fullmatch(key):
        return problem(request, 400, "COMMON_IDEMPOTENCY_KEY_INVALID", "Idempotency-Key must contain 16-128 allowed characters.")
    fingerprint = hashlib.sha256(
        b"POST\n/api/diagnosis/v2/assessments\n" + await request.body()
    ).hexdigest()
    try:
        replay = store.replay_assessment(actor.user_id, key, fingerprint)
        if replay:
            out = present(replay)
            return JSONResponse(
                status_code=201,
                content=out,
                headers=headers(request, ETag=etag(out), **{"Idempotency-Replayed": "true"}),
            )
        validate_patient_encounter(patient_id, encounter_id, request.headers.get("cookie"))
        assessment, replayed = store.init_assessment(patient_id, encounter_id, actor.user_id, key, fingerprint)
    except ValueError as error:
        if str(error) == "encounter belongs to a different patient":
            return problem(request, 409, "DIAGNOSIS_ENCOUNTER_CONFLICT", "Encounter already has a diagnosis assessment for another patient.")
        return problem(request, 409, "COMMON_IDEMPOTENCY_KEY_REUSED", "Idempotency key was reused with a different request.")
    out = present(assessment)
    extra = {"ETag": etag(out)}
    if replayed:
        extra["Idempotency-Replayed"] = "true"
    return JSONResponse(status_code=201, content=out, headers=headers(request, **extra))


@router.get(f"{PREFIX}/assessments/{{assessmentId}}/audit")
def get_audit(request: Request, assessmentId: str, _: Session = Depends(require_psychiatrist_or_admin)) -> JSONResponse:
    assessment_id = canonical_uuid(assessmentId) or ""
    if not assessment_id:
        return problem(request, 400, "DIAGNOSIS_ASSESSMENT_ID_INVALID", "Assessment ID must be a canonical UUID.")
    if not store.get_assessment(assessment_id):
        return problem(request, 404, "DIAGNOSIS_ASSESSMENT_NOT_FOUND", "Diagnosis assessment was not found.")
    events = store.list_assessment_audits(assessment_id)
    return JSONResponse(content={"assessmentId": assessment_id, "events": events}, headers=headers(request))


@router.get(f"{PREFIX}/assessments/{{assessmentId}}")
def get_assessment(request: Request, assessmentId: str, _: Session = Depends(require_psychiatrist_or_admin)) -> JSONResponse:
    assessment_id = canonical_uuid(assessmentId) or ""
    if not assessment_id:
        return problem(request, 400, "DIAGNOSIS_ASSESSMENT_ID_INVALID", "Assessment ID must be a canonical UUID.")
    assessment = store.get_assessment(assessment_id)
    if not assessment:
        return problem(request, 404, "DIAGNOSIS_ASSESSMENT_NOT_FOUND", "Diagnosis assessment was not found.")
    out = present(assessment)
    return JSONResponse(content=out, headers=headers(request, ETag=etag(out)))


@router.put(f"{PREFIX}/assessments/{{assessmentId}}")
def update_assessment(request: Request, assessmentId: str, body: AssessmentUpdate, actor: Session = Depends(require_psychiatrist), _: None = Depends(require_csrf)) -> JSONResponse:
    if error := require_schema(request):
        return error
    assessment_id = canonical_uuid(assessmentId) or ""
    if not assessment_id:
        return problem(request, 400, "DIAGNOSIS_ASSESSMENT_ID_INVALID", "Assessment ID must be a canonical UUID.")
    current = store.get_assessment(assessment_id)
    if not current:
        return problem(request, 404, "DIAGNOSIS_ASSESSMENT_NOT_FOUND", "Diagnosis assessment was not found.")
    if not request.headers.get("if-match"):
        return problem(request, 428, "COMMON_PRECONDITION_REQUIRED", "If-Match is required.")
    if request.headers["if-match"] != etag(current):
        return problem(request, 412, "COMMON_PRECONDITION_FAILED", "Diagnosis assessment has changed.")
    if len(body.checkedCriteria) != len(set(body.checkedCriteria)):
        return problem(request, 422, "DIAGNOSIS_CRITERIA_INVALID", "Checked criteria must be unique.")
    checked = body.checkedCriteria
    if set(checked) - CRITERIA_IDS:
        return problem(request, 422, "DIAGNOSIS_CRITERIA_INVALID", "Checked criteria contain unsupported identifiers.")
    if body.clinicianDecision and body.clinicianDecision.type == "confirmed" and not evaluate_checked(checked)["met"]:
        return problem(
            request,
            422,
            "DIAGNOSIS_CONFIRMATION_REQUIRES_MET_CRITERIA",
            "A confirmed clinician decision requires the server evaluation to be met; use bypass explicitly otherwise.",
        )
    try:
        assessment = store.update_assessment(assessment_id, current["resourceVersion"], checked, body.clinicianDecision.type if body.clinicianDecision else None, actor.user_id)
    except RuntimeError:
        return problem(request, 412, "COMMON_PRECONDITION_FAILED", "Diagnosis assessment has changed.")
    out = present(assessment)
    return JSONResponse(content=out, headers=headers(request, ETag=etag(out)))


@router.get(f"{PREFIX}/encounters/{{encounterId}}/assessment-snapshot")
def get_encounter_snapshot(request: Request, encounterId: str, _: Session = Depends(require_psychiatrist_or_admin)) -> JSONResponse:
    return _get_latest_assessment(request, encounterId)


@router.get(f"{PREFIX}/encounters/{{encounterId}}/assessments/latest")
def get_latest_assessment(request: Request, encounterId: str, _: Session = Depends(require_psychiatrist_or_admin)) -> JSONResponse:
    return _get_latest_assessment(request, encounterId)


def _get_latest_assessment(request: Request, encounter_id_value: str) -> JSONResponse:
    encounter_id = canonical_uuid(encounter_id_value) or ""
    if not encounter_id:
        return problem(request, 400, "ENCOUNTER_ID_INVALID", "Encounter ID must be a canonical UUID.")
    assessment = store.get_assessment_by_encounter(encounter_id)
    if not assessment:
        return problem(request, 404, "DIAGNOSIS_ASSESSMENT_NOT_FOUND", "Diagnosis assessment was not found.")
    out = present(assessment)
    return JSONResponse(content=out, headers=headers(request, ETag=etag(out)))


__all__ = ["router", "present", "problem", "headers", "trace_ids", "INTERFACE_VERSION", "RULE_VERSION"]
