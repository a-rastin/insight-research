from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict

from .auth import Session
from .criteria import CRITERIA, evaluate
from .deps import require_csrf, require_psychiatrist, require_psychiatrist_or_admin, store
from .patient import validate_patient_encounter

INTERFACE_VERSION = "2.0.0"
RULE_VERSION = "diagnosis-rules-1.0.0"
PREFIX = "/api/diagnosis/v2"
SCHEMA_DIR = Path(__file__).resolve().parents[1] / "schema"
IDEMPOTENCY_KEY = re.compile(r"^[A-Za-z0-9._:-]{16,128}$")
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


def problem(request: Request, status: int, code: str, detail: str) -> JSONResponse:
    request_id = request.headers.get("x-request-id")
    body = {"type": f"urn:insight:problem:{code.lower()}", "title": detail, "status": status, "code": code}
    if request_id:
        body["requestId"] = request_id
    return JSONResponse(status_code=status, content=body, media_type="application/problem+json")


def headers(**extra: str) -> dict[str, str]:
    return {"X-Schema-Version": INTERFACE_VERSION, **extra}


def canonical_uuid(value: str) -> str | None:
    try:
        canonical = str(UUID(value))
    except ValueError:
        return None
    return canonical if value == canonical else None


def etag(assessment: dict) -> str:
    return f'"diagnosis-assessment:{assessment["assessmentId"]}:{assessment["resourceVersion"]}"'


def present(assessment: dict) -> dict:
    result = evaluate(assessment["checkedCriteria"])
    status = "decided" if assessment["clinicianDecision"] else ("in-progress" if assessment["checkedCriteria"] else "initialized")
    return {
        "assessmentId": assessment["assessmentId"],
        "patientId": assessment["patientId"],
        "encounterId": assessment["encounterId"],
        "checkedCriteria": assessment["checkedCriteria"],
        "evaluation": {
            "met": result.met, "aCount": result.a_count, "coreCount": result.core_count,
            "failures": result.failures, "reason": result.reason,
            "checkedCriteria": result.checked_ids, "ruleVersion": RULE_VERSION,
        },
        "clinicianDecision": assessment["clinicianDecision"],
        "ruleVersion": RULE_VERSION,
        "schemaVersion": INTERFACE_VERSION,
        "status": status,
        "resourceVersion": assessment["resourceVersion"],
        "createdAt": assessment["createdAt"],
        "updatedAt": assessment["updatedAt"],
        "provenance": {
            "sourceModule": "diagnosis",
            "createdByUserId": assessment["createdByUserId"],
            "lastUpdatedByUserId": assessment["lastUpdatedByUserId"],
        },
    }


def require_schema(request: Request) -> JSONResponse | None:
    if request.headers.get("x-schema-version") != INTERFACE_VERSION:
        return problem(request, 400, "COMMON_UNSUPPORTED_SCHEMA_MAJOR", "X-Schema-Version 2.0.0 is required.")
    return None


@router.get(f"{PREFIX}/contract")
def contract() -> JSONResponse:
    return JSONResponse(content={
        "moduleId": "diagnosis", "moduleVersion": "1.2.0", "interfaceVersion": INTERFACE_VERSION,
        "schemaVersions": [INTERFACE_VERSION], "ruleVersions": [RULE_VERSION], "profileVersion": "1.0.0",
        "openapiPath": f"{PREFIX}/openapi.json", "idempotencyKeyRetentionSeconds": 86400,
    }, headers=headers())


@router.get(f"{PREFIX}/openapi.json")
def openapi_contract() -> FileResponse:
    return FileResponse(SCHEMA_DIR / "diagnosis-assessment-v2.openapi.json", media_type="application/json", headers=headers())


