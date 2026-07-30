"""Patient identity adapter for the diagnosis module.

Aligns the diagnosis module's free-text patient code with the canonical
patient registry the larger Insight app exposes via its "Add New Patient"
feature. The diagnosis module NEVER reads the patient DB directly — it
forwards the incoming ``Cookie`` header (same trust boundary as
``auth.py``) and reads only the JSON the Insight primitives app returns:

    GET {PATIENT_BASE_URL}/api/patients/lookup?code={code}

Response shape (audit-friendly contract):

    {
        "id":           str,            # canonical patient.id (INSIGHT registry)
        "patient_code": str,            # canonical patientCode (Add New Patient)
        "display_name": str | null      # human-readable, optional
    }

404 from the registry -> the free-text code is not a known patient; the
route maps that to a clean 422. Transport / parse failure collapses to
the same 422 (do not leak registry infra details).

Configuration (env):
    PATIENT_BASE_URL    default "http://localhost:9000" — Insight patient
                        registry (same host as the auth service by default).
    PATIENT_TIMEOUT_S   default 2.0 — fail fast on a slow registry.

Bypass (matches ``csrf.py`` semantics — opt-in via a separate env so auth
can run real while patient lookup is shorted, and vice versa):
    DIAGNOSIS_PATIENT_LOOKUP != "1"   (default) lookup is disabled: the
                                       adapter returns a self-consistent
                                       ``Patient`` built from the free-text
                                       ``code`` itself (id=code,
                                       patient_code=code, display_name=code).
                                       This preserves the prior diagnosis-
                                       local behaviour. The in-process self-
                                       check and offline tests rely on this
                                       short — they never have a live registry.
    DIAGNOSIS_PATIENT_LOOKUP == "1"   enforce real lookup. A 404 / transport
                                       fault / missing canonical id all map
                                       to a clean 422 so the clinician sees
                                       "unknown patient code" instead of a
                                       stack trace.

Wire the dependency from ``api.py`` via ``resolve_patient(code, cookie)``;
routes never construct the url or touch the registry themselves.
"""
from __future__ import annotations

import os
import urllib.error
import urllib.parse
import urllib.request
import json
from dataclasses import dataclass
from uuid import UUID

from fastapi import HTTPException

from .config import settings

# Mutable module globals initialised from the settings adapter (mirrors
# ``auth.py``). ``reset_patient_for_tests`` rebinds ``PATIENT_BASE_URL`` for
# fake-registry tests; readiness inspects the live value.
PATIENT_BASE_URL = settings.patient_url
PATIENT_TIMEOUT_S = settings.patient_timeout_s


@dataclass(frozen=True)
class Patient:
    """Canonical patient identity as the diagnosis module consumes it.

    ``id`` is the INSIGHT registry primary key — what ``store.put`` persists
    in ``sessions.patient_id``. ``patient_code`` is what the clinician typed
    (the Add New Patient code); ``display_name`` is for the audit log only.
    The diagnosis REST contract is keyed by the free-text ``code`` path
    parameter; the adapter only enriches it with the canonical id.
    """
    id: str
    patient_code: str
    display_name: str | None


class _PatientUnavailable(Exception):
    """The patient registry is unreachable or returned a non-JSON body."""


