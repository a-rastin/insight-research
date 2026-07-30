"""Module-local health/readiness probe for the diagnosis module.

Liveness (``/health`` -> ``{"ok": True}``) only answers "is the process
up?". Readiness (``/ready``) answers "are this module's dependencies
configured + reachable so we can actually serve clinical traffic?".

The check is **module-local** and **never leaks secrets**:

- *DB* — we own a SQLite ``DiagnosisStore`` that the route handlers write
  clinical state through. We probe it with a ``SELECT 1`` on the same
  lazily opened connection ``store.py`` reuses (read from ``deps.store``
  at call time so the swap in the self-check / multi-deploy tests is
  honoured), so readiness reflects the live adapter the next request
  will hit, not a throwaway handle.
- *Auth* — we delegate trust to the Insight auth service via
  ``AUTH_BASE_URL``. We do NOT call it here: it sits behind the same
  ``Cookie`` the user sends, so calling it without one would either 401
  (false negative during a clean deploy) or leak the configured base URL
  / transport details to the caller. We only verify the module is
  *configured* to delegate (base URL resolves to a non-empty string) and
  the bypass shim is off — configuration shape, never the secret itself.
  The base URL value is deliberately NOT echoed in the response so an
  internal host name or IP is not surfaced to a caller.
- *Patient* — the patient identity adapter is opt-in via
  ``DIAGNOSIS_PATIENT_LOOKUP``. When disabled (default) the readiness
  state is "skipped" (the adapter short-circuits and never contacts the
  registry). When enabled we verify ``PATIENT_BASE_URL`` resolves to a
  non-empty string — same no-leak rule as Auth.

Response shape (stable; do not drop keys without coordinating with the
larger Insight app's readiness aggregator):

    {
      "ok":        bool,             # AND of every check's ok
      "module":    "diagnosis",
      "checks":    {
          "db":      {"ok": bool},
          "auth":    {"ok": bool, "configured": bool, "bypass": bool},
          "patient": {"ok": bool, "enabled": bool, "configured": bool}
      }
    }

``bypass`` on the auth check is ``True`` when
``DIAGNOSIS_AUTH_BYPASS=1`` is set — the shim that shorts both the role
dependency and the CSRF gate for the in-process self-check. Surfacing
it here lets a deployment readiness gate fail loud when the bypass
shim is left on in production, without the readiness response itself
ever disclosing the auth-service URL.

A check the deploy operator can fly against this:

    curl /ready -> 200 + {"ok": true}                      -> serve traffic
    curl /ready -> 503 + {"ok": false, <which check>}      -> hold traffic

The HTTP route is in ``app.py`` (standalone mode); when mounted inside
the larger Insight app the parent app composes ``check_readiness()`` into
its own aggregator. See ``__init__.py`` for the lazy re-export.
"""
from __future__ import annotations

import os
from typing import Any


def _check_db() -> dict[str, Any]:
    """Probe the process-wide ``DiagnosisStore``. Imports the store from
    ``deps`` at call time so a swap (self-check / multi-deploy test) is
    honoured. Uses the same lazily opened connection the route handlers
    reuse, so readiness reflects the live adapter the next request will
    hit — not a throwaway handle that would hide a stuck connection."""
    from .deps import store
    try:
        with store._cursor() as cur:
            cur.execute("SELECT 1")
            row = cur.fetchone()
        ok = row is not None and row[0] == 1
    except Exception:
        # Any SQLite fault -> not ready. Do not surface the error
        # message: it can carry the on-disk DB path (PII-adjacent in
        # multi-tenant deploys) and is operationally noisy. The operator
        # reads the uvicorn log for the traceback.
        ok = False
    return {"ok": ok}