@router.get(f"{PREFIX}/diagnosis-assessment-v2.schema.json")
def schema_contract() -> FileResponse:
    return FileResponse(SCHEMA_DIR / "diagnosis-assessment-v2.schema.json", media_type="application/schema+json", headers=headers())


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
    fingerprint = hashlib.sha256(b"POST\n/api/diagnosis/v2/assessments\n" + await request.body()).hexdigest()
    try:
        replay = store.replay_assessment(actor.user_id, key, fingerprint)
        if replay:
            out = present(replay)
            return JSONResponse(
                status_code=201,
                content=out,
                headers=headers(ETag=etag(out), **{"Idempotency-Replayed": "true"}),
            )
        validate_patient_encounter(patient_id, encounter_id, request.headers.get("cookie"))
        assessment, replayed = store.init_assessment(patient_id, encounter_id, actor.user_id, key, fingerprint)
    except ValueError:
        return problem(request, 409, "COMMON_IDEMPOTENCY_KEY_REUSED", "Idempotency key was reused with a different request.")
    out = present(assessment)
    extra = {"ETag": etag(out)}
    if replayed:
        extra["Idempotency-Replayed"] = "true"
    return JSONResponse(status_code=201, content=out, headers=headers(**extra))


@router.get(f"{PREFIX}/assessments/{{assessmentId}}/audit")
def get_audit(request: Request, assessmentId: str, _: Session = Depends(require_psychiatrist_or_admin)) -> JSONResponse:
    assessment_id = canonical_uuid(assessmentId) or ""
    if not assessment_id:
        return problem(request, 400, "DIAGNOSIS_ASSESSMENT_ID_INVALID", "Assessment ID must be a canonical UUID.")
    if not store.get_assessment(assessment_id):
        return problem(request, 404, "DIAGNOSIS_ASSESSMENT_NOT_FOUND", "Diagnosis assessment was not found.")
    events = store.list_assessment_audits(assessment_id)
    for event in events:
        event["snapshot"] = present(event["snapshot"])
    return JSONResponse(content={"assessmentId": assessment_id, "events": events}, headers=headers())


@router.get(f"{PREFIX}/assessments/{{assessmentId}}")
def get_assessment(request: Request, assessmentId: str, _: Session = Depends(require_psychiatrist_or_admin)) -> JSONResponse:
    assessment_id = canonical_uuid(assessmentId) or ""
    if not assessment_id:
        return problem(request, 400, "DIAGNOSIS_ASSESSMENT_ID_INVALID", "Assessment ID must be a canonical UUID.")
    assessment = store.get_assessment(assessment_id)
    if not assessment:
        return problem(request, 404, "DIAGNOSIS_ASSESSMENT_NOT_FOUND", "Diagnosis assessment was not found.")
    out = present(assessment)
    return JSONResponse(content=out, headers=headers(ETag=etag(out)))


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
    try:
        assessment = store.update_assessment(assessment_id, current["resourceVersion"], checked, body.clinicianDecision.type if body.clinicianDecision else None, actor.user_id)
    except RuntimeError:
        return problem(request, 412, "COMMON_PRECONDITION_FAILED", "Diagnosis assessment has changed.")
    out = present(assessment)
    return JSONResponse(content=out, headers=headers(ETag=etag(out)))


@router.get(f"{PREFIX}/encounters/{{encounterId}}/assessment-snapshot")
def get_encounter_snapshot(request: Request, encounterId: str, _: Session = Depends(require_psychiatrist_or_admin)) -> JSONResponse:
    encounter_id = canonical_uuid(encounterId) or ""
    if not encounter_id:
        return problem(request, 400, "ENCOUNTER_ID_INVALID", "Encounter ID must be a canonical UUID.")
    assessment = store.get_assessment_by_encounter(encounter_id)
    if not assessment:
        return problem(request, 404, "DIAGNOSIS_ASSESSMENT_NOT_FOUND", "Diagnosis assessment was not found.")
    out = present(assessment)
    return JSONResponse(content=out, headers=headers(ETag=etag(out)))


__all__ = ["router", "present", "INTERFACE_VERSION", "RULE_VERSION"]