def _fetch_patient(code: str, cookie_header: str | None) -> dict:
    """Call the Insight patient registry. Returns the parsed JSON.

    Raises ``_PatientUnavailable`` on transport / parse failure so the
    caller can map that to a clean 422 (do not leak registry infra details).
    """
    qs = urllib.parse.urlencode({"code": code})
    url = f"{PATIENT_BASE_URL.rstrip('/')}/api/patients/lookup?{qs}"
    req = urllib.request.Request(url, method="GET")
    if cookie_header:
        req.add_header("Cookie", cookie_header)
    try:
        with urllib.request.urlopen(req, timeout=PATIENT_TIMEOUT_S) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        # HTTPError carries a status; 404 is the "not a known patient" case
        # and the caller maps it to a clean 422. Any other status is an
        # infra fault — collapse to the same transport-bus exception so the
        # route does not leak registry internals.
        if e.code == 404:
            raise _PatientNotFound()
        raise _PatientUnavailable(f"registry returned HTTP {e.code}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise _PatientUnavailable(str(e)) from e
    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        raise _PatientUnavailable(f"non-JSON patient response: {e}") from e


class _PatientNotFound(Exception):
    """The registry responded 404 — the code is not a known patient."""


def validate_patient_encounter(
    patient_id: str,
    encounter_id: str,
    cookie_header: str | None,
) -> None:
    """Fail closed unless Add New Patient v2 confirms encounter ownership."""
    try:
        patient_id = str(UUID(patient_id))
        encounter_id = str(UUID(encounter_id))
    except ValueError as error:
        raise HTTPException(status_code=400, detail="Patient and encounter IDs must be canonical UUIDs") from error

    headers = {"X-Schema-Version": "2.0.0"}
    if cookie_header:
        headers["Cookie"] = cookie_header

    def fetch(path: str) -> dict:
        request = urllib.request.Request(f"{PATIENT_BASE_URL.rstrip('/')}{path}", headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=PATIENT_TIMEOUT_S) as response:
                if response.headers.get("X-Schema-Version") != "2.0.0":
                    raise _PatientUnavailable("unsupported schema")
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            if error.code == 404:
                raise _PatientNotFound() from error
            raise _PatientUnavailable(str(error)) from error
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError) as error:
            raise _PatientUnavailable(str(error)) from error

    try:
        patient = fetch(f"/api/add-new-patient/v2/patients/{patient_id}")
        encounter = fetch(f"/api/add-new-patient/v2/encounters/{encounter_id}")
    except _PatientNotFound as error:
        raise HTTPException(status_code=404, detail="Patient or encounter was not found") from error
    except _PatientUnavailable as error:
        raise HTTPException(status_code=503, detail="Patient registry unavailable") from error
    if patient.get("patientId") != patient_id or encounter.get("encounterId") != encounter_id:
        raise HTTPException(status_code=502, detail="Patient registry returned incompatible identity")
    if encounter.get("patientId") != patient_id:
        raise HTTPException(status_code=409, detail="Encounter does not belong to patient")


def _build_patient(payload: dict, code: str) -> Patient:
    """Normalize the registry payload. Fail closed on missing ``id`` —
    a partially populated response must never write a row whose
    ``patient_id`` is empty (that would re-introduce the diagnosis-local
    free-text bug under a different name).
    """
    pid = payload.get("id")
    if not isinstance(pid, str) or not pid:
        raise HTTPException(
            status_code=422,
            detail=f"Patient registry returned no canonical id for code {code!r}",
        )
    patient_code = payload.get("patient_code") or code
    if not isinstance(patient_code, str):
        patient_code = code
    display = payload.get("display_name")
    if display is not None and not isinstance(display, str):
        display = None
    return Patient(id=pid, patient_code=patient_code, display_name=display)