def _check_auth() -> dict[str, Any]:
    """Auth-service configuration shape check. Never calls the auth
    service (no Cookie to forward -> would 401 and falsely report
    not-ready on a clean deploy), never echoes the configured base URL
    (would surface an internal host / IP to the caller)."""
    from . import auth as _auth
    raw = getattr(_auth, "AUTH_BASE_URL", "") or ""
    configured = (raw.strip() if isinstance(raw, str) else str(raw)) != ""
    bypass = os.environ.get("DIAGNOSIS_AUTH_BYPASS") == "1"
    # The module can only delegate safely when it's configured AND the
    # bypass shim is off. The bypass is for the in-process self-check /
    # offline tests only; production readiness MUST report it as False.
    ok = configured and not bypass
    return {"ok": ok, "configured": configured, "bypass": bypass}


def _check_patient() -> dict[str, Any]:
    """Patient-identity adapter configuration check. The adapter is
    opt-in; "disabled" is a valid, healthy state for offline tests and
    the self-check."""
    from . import patient as _patient
    enabled = os.environ.get("DIAGNOSIS_PATIENT_LOOKUP") == "1"
    if not enabled:
        # Adapter short-circuits -> the registry is never contacted,
        # so we do not need to verify its base URL. This is a clean
        # "skipped" state, not a fault.
        return {"ok": True, "enabled": False, "configured": True}
    raw = getattr(_patient, "PATIENT_BASE_URL", "") or ""
    configured = (raw.strip() if isinstance(raw, str) else str(raw)) != ""
    ok = configured
    return {"ok": ok, "enabled": True, "configured": configured}


def check_readiness() -> dict[str, Any]:
    """Return the module-local readiness snapshot. Pure: no HTTP, no
    env mutation, never raises. The HTTP route in ``app.py`` wraps this
    and sets the 200/503 status code based on ``ok``.
    """
    db = _check_db()
    auth = _check_auth()
    patient = _check_patient()
    ok = db["ok"] and auth["ok"] and patient["ok"]
    return {
        "ok": ok,
        "module": "diagnosis",
        "checks": {"db": db, "auth": auth, "patient": patient},
    }


__all__ = ["check_readiness"]


