"""Dashboard discovery-route tests for the diagnosis module.

Mirrors the ``test_auth.py`` / ``test_csrf.py`` strategy: stand up a tiny
in-process HTTP server that mimics the Insight auth service so we can
exercise the real role dependency (no env bypass) against the new
``GET /internal/dashboard/module-routes/{moduleId}`` endpoint.

Covers:
  - happy path: psychiatrist/admind cookie -> 200 + descriptor shape;
  - unknown moduleId -> 404 (clean, no stack trace);
  - non-canonical role (nurse) -> 401 fail-closed;
  - no cookie at all -> 401 (auth fail-closed before we answer).

Run: ``python -m test_discovery`` — no test framework, ponytail style.
"""
from __future__ import annotations

import json
import os
import socket
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

# Make the diagnosis package importable regardless of cwd.
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

# Force the auth bypass off — we want to exercise the real dependency.
os.environ.pop("DIAGNOSIS_AUTH_BYPASS", None)

from fastapi.testclient import TestClient

from diagnosis import auth as diag_auth
from diagnosis.app import app


# ---------------------------------------------------------------------------
# Fake auth service — role selected by the ``as`` query param on the Cookie.

SCENARIOS = {
    "psychiatrist": {
        "authenticated": True,
        "authorized": True, "interfaceVersion": "2.0.0",
        "session": {"id": "11111111-1111-4111-8111-111111111111", "active": True, "expiresAt": "2999-01-01T00:00:00Z"},
        "user": {"id": "22222222-2222-4222-8222-222222222222", "username": "psy", "role": "psychiatrist"},
        "gates": {"passwordChangeRequired": False, "disclaimerRequired": False, "disclaimerVersion": "test-v1"},
    },
    "admin": {
        "authenticated": True,
        "authorized": True, "interfaceVersion": "2.0.0",
        "session": {"id": "33333333-3333-4333-8333-333333333333", "active": True, "expiresAt": "2999-01-01T00:00:00Z"},
        "user": {"id": "44444444-4444-4444-8444-444444444444", "username": "admin", "role": "admin"},
        "gates": {"passwordChangeRequired": False, "disclaimerRequired": False, "disclaimerVersion": "test-v1"},
    },
    "nurse": {
        "authenticated": True,
        "authorized": True, "interfaceVersion": "2.0.0",
        "session": {"id": "55555555-5555-4555-8555-555555555555", "active": True, "expiresAt": "2999-01-01T00:00:00Z"},
        "user": {"id": "66666666-6666-4666-8666-666666666666", "username": "nurse", "role": "nurse"},
        "gates": {"passwordChangeRequired": False, "disclaimerRequired": False, "disclaimerVersion": "test-v1"},
    },
}


class _Handler(BaseHTTPRequestHandler):
    # Role carried in the Cookie value, e.g. ``insight_session=psychiatrist``.
    def log_message(self, *_args):
        return

    def do_GET(self):  # noqa: N802
        cookie = self.headers.get("cookie", "") or ""
        role = None
        for chunk in cookie.split(";"):
            chunk = chunk.strip()
            if chunk.startswith("insight_session="):
                role = chunk.split("=", 1)[1] or None
        # No insight_session cookie at all -> the auth service treats the
        # caller as unauthenticated (mirrors the real Insight contract).
        if role is None:
            payload = {"authenticated": False}
        else:
            payload = SCENARIOS.get(role, SCENARIOS["nurse"])
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("X-Schema-Version", "2.0.0")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _start_fake_auth() -> tuple[HTTPServer, int]:
    port = _free_port()
    httpd = HTTPServer(("127.0.0.1", port), _Handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    return httpd, port


def _client(port: int, role: str) -> TestClient:
    diag_auth.AUTH_BASE_URL = f"http://127.0.0.1:{port}"
    return TestClient(app, cookies={"insight_session": role})


DISCOVERY = "/internal/dashboard/module-routes/diagnosis"


# ---------------------------------------------------------------------------
# Tests

def test_descriptor_shape_and_launch_href(port: int):
    c = _client(port, "psychiatrist")
    r = c.get(DISCOVERY)
    assert r.status_code == 200, ("psychiatrist discovery not 200", r.status_code, r.text)
    d = r.json()
    assert d["moduleId"] == "diagnosis", d
    assert d["launch"]["href"] == "/modules/diagnosis", d
    assert d["title"] == "Diagnosis", d
    assert "self" in d["routes"] and d["routes"]["self"] == "/diagnosis/_meta", d
    assert d["routes"]["csrf"] == "/diagnosis/_csrf", d
    assert d["routes"]["session"] == "/diagnosis/{code}", d


def test_admin_can_read_discovery(port: int):
    c = _client(port, "admin")
    r = c.get(DISCOVERY)
    assert r.status_code == 200, ("admin discovery not 200", r.status_code, r.text)


def test_unknown_module_id_returns_404(port: int):
    c = _client(port, "psychiatrist")
    r = c.get("/internal/dashboard/module-routes/not-a-module")
    assert r.status_code == 404, ("unknown moduleId should be 404", r.status_code, r.text)
    # detail must be a clean string — no stack trace leak.
    assert "detail" in r.json() and r.json()["detail"] == "Unknown module id", r.text


def test_nurse_role_is_401(port: int):
    c = _client(port, "nurse")
    r = c.get(DISCOVERY)
    assert r.status_code == 401, ("non-canonical role should fail closed", r.status_code, r.text)


def test_no_cookie_returns_401(port: int):
    diag_auth.AUTH_BASE_URL = f"http://127.0.0.1:{port}"
    # Fresh client with no cookies at all -> auth dep fails closed.
    c = TestClient(app)
    r = c.get(DISCOVERY)
    assert r.status_code == 401, ("no cookie should be 401", r.status_code, r.text)


def main() -> None:
    httpd, port = _start_fake_auth()
    failures = []
    cases = [
        ("test_descriptor_shape_and_launch_href",
         lambda: test_descriptor_shape_and_launch_href(port)),
        ("test_admin_can_read_discovery",
         lambda: test_admin_can_read_discovery(port)),
        ("test_unknown_module_id_returns_404",
         lambda: test_unknown_module_id_returns_404(port)),
        ("test_nurse_role_is_401",
         lambda: test_nurse_role_is_401(port)),
        ("test_no_cookie_returns_401",
         lambda: test_no_cookie_returns_401(port)),
    ]
    for name, fn in cases:
        try:
            fn()
            print(f"PASS  {name}")
        except AssertionError as e:
            failures.append((name, repr(e)))
            print(f"FAIL  {name}: {e}")
    httpd.shutdown()
    if failures:
        print(f"\n{len(failures)}/{len(cases)} FAILED")
        sys.exit(1)
    print(f"\nOK: {len(cases)}/{len(cases)} discovery tests passed")


if __name__ == "__main__":
    main()