def resolve_patient(code: str, cookie_header: str | None) -> Patient:
    """Resolve a free-text patient code to the canonical INSIGHT patient.

    Honours ``DIAGNOSIS_PATIENT_LOOKUP`` (opt-in):

      * unset / not "1" (default) — lookup disabled; the adapter returns a
        self-consistent ``Patient`` built from ``code`` itself so the row's
        ``patient_id`` column is never blank. This is the prior
        diagnosis-local behaviour preserved for offline tests and the
        self-check.
      * "1" — real lookup enforced. A 404 / transport fault / missing
        ``id`` all map to a clean 422 so the clinician sees "unknown
        patient code" instead of a stack trace.

    Production deployment inside the larger Insight app sets
    ``DIAGNOSIS_PATIENT_LOOKUP=1`` so sessions bind to the canonical
    ``patient.id`` from the "Add New Patient" registry.
    """
    if not code or not code.strip():
        raise HTTPException(status_code=400, detail="Patient code required")

    if os.environ.get("DIAGNOSIS_PATIENT_LOOKUP") != "1":
        # Lookup disabled by default: keep the free-text identity, never
        # call the registry. The self-check + offline tests rely on this
        # short; production opts INTO real lookup via the env.
        c = code.strip()
        return Patient(id=c, patient_code=c, display_name=c)

    try:
        payload = _fetch_patient(code.strip(), cookie_header)
    except _PatientNotFound:
        raise HTTPException(
            status_code=422,
            detail=f"Unknown patient code: {code!r}",
        )
    except _PatientUnavailable:
        # Registry down / malformed response. Fail closed: do not silently
        # write a row with a free-text id — surface the same 422 the
        # unknown-patient path returns, without leaking the transport error.
        raise HTTPException(
            status_code=422,
            detail=f"Patient registry unavailable for code {code!r}",
        )
    return _build_patient(payload, code.strip())


def reset_patient_for_tests(base_url: str | None = None) -> None:
    """Test-only hook: rebind the patient-registry base URL for the
    lifetime of the current process. Production code never needs this —
    it reads ``PATIENT_BASE_URL`` at import time.

    Exposed because we deliberately avoid global mutable state in
    production. Tests that mount a fake registry call this once in setup,
    then restore by passing ``None`` (which falls back to the settings-
    adapter value captured at import).
    """
    global PATIENT_BASE_URL
    if base_url is not None:
        PATIENT_BASE_URL = base_url
    else:
        PATIENT_BASE_URL = settings.patient_url


__all__ = [
    "Patient",
    "resolve_patient",
    "reset_patient_for_tests",
    "PATIENT_BASE_URL",
    "validate_patient_encounter",
]


# --- ponytail: one runnable self-check. No framework. Fail = bug. ---------
def _patient_selfcheck() -> None:
    """Self-verify the identity adapter without a live registry. Covers:
    - empty code -> 400
    - lookup disabled (default) -> returns Patient(id=code=code=code)
    - _build_patient rejects a missing canonical id
    - _build_patient accepts a payload with only id and falls back the
      patient_code to the supplied free-text code
    - _build_patient passes display_name through and tolerates None /
      non-str display_name
    Run: ``python -m diagnosis.patient``
    """
    from fastapi import HTTPException

    # 1. Empty code -> 400 regardless of the lookup env.
    os.environ.pop("DIAGNOSIS_PATIENT_LOOKUP", None)
    try:
        resolve_patient("", None)
        raise AssertionError("empty code should 400")
    except HTTPException as e:
        assert e.status_code == 400, e

    # 2. Lookup disabled (default) -> identity built from the code itself.
    p = resolve_patient("P-SELF", None)
    assert p.id == "P-SELF" and p.patient_code == "P-SELF", p
    assert p.display_name == "P-SELF", p

    # 3. _build_patient fails closed on a missing canonical id.
    try:
        _build_patient({"patient_code": "x", "display_name": "y"}, "x")
        raise AssertionError("missing id should 422")
    except HTTPException as e:
        assert e.status_code == 422 and "no canonical id" in e.detail, e

    # 4. _build_patient: canonical id is authoritative, patient_code
    #    falls back to the supplied free-text code when the payload omits it.
    p = _build_patient({"id": "pid-9"}, "P-LOOKUP")
    assert p.id == "pid-9" and p.patient_code == "P-LOOKUP", p
    assert p.display_name is None, p

    # 5. display_name passes through when present, None tolerated, and a
    #    non-str display_name (e.g. a registry bug) collapses to None.
    assert _build_patient({"id": "1", "display_name": "Ada"}, "c").display_name == "Ada"
    assert _build_patient({"id": "1", "display_name": None}, "c").display_name is None
    assert _build_patient({"id": "1", "display_name": 42}, "c").display_name is None

    print("OK: diagnosis patient adapter self-check passed")


if __name__ == "__main__":
    _patient_selfcheck()