# --- ponytail: one runnable self-check. No framework. Fail = bug. ---------
def _readiness_selfcheck() -> None:
    """Self-verify the readiness probe without a live auth service or
    patient registry. Covers:
    - bypass off + lookup off (default) -> ok=True, every check shape
      present, auth.bypass False, patient.enabled False, DB ok
    - bypass on -> auth.ok False + auth.bypass True (the deploy alarm
      that would block production traffic), aggregator ok False
    - lookup on + PATIENT_BASE_URL set -> patient.ok/enabled/configured
      all True
    - lookup on + PATIENT_BASE_URL blank -> patient.ok False +
      configured False, aggregator ok False
    - DB unreachable maps to db.ok False without raising

    Run: ``python -m diagnosis.readiness``
    """
    import shutil
    import tempfile
    import os as _os

    from . import deps as _deps
    from . import patient as _patient
    from .store import DiagnosisStore

    # Snapshot the env we mutate so the process exits clean for the
    # next test in the same interpreter (mirrors test_patient.py).
    saved_bypass = _os.environ.get("DIAGNOSIS_AUTH_BYPASS")
    saved_lookup = _os.environ.get("DIAGNOSIS_PATIENT_LOOKUP")
    saved_patient_url = _patient.PATIENT_BASE_URL

    fd, db_path = tempfile.mkstemp(prefix="diagnosis_ready_test_", suffix=".db")
    _os.close(fd)
    backup_store = _deps.store
    tmp_store: DiagnosisStore | None = None
    try:
        # 1. Default env: bypass off + lookup off. Swap the module-level
        #    store for a fresh temp-backed one so we exercise a live
        #    ``SELECT 1`` without touching ``diagnosis_store.db``.
        _os.environ.pop("DIAGNOSIS_AUTH_BYPASS", None)
        _os.environ.pop("DIAGNOSIS_PATIENT_LOOKUP", None)
        tmp_store = DiagnosisStore(db_path)
        _deps.store = tmp_store

        r = check_readiness()
        assert r["module"] == "diagnosis", r
        assert r["ok"] is True, ("default env should be ready", r)
        assert r["checks"]["db"]["ok"] is True, r
        assert r["checks"]["auth"]["configured"] is True, r
        assert r["checks"]["auth"]["bypass"] is False, r
        assert r["checks"]["auth"]["ok"] is True, r
        assert r["checks"]["patient"]["enabled"] is False, r
        assert r["checks"]["patient"]["configured"] is True, r
        assert r["checks"]["patient"]["ok"] is True, r

        # 2. Bypass shim on -> auth not deploy-ready; aggregator
        #    must go False so the deploy gate holds traffic.
        _os.environ["DIAGNOSIS_AUTH_BYPASS"] = "1"
        try:
            r = check_readiness()
            assert r["checks"]["auth"]["bypass"] is True, r
            assert r["checks"]["auth"]["ok"] is False, r
            assert r["ok"] is False, ("bypass must fail readiness", r)
        finally:
            _os.environ.pop("DIAGNOSIS_AUTH_BYPASS", None)

        # 3. Patient lookup enabled with PATIENT_BASE_URL set -> ready.
        #    Loopback base URL so we never touch the network;
        #    readiness only inspects the configured value.
        _os.environ["DIAGNOSIS_PATIENT_LOOKUP"] = "1"
        _patient.PATIENT_BASE_URL = "http://127.0.0.1:9000"
        try:
            r = check_readiness()
            assert r["checks"]["patient"]["enabled"] is True, r
            assert r["checks"]["patient"]["configured"] is True, r
            assert r["checks"]["patient"]["ok"] is True, r
            assert r["ok"] is True, r
        finally:
            _patient.PATIENT_BASE_URL = saved_patient_url
            _os.environ.pop("DIAGNOSIS_PATIENT_LOOKUP", None)

        # 4. Patient lookup enabled but PATIENT_BASE_URL blank ->
        #    configured False, ok False, aggregator False.
        _os.environ["DIAGNOSIS_PATIENT_LOOKUP"] = "1"
        _patient.PATIENT_BASE_URL = ""
        try:
            r = check_readiness()
            assert r["checks"]["patient"]["enabled"] is True, r
            assert r["checks"]["patient"]["configured"] is False, r
            assert r["checks"]["patient"]["ok"] is False, r
            assert r["ok"] is False, r
        finally:
            _patient.PATIENT_BASE_URL = saved_patient_url
            _os.environ.pop("DIAGNOSIS_PATIENT_LOOKUP", None)

        # 5. DB unreachable maps to db.ok False without raising.
        #    Close the live connection then point the adapter's path
        #    at a directory (SQLite cannot open a directory as a DB)
        #    so reopening faults deterministically across platforms.
        if tmp_store._conn is not None:
            try:
                tmp_store._conn.close()
            except Exception:
                pass
            tmp_store._conn = None
        tmp_store.path = db_path + ".dir"
        _os.makedirs(tmp_store.path, exist_ok=True)
        r = check_readiness()
        assert r["checks"]["db"]["ok"] is False, ("DB fault should be False", r)
        assert r["ok"] is False, ("DB fault should fail readiness", r)
    finally:
        # Restore the global store + env so the next test in the same
        # process sees the original wiring.
        _deps.store = backup_store
        if saved_bypass is None:
            _os.environ.pop("DIAGNOSIS_AUTH_BYPASS", None)
        else:
            _os.environ["DIAGNOSIS_AUTH_BYPASS"] = saved_bypass
        if saved_lookup is None:
            _os.environ.pop("DIAGNOSIS_PATIENT_LOOKUP", None)
        else:
            _os.environ["DIAGNOSIS_PATIENT_LOOKUP"] = saved_lookup
        _patient.PATIENT_BASE_URL = saved_patient_url

        # Clean up the temp DB file + the dir we created for the fault
        # case. Best-effort: do not raise on cleanup.
        if tmp_store is not None and tmp_store._conn is not None:
            try:
                tmp_store._conn.close()
            except Exception:
                pass
        shutil.rmtree(db_path + ".dir", ignore_errors=True)
        try:
            _os.remove(db_path)
        except OSError:
            pass

    print("OK: diagnosis readiness self-check passed")


if __name__ == "__main__":
    _readiness_selfcheck()
