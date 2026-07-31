"""Readiness-probe tests for the diagnosis module.

Strategy:
    - Exercise the pure ``check_readiness()`` function directly (no HTTP
      round-trip needed) under every env permutation the probe branches
      on. Covers the default env, the bypass-shim alarm, the patient
      lookup enabled/disabled + configured/blank paths, and a DB fault
      that must collapse to ``db.ok=False`` without raising.
    - Exercise the HTTP route too: ``GET /ready`` must be 200 when the
      module is ready and 503 when any check fails, and the body must
      carry the ``checks`` map so the operator sees which check went
      False without a stack trace. A no-leak assertion scans the body
      for any auth / patient base URL string so the probe does not
      surface internal host names / IPs to the caller.

Run: ``python -m test_readiness`` — no test framework, ponytail style.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Make the diagnosis package importable regardless of cwd.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from fastapi.testclient import TestClient

from diagnosis import auth as diag_auth
from diagnosis import deps as diag_deps
from diagnosis import patient as diag_patient
from diagnosis.app import app
from diagnosis.readiness import check_readiness
from diagnosis.store import DiagnosisStore


# ---------------------------------------------------------------------------
# Tests against the pure function.
# Each case snapshots + restores the env the probe branches on so the
# process exits clean for the next test in the same interpreter.


def test_default_env_is_ready(tmpdb):
    _set_env(bypass=None, lookup=None, patient_url="http://localhost:9000")
    _swap_store(tmpdb)
    try:
        r = check_readiness()
        assert r["module"] == "diagnosis", r
        assert r["ok"] is True, r
        assert r["checks"]["db"]["ok"] is True, r
        assert r["checks"]["auth"]["ok"] is True, r
        assert r["checks"]["auth"]["configured"] is True, r
        assert r["checks"]["auth"]["bypass"] is False, r
        assert r["checks"]["patient"]["enabled"] is False, r
        assert r["checks"]["patient"]["configured"] is True, r
        assert r["checks"]["patient"]["ok"] is True, r
    finally:
        _restore_env()


def test_bypass_shim_fails_readiness(tmpdb):
    # Bypass is the self-check shim — production readiness MUST hold
    # traffic when it's left on. Surfaces as auth.bypass=True + ok=False
    # so a deploy gate can alarm on the flag name without the probe
    # disclosing the auth-service URL.
    _set_env(bypass="1", lookup=None, patient_url="http://localhost:9000")
    _swap_store(tmpdb)
    try:
        r = check_readiness()
        assert r["checks"]["auth"]["bypass"] is True, r
        assert r["checks"]["auth"]["ok"] is False, r
        assert r["ok"] is False, r
    finally:
        _restore_env()


def test_auth_base_url_blank_fails(tmpdb):
    _set_env(bypass=None, lookup=None, patient_url="http://localhost:9000")
    _swap_store(tmpdb)
    saved = diag_auth.AUTH_BASE_URL
    diag_auth.AUTH_BASE_URL = ""
    try:
        r = check_readiness()
        assert r["checks"]["auth"]["configured"] is False, r
        assert r["checks"]["auth"]["ok"] is False, r
        assert r["ok"] is False, r
    finally:
        diag_auth.AUTH_BASE_URL = saved
        _restore_env()


def test_patient_lookup_enabled_and_configured(tmpdb):
    _set_env(bypass=None, lookup="1", patient_url="http://127.0.0.1:9000")
    _swap_store(tmpdb)
    try:
        r = check_readiness()
        assert r["checks"]["patient"]["enabled"] is True, r
        assert r["checks"]["patient"]["configured"] is True, r
        assert r["checks"]["patient"]["ok"] is True, r
        assert r["ok"] is True, r
    finally:
        _restore_env()


def test_patient_lookup_enabled_blank_url_fails(tmpdb):
    _set_env(bypass=None, lookup="1", patient_url="")
    _swap_store(tmpdb)
    try:
        r = check_readiness()
        assert r["checks"]["patient"]["enabled"] is True, r
        assert r["checks"]["patient"]["configured"] is False, r
        assert r["checks"]["patient"]["ok"] is False, r
        assert r["ok"] is False, r
    finally:
        _restore_env()


def test_db_fault_is_false_without_raising(tmpdb):
    # Close the live connection then point the adapter's path at a
    # directory (SQLite cannot open a directory as a DB) so reopen
    # faults deterministically across platforms. The probe must swallow
    # the fault and report db.ok=False without raising.
    _set_env(bypass=None, lookup=None, patient_url="http://localhost:9000")
    _swap_store(tmpdb)
    _break_tmpdb(tmpdb)
    try:
        r = check_readiness()
        assert r["checks"]["db"]["ok"] is False, r
        assert r["ok"] is False, r
    finally:
        _heal_tmpdb(tmpdb)
        _restore_env()


def test_response_never_leaks_base_urls(tmpdb):
    # Operator-safety contract: readiness must NEVER echo AUTH_BASE_URL
    # or PATIENT_BASE_URL. Both can carry internal host names / IPs that
    # should not be surfaced to a caller. Set them to a recognisable
    # sentinel and assert neither string appears in the JSON response.
    sentinel_auth = "http://leak-test-auth.invalid:1234"
    sentinel_patient = "http://leak-test-patient.invalid:5678"
    _set_env(bypass=None, lookup="1", patient_url=sentinel_patient)
    diag_auth.AUTH_BASE_URL = sentinel_auth
    _swap_store(tmpdb)
    try:
        r = check_readiness()
        body = json.dumps(r, sort_keys=True)
        assert sentinel_auth not in body, ("auth URL leaked", body)
        assert sentinel_patient not in body, ("patient URL leaked", body)
        assert "leak-test" not in body, body
    finally:
        diag_auth.AUTH_BASE_URL = "http://localhost:9000"
        _restore_env()


# ---------------------------------------------------------------------------
# Tests against the HTTP route.


def test_http_ready_200_when_healthy(port, tmpdb):
    _set_env(bypass=None, lookup=None, patient_url="http://localhost:9000")
    _swap_store(tmpdb)
    try:
        c = TestClient(app)
        r = c.get("/ready")
        assert r.status_code == 200, (r.status_code, r.text)
        body = r.json()
        assert body["ok"] is True, body
        assert body["module"] == "diagnosis", body
        assert set(body["checks"].keys()) == {"db", "auth", "patient"}, body
    finally:
        _restore_env()


def test_http_ready_503_when_bypass_on(port, tmpdb):
    _set_env(bypass="1", lookup=None, patient_url="http://localhost:9000")
    _swap_store(tmpdb)
    try:
        c = TestClient(app)
        r = c.get("/ready")
        assert r.status_code == 503, (r.status_code, r.text)
        body = r.json()
        assert body["ok"] is False, body
        assert body["checks"]["auth"]["bypass"] is True, body
    finally:
        _restore_env()


def test_http_ready_503_when_db_down(port, tmpdb):
    _set_env(bypass=None, lookup=None, patient_url="http://localhost:9000")
    _swap_store(tmpdb)
    _break_tmpdb(tmpdb)
    try:
        c = TestClient(app)
        r = c.get("/ready")
        assert r.status_code == 503, (r.status_code, r.text)
        body = r.json()
        assert body["checks"]["db"]["ok"] is False, body
        assert body["ok"] is False, body
    finally:
        _heal_tmpdb(tmpdb)
        _restore_env()


def test_http_ready_body_no_url_leak(port, tmpdb):
    sentinel_auth = "http://leak-test-auth.invalid:1234"
    sentinel_patient = "http://leak-test-patient.invalid:5678"
    _set_env(bypass=None, lookup="1", patient_url=sentinel_patient)
    diag_auth.AUTH_BASE_URL = sentinel_auth
    _swap_store(tmpdb)
    try:
        c = TestClient(app)
        r = c.get("/ready")
        assert "leak-test" not in r.text, ("URL leaked in HTTP body", r.text)
    finally:
        diag_auth.AUTH_BASE_URL = "http://localhost:9000"
        _restore_env()


# ---------------------------------------------------------------------------
# Helpers


def _set_env(bypass, lookup, patient_url) -> None:
    """Snapshot is handled by ``_restore_env`` — this call just applies
    a fresh permutation. ``bypass`` / ``lookup`` are ``None`` to pop,
    or a string value to set."""
    if bypass is None:
        os.environ.pop("DIAGNOSIS_AUTH_BYPASS", None)
    else:
        os.environ["DIAGNOSIS_AUTH_BYPASS"] = bypass
    if lookup is None:
        os.environ.pop("DIAGNOSIS_PATIENT_LOOKUP", None)
    else:
        os.environ["DIAGNOSIS_PATIENT_LOOKUP"] = lookup
    diag_patient.PATIENT_BASE_URL = patient_url


def _restore_env() -> None:
    os.environ.pop("DIAGNOSIS_AUTH_BYPASS", None)
    os.environ.pop("DIAGNOSIS_PATIENT_LOOKUP", None)
    diag_patient.PATIENT_BASE_URL = "http://localhost:9000"
    diag_auth.AUTH_BASE_URL = "http://localhost:9000"


def _swap_store(s: DiagnosisStore) -> None:
    diag_deps.store = s


def _fresh_tmpdb() -> tuple[DiagnosisStore, str]:
    fd, path = tempfile.mkstemp(prefix="diagnosis_ready_test_", suffix=".db")
    os.close(fd)
    s = DiagnosisStore(path)
    s._orig_path = path  # type: ignore[attr-defined]
    return s, path


def _break_tmpdb(s: DiagnosisStore) -> None:
    """Force the store's next ``SELECT 1`` to fault deterministically by
    closing the connection and pointing the path at a directory (SQLite
    cannot open a directory as a DB). Pairs with ``_heal_tmpdb`` so the
    next test in the suite can reuse the same store object."""
    if s._conn is not None:
        try:
            s._conn.close()
        except Exception:
            pass
        s._conn = None
    s.path = s._orig_path + ".dir"  # type: ignore[attr-defined]
    os.makedirs(s.path, exist_ok=True)


def _heal_tmpdb(s: DiagnosisStore) -> None:
    """Undo ``_break_tmpdb``: drop the fault dir, point path back at the
    real temp DB file, and let ``_cursor`` reopen lazily on next use."""
    if s._conn is not None:
        try:
            s._conn.close()
        except Exception:
            pass
        s._conn = None
    shutil.rmtree(s._orig_path + ".dir", ignore_errors=True)  # type: ignore[attr-defined]
    s.path = s._orig_path  # type: ignore[attr-defined]


def _cleanup_tmpdb(s: DiagnosisStore | None, path: str) -> None:
    if s is not None and s._conn is not None:
        try:
            s._conn.close()
        except Exception:
            pass
    shutil.rmtree(path + ".dir", ignore_errors=True)
    try:
        os.remove(path)
    except OSError:
        pass


# A tiny fake auth server is still required for the HTTP-route tests so
# the bypass-off path does not fault on the real auth service (the
# endpoint never calls it during readiness, but other imports may). We
# run one for the suite to satisfy the conventional harness shape — the
# probe itself never contacts it.

class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        return

    def do_GET(self):  # noqa: N802
        body = json.dumps({
            "authenticated": True, "authorized": True, "interfaceVersion": "2.0.0",
            "session": {"id": "11111111-1111-4111-8111-111111111111", "active": True, "expiresAt": "2999-01-01T00:00:00Z"},
            "user": {"id": "22222222-2222-4222-8222-222222222222", "username": "psy", "role": "psychiatrist"},
            "gates": {"passwordChangeRequired": False, "disclaimerRequired": False, "disclaimerVersion": "test-v1"},
        }).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Schema-Version", "2.0.0")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _free_port() -> int:
    sk = socket.socket()
    sk.bind(("127.0.0.1", 0))
    port = sk.getsockname()[1]
    sk.close()
    return port


def _start_fake_auth() -> tuple[HTTPServer, int]:
    port = _free_port()
    httpd = HTTPServer(("127.0.0.1", port), _Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, port


def main() -> None:
    # Allocate one temp store for the whole suite + a fake auth server
    # for the HTTP route tests that bypass off (so other protected
    # imports don't fault on a dead auth service during the request).
    auth_httpd, auth_port = _start_fake_auth()
    diag_auth.AUTH_BASE_URL = f"http://127.0.0.1:{auth_port}"

    tmpdb, db_path = _fresh_tmpdb()
    backup_store = diag_deps.store
    diag_deps.store = tmpdb
    try:
        cases = [
            ("test_default_env_is_ready", lambda: test_default_env_is_ready(tmpdb)),
            ("test_bypass_shim_fails_readiness", lambda: test_bypass_shim_fails_readiness(tmpdb)),
            ("test_auth_base_url_blank_fails", lambda: test_auth_base_url_blank_fails(tmpdb)),
            ("test_patient_lookup_enabled_and_configured", lambda: test_patient_lookup_enabled_and_configured(tmpdb)),
            ("test_patient_lookup_enabled_blank_url_fails", lambda: test_patient_lookup_enabled_blank_url_fails(tmpdb)),
            ("test_db_fault_is_false_without_raising", lambda: test_db_fault_is_false_without_raising(tmpdb)),
            ("test_response_never_leaks_base_urls", lambda: test_response_never_leaks_base_urls(tmpdb)),
            ("test_http_ready_200_when_healthy", lambda: test_http_ready_200_when_healthy(auth_port, tmpdb)),
            ("test_http_ready_503_when_bypass_on", lambda: test_http_ready_503_when_bypass_on(auth_port, tmpdb)),
            ("test_http_ready_503_when_db_down", lambda: test_http_ready_503_when_db_down(auth_port, tmpdb)),
            ("test_http_ready_body_no_url_leak", lambda: test_http_ready_body_no_url_leak(auth_port, tmpdb)),
        ]
        failures = []
        for name, fn in cases:
            try:
                fn()
                print(f"PASS  {name}")
            except AssertionError as e:
                failures.append((name, repr(e)))
                print(f"FAIL  {name}: {e}")

        _cleanup_tmpdb(tmpdb, db_path)
        auth_httpd.shutdown()

        if failures:
            print(f"\n{len(failures)}/{len(cases)} FAILED")
            sys.exit(1)
        print(f"\nOK: {len(cases)}/{len(cases)} readiness tests passed")
    finally:
        diag_deps.store = backup_store
        _restore_env()


if __name__ == "__main__":
    main()
