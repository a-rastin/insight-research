"""Dashboard discovery seam for the diagnosis module.

This is the read-only discovery surface the larger Insight Dashboard (and
other internal integrators) use to learn what this module offers and to
pull audit snapshots of a clinician-confirmed / bypassed session. It
contains NO patient-state mutation — writes live in
``diagnosis_api.py``.

Routes (literal paths; must be declared before any ``/{code}`` route on
the composed router — see ``api.py``):
    GET /diagnosis/_meta   -> criteria tree + the ``rules`` contract
                              (``criteria.meta_contract``). Stable, no
                              patient data. UI bootstraps from this;
                              the ``rules`` block is the single source of
                              truth for the browser page's optimistic
                              display (HANDOFF §9.12).
    GET /diagnosis/_csrf   -> mint a signed double-submit CSRF token,
                              set the ``csrf`` cookie, return the same
                              value JSON-encoded. Read-only (no state
                              mutation).
    GET /internal/dashboard/module-routes/{moduleId}
                            -> Dashboard module-route discovery. The
                              larger Insight Dashboard asks every mounted
                              module for its launch descriptor through
                              this single URL pattern. The diagnosis
                              module answers for ``moduleId == "diagnosis"``
                              and 404s otherwise so a wrong-id call is
                              clean, not a stack trace. Read-only (no
                              state mutation).

Routes (cont.):
    GET /internal/diagnosis/audit/{code}
                            -> audit-log seam for the future Insight Logs
                              module (and other internal integrators).
                              Returns the chronologically ordered list of
                              persisted audit snapshots for ``code``. Read-
                              only (no state mutation). Lives under the
                              ``/internal/...`` prefix so its ``{code}``
                              param does NOT collide with the per-patient
                              ``/{code}`` family — same reasoning as the
                              dashboard discovery route. Auth: ``psychiatrist``
                              or ``admin`` (same read policy as ``_meta`` /
                              ``_csrf``); admins audit, never mutate.

Helpers:
    _dump_for_audit(code)  -> JSON snapshot for the larger Insight app's
                              audit logging. Persisted to the audit
                              table by ``store.audit_snapshot`` and NOW
                              also called from ``diagnosis_api.put_session``
                              on every decision-bearing PUT so local audit
                              events accumulate without waiting for an
                              external Logs module poll. Reserved surface —
                              don't expand without coordinating.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse

from .auth import Session
from . import csrf as _csrf
from .criteria import get_criteria, meta_contract
from .deps import require_psychiatrist_or_admin, store

router = APIRouter()


# Stable id this module advertises to the Dashboard discovery endpoint.
# Sourced from the settings adapter so a non-default mount prefix
# (``DIAGNOSIS_MODULE_BASE_PATH``) flows through to the launch href the
# descriptor returns; the REST paths themselves stay prefix-less so the
# mount prefix remains the parent app's choice (HANDOFF §2).
from .config import settings
MODULE_ID = settings.module_id


@router.get("/diagnosis/_meta")
def meta(_: Session = Depends(require_psychiatrist_or_admin)):
    """Return the criteria tree and the rule contract the UI derives its
    optimistic display from. Stable, no patient data. UI bootstraps from this.

    ``rules`` (``criteria.meta_contract()``) exposes the SAME primitives
    ``evaluate()`` reads (symptom / core / duration / guard ids + the
    DSM-5-TR thresholds). The browser page uses them for instant-feedback
    tiles instead of mirroring the rule logic in JS — a server rule change
    ships through ``rules`` as the single source of truth, locked by
    ``test_unittest.py`` against every id subset. Do NOT reimplement the
    rules client-side; consume this contract.
    """
    return {"criteria": get_criteria(), "rules": meta_contract()}


@router.get("/diagnosis/_csrf")
def csrf_token(_: Session = Depends(require_psychiatrist_or_admin)):
    """Mint a signed double-submit CSRF token. Sets the ``csrf`` cookie
    and returns the same value JSON-encoded so non-browser clients can
    read it without scraping cookies. Read-only (no state mutation)."""
    token = _csrf.mint()
    resp = JSONResponse({"token": token})
    _csrf.set_cookie(resp, token)
    return resp


@router.get("/internal/dashboard/module-routes/{moduleId}")
def module_routes(moduleId: str, _: Session = Depends(require_psychiatrist_or_admin)):
    """Dashboard module-route discovery.

    The larger Insight Dashboard learns how to launch each mounted module
    by calling this single URL pattern across every module. The diagnosis
    module answers for ``moduleId == "diagnosis"`` and returns its launch
    descriptor; any other id falls through to a clean 404 so a misrouted
    call is loud but does not leak a stack trace.

    Descriptor shape (stable; Dashboard depends on every key):

        {
          "moduleId":    "diagnosis",
          "title":       "Diagnosis",
          "description": "DSM-5-TR schizophrenia criteria checklist.",
          "launch":      {"href": "/modules/diagnosis"},
          "routes":      {"self":    "/diagnosis/_meta",
                          "csrf":    "/diagnosis/_csrf",
                          "session": "/diagnosis/{code}"}
        }

    Read-only. No patient-state mutation, no CSRF gate (read policy only).
    """
    if moduleId != MODULE_ID:
        raise HTTPException(status_code=404, detail="Unknown module id")
    return {
        "moduleId": MODULE_ID,
        "title": "Diagnosis",
        "description": "DSM-5-TR schizophrenia criteria checklist.",
        "launch": {"href": settings.launch_href},
        "routes": {
            "self": "/diagnosis/_meta",
            "csrf": "/diagnosis/_csrf",
            "session": "/diagnosis/{code}",
        },
    }


@router.get("/internal/diagnosis/audit/{code}")
def audit_log(code: str, _: Session = Depends(require_psychiatrist_or_admin)):
    """Audit-log seam — expose persisted audit snapshots for a code.

    The future Insight Logs module (and any internal integrator) reads a
    code's chronological audit trail through this single URL. Each put on
    a ``diagnosis`` session is now persisted as an audit event by
    ``diagnosis_api.put_session`` (via ``store.audit_snapshot``), so this
    route returns whatever has accumulated rather than snapshotting on
    demand — the Logs module reads, never triggers a write.

    Lives under ``/internal/diagnosis/...`` so the ``{code}`` parameter
    does NOT collide with the per-patient ``/{code}`` family the dashboard
    seam must precede (same reasoning as ``/internal/dashboard/module-routes/{moduleId}``).
    Read-only: no state mutation, no CSRF gate. Auth: ``psychiatrist`` or
    ``admin`` — clinicians read the audit of sessions they wrote, admins
    read for review; neither mutates clinical state here.

    Response shape (stable; Logs module depends on every key):

        {
          "code":       "P-0427-A",
          "snapshots": [ {parsed JSON snapshot, oldest first}, ... ]
        }

    An unknown / never-audited code yields an empty ``snapshots`` list
    (NOT a 404) — ``code`` is the free-text local session key, and an
    empty trail is a legitimate audit state (no writes recorded yet).
    """
    import json
    raw = store.list_audits(code)
    return {"code": code, "snapshots": [json.loads(s) for s in raw]}


def _dump_for_audit(code: str) -> str:
    """JSON snapshot for audit logging. Persisted to the audit table by
    ``store.audit_snapshot`` (which both this hook and
    ``diagnosis_api.put_session`` call) and returned for the larger Insight
    app's audit logger. Persisting every decision-bearing PUT through
    ``put_session`` keeps the local audit table authoritative even before
    the Logs module ships — when it does, ``GET /internal/diagnosis/audit/{code}``
    reads the persisted trail instead of re-snapshotting."""
    return store.audit_snapshot(code)


__all__ = [
    "router",
    "meta",
    "csrf_token",
    "module_routes",
    "audit_log",
    "MODULE_ID",
    "_dump_for_audit",
    "meta_contract",
]
