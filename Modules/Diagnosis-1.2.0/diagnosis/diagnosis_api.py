"""Protected diagnosis REST seam — per-patient session state.

This is the only router in this module that mutates ``DiagnosisStore``.
Three routes, keyed by the free-text ``{code}`` local session key:

    POST /diagnosis/{code}/init  -> create an empty session for a code.
    GET  /diagnosis/{code}       -> criteria tree + current evaluation state.
    PUT  /diagnosis/{code}       -> persist checked ids + decision; return evaluation.

The free-text ``{code}`` is the local session key only. Before a write
route (init / put) persists a row it calls
``patient.resolve_patient(code, cookie)`` to align the row's
``patient_id`` column with the canonical INSIGHT registry id ("Add New
Patient"). The REST contract is unchanged: ``{code}`` stays the local
key; the adapter only enriches ``sessions.patient_id``.

Auth + CSRF policy is shared across the seams (``deps.py``): writes
require ``psychiatrist`` AND a signed double-submit CSRF token; reads
accept either ``psychiatrist`` or ``admin``. Auth runs before CSRF on
writes (dep declaration order) so unauthenticated callers get a clean
401 and never learn a CSRF token exists.

``RESULT_FIELDS`` is the acceptance contract shared by GET/PUT response
evaluation objects. Don't drop or rename keys without bumping the
Insight integration.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from .auth import Session
from .assessment_service import evaluate_checked, legacy_decision_to_v2, v2_decision_to_legacy
from .dashboard import _dump_for_audit
from .deps import require_psychiatrist, require_psychiatrist_or_admin, require_csrf, store
from .patient import resolve_patient


router = APIRouter()


class Submission(BaseModel):
    checked: list[str] = Field(default_factory=list)
    # "confirmed" = criteria met & clinician confirms; "definite" = bypass
    decision: Literal["confirmed", "definite"] | None = None


# Internal: acceptance contract. Shared by GET and PUT.
RESULT_FIELDS = ("met", "a_count", "core_count", "failures", "reason", "checked")


def _legacy_assessment_response(assessment: dict) -> dict:
    decision = assessment["clinicianDecision"]
    return {
        "code": None,
        "patient_id": assessment["patientId"],
        "checked": assessment["checkedCriteria"],
        "evaluation": evaluate_checked(assessment["checkedCriteria"]),
        "decision": v2_decision_to_legacy(decision["type"] if decision else None),
        "updated_at": assessment["updatedAt"],
    }


@router.post("/diagnosis/{code}/init")
def init_session(
    code: str,
    request: Request,
    _: Session = Depends(require_psychiatrist),
    __: None = Depends(require_csrf),
):
    if not code.strip():
        raise HTTPException(status_code=400, detail="Patient code required")
    linked = store.get_legacy_assessment(code.strip())
    if linked:
        return {"created": False, "patient_id": linked["patientId"]}
    patient = resolve_patient(code.strip(), request.headers.get("cookie"))
    created = store.init(code.strip(), patient_id=patient.id)
    return {"created": created, "patient_id": patient.id}


@router.get("/diagnosis/{code}")
def get_session(code: str, _: Session = Depends(require_psychiatrist_or_admin)):
    """Return criteria tree and the patient's current evaluation state.

    404 if the patient code has never been seen. The caller (other Insight
    modules) is expected to create the session via PUT.
    """
    linked = store.get_legacy_assessment(code)
    if linked:
        response = _legacy_assessment_response(linked)
        response["code"] = code
        return response
    session = store.get(code)
    if session is None:
        raise HTTPException(status_code=404, detail=f"Unknown patient code: {code}")
    return {
        "code": session["code"],
        "patient_id": session["patient_id"],
        "checked": session["checked"],
        "decision": session["decision"],
        "evaluation": evaluate_checked(session["checked"]),
        "updated_at": session["updated_at"],
    }


@router.put("/diagnosis/{code}")
def put_session(
    code: str,
    body: Submission,
    request: Request,
    _: Session = Depends(require_psychiatrist),
    __: None = Depends(require_csrf),
):
    """Persist the clinician's checked criteria and final decision.

    Returns the new evaluation. The web page calls this on every checkbox
    change (enabled state) and on the explicit decision buttons. The
    'definite' decision bypasses criteria-met requirement per clinician
    authority (see DESIGN.md - clinician-confirmed bypass).
    """
    if not code.strip():
        raise HTTPException(status_code=400, detail="Patient code required")

    checked = list(dict.fromkeys(body.checked))   # de-dupe, preserve order
    linked = store.get_legacy_assessment(code.strip())
    if linked:
        decision = legacy_decision_to_v2(body.decision)
        if decision == "confirmed" and not evaluate_checked(checked)["met"]:
            raise HTTPException(
                status_code=422,
                detail="A confirmed clinician decision requires the server evaluation to be met; use bypass explicitly otherwise.",
            )
        assessment = store.update_assessment(
            linked["assessmentId"],
            linked["resourceVersion"],
            checked,
            decision,
            _.user_id,
        )
        response = _legacy_assessment_response(assessment)
        response["code"] = code.strip()
        response.pop("checked")
        return response

    patient = resolve_patient(code.strip(), request.headers.get("cookie"))
    session = store.put(
        code.strip(),
        patient_id=patient.id,
        checked=checked,
        decision=body.decision,
    )

    # Audit seam: persist a local audit event on every decision-bearing
    # PUT. ``_dump_for_audit`` (owned by ``dashboard.py``, re-exported by
    # ``api.py``) is the reserved hook for the larger Insight audit logger;
    # calling it here keeps the local audit table authoritative even
    # before the future Logs module ships, and the dashboard seam's
    # ``GET /internal/diagnosis/audit/{code}`` route exposes that trail for
    # it. No re-evaluation is recorded — the snapshot is the source row
    # (decision + checked ids), so it can never be mistaken for a
    # server-derived auto-diagnosis (HANDOFF §6.1).
    _dump_for_audit(code.strip())

    return {
        "code": session["code"],
        "patient_id": session["patient_id"],
        "evaluation": evaluate_checked(session["checked"]),
        "decision": session["decision"],
        "updated_at": session["updated_at"],
    }


__all__ = ["router", "Submission", "RESULT_FIELDS",
           "init_session", "get_session", "put_session"]
