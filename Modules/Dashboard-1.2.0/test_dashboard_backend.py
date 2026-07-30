from __future__ import annotations

import json
import os
import socket
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

PSYCHIATRIST_ID = "f2af6c59-6856-4dcc-bcf6-8569e009d58b"
ADMIN_ID = "68f577d0-8d3f-46c7-bd8a-4396350a6454"
AUTH_SESSION_ID = "720705d7-97bc-4d40-a4ac-59bdfcc65501"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class MockAuthenticationServer:
    def __init__(self) -> None:
        self.payloads: dict[str, tuple[int, dict]] = {}
        self.requests: list[dict[str, str]] = []

    def set_payload(self, session_id: str, payload: dict, status: int = 200) -> None:
        self.payloads[session_id] = (status, payload)
        provider_session_id = payload.get("session", {}).get("id")
        if provider_session_id:
            self.payloads[provider_session_id] = (status, payload)

    def __enter__(self) -> "MockAuthenticationServer":
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                token = self.headers.get("x-auth-session") or self.headers.get("x-auth-session-id") or ""
                owner.requests.append({"path": self.path, "x-auth-session": token})
                status, payload = owner.payloads.get(token, (401, {"authenticated": False}))
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("content-type", "application/json")
                if 200 <= status < 300:
                    self.send_header("x-schema-version", "2.0.0")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_: object) -> None:
                return

        self.port = free_port()
        self.server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.port}/api/auth/v2/session"
        return self

    def __exit__(self, *_: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


class DashboardServer:
    def __init__(self, auth_session_url: str | None = None) -> None:
        self.auth_session_url = auth_session_url

    def __enter__(self) -> str:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tempdir.name, "dashboard.sqlite3")
        os.environ["DASHBOARD_DB_PATH"] = self.db_path
        if self.auth_session_url:
            os.environ["AUTH_SESSION_URL"] = self.auth_session_url
            os.environ["DASHBOARD_MOCK_AUTH"] = "0"
        else:
            os.environ.pop("AUTH_SESSION_URL", None)
            os.environ.pop("DASHBOARD_MOCK_AUTH", None)
        os.environ.pop("AUTH_BASE_URL", None)
        for name in list(sys.modules):
            if name == "dashboard_backend" or name.startswith("dashboard_backend."):
                del sys.modules[name]

        import uvicorn
        from dashboard_backend.main import app

        self.port = free_port()
        self.config = uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="error")
        self.server = uvicorn.Server(self.config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()

        base = f"http://127.0.0.1:{self.port}"
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                request_json(base, "/healthz")
                return base
            except Exception:
                time.sleep(0.05)
        raise RuntimeError("server did not start")

    def __exit__(self, *_: object) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=5)
        self.tempdir.cleanup()


def request_json(base: str, path: str, method: str = "GET", headers: dict[str, str] | None = None, body: dict | None = None) -> tuple[int, dict]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = Request(
        f"{base}{path}",
        data=data,
        method=method,
        headers={"content-type": "application/json", **(headers or {})},
    )
    try:
        with urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        try:
            payload = json.loads(error.read().decode("utf-8"))
        finally:
            if error.fp:
                error.fp.close()
            error.close()
        return error.code, payload


def create_session(base: str, user_id: str) -> dict:
    status, data = request_json(
        base,
        "/internal/dashboard/session",
        method="POST",
        headers={"x-demo-auth-user": user_id},
        body={"device": "Test"},
    )
    assert status == 201
    return data


def future_iso() -> str:
    return (datetime.now(UTC) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")


def auth_payload(**overrides: dict) -> dict:
    payload = {
        "authenticated": True,
        "authorized": True,
        "interfaceVersion": "2.0.0",
        "session": {"id": AUTH_SESSION_ID, "active": True, "expiresAt": future_iso()},
        "user": {
            "id": PSYCHIATRIST_ID,
            "username": "Verified Clinician",
            "role": "psychiatrist",
        },
        "gates": {
            "passwordChangeRequired": False,
            "disclaimerRequired": False,
            "disclaimerVersion": "2026-07-06",
        },
        "compatibility": {"legacyUserId": 2, "legacyRole": "user"},
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(payload.get(key), dict):
            payload[key] = {**payload[key], **value}
        else:
            payload[key] = value
    return payload


class AuthSessionNormalizationTest(unittest.TestCase):
    def test_auth_identity_requires_verified_session_and_derives_profile(self) -> None:
        from dashboard_backend.auth import normalize_auth_identity

        identity = normalize_auth_identity(auth_payload())

        self.assertIsNotNone(identity)
        assert identity is not None
        self.assertEqual(identity["authSessionId"], AUTH_SESSION_ID)
        self.assertEqual(identity["user"]["id"], PSYCHIATRIST_ID)
        self.assertEqual(identity["user"]["role"], "PSYCHIATRIST")
        self.assertEqual(identity["user"]["fullName"], "Verified Clinician")

    def test_auth_identity_rejects_missing_and_blocked_sessions(self) -> None:
        from dashboard_backend.auth import normalize_auth_identity

        blocked_payloads = [
            auth_payload(session=None),
            auth_payload(authenticated=False),
            auth_payload(authorized=False),
            auth_payload(interfaceVersion="1.0.0"),
            auth_payload(session={"active": False}),
            auth_payload(session={"expiresAt": "2000-01-01T00:00:00Z"}),
            auth_payload(session={"expiresAt": future_iso().replace("Z", "+00:00")}),
            auth_payload(gates={"passwordChangeRequired": True}),
            auth_payload(gates={"disclaimerRequired": True}),
            auth_payload(user={"role": "PSYCHIATRIST"}),
            auth_payload(user={"id": "legacy-user-id"}),
        ]
        for payload in blocked_payloads:
            with self.subTest(payload=payload):
                self.assertIsNone(normalize_auth_identity(payload))


class DashboardBackendTest(unittest.TestCase):
    def test_health_and_readiness(self) -> None:
        with DashboardServer() as base:
            self.assertEqual(request_json(base, "/healthz")[0], 200)
            self.assertEqual(request_json(base, "/readyz")[0], 200)

    def test_dataset_schema_keeps_only_dashboard_owned_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tempdir:
            db_path = os.path.join(tempdir, "dashboard.sqlite3")
            from dashboard_backend.db import SQLiteAdapter
            from dashboard_backend.repository import DashboardRepository

            DashboardRepository(SQLiteAdapter(db_path)).initialize()
            conn = sqlite3.connect(db_path)
            try:
                tables = {
                    row[0]
                    for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%'")
                }
            finally:
                conn.close()

        self.assertEqual(tables, {"dashboard_sessions", "workspace_events"})

    def test_dashboard_creates_sessions_from_authentication_identity_not_body_identity(self) -> None:
        with DashboardServer() as base:
            status, created = request_json(
                base,
                "/internal/dashboard/session",
                method="POST",
                headers={"x-demo-auth-user": "psy-1"},
                body={"userId": "admin-1", "role": "ADMIN", "fullName": "Spoofed Admin"},
            )

            self.assertEqual(status, 201)
            self.assertEqual(created["user"]["id"], PSYCHIATRIST_ID)
            self.assertEqual(created["user"]["role"], "PSYCHIATRIST")
            self.assertEqual(created["user"]["fullName"], "Mina Rahimi")

            status, workspace = request_json(base, f"/internal/dashboard/workspace?session={created['sessionId']}")
            self.assertEqual(status, 200)
            self.assertEqual(workspace["workspace"]["kind"], "PSYCHIATRIST")
            self.assertEqual(workspace["workspace"]["title"], "Workspace")

    def test_dashboard_refuses_activation_without_authentication_session(self) -> None:
        with DashboardServer() as base:
            status, data = request_json(
                base,
                "/internal/dashboard/session",
                method="POST",
                body={"userId": "psy-1", "role": "PSYCHIATRIST"},
            )

            self.assertEqual(status, 401)
            self.assertEqual(data["error"], "authentication_session_required")

    def test_psychiatrist_workspace_model_has_exact_buttons_and_route_discovery(self) -> None:
        with DashboardServer() as base:
            created = create_session(base, "psy-1")
            status, workspace = request_json(base, f"/internal/dashboard/workspace?session={created['sessionId']}")

            self.assertEqual(status, 200)
            self.assertEqual(workspace["displayName"], "Dr. Mina Rahimi")
            self.assertEqual(workspace["user"]["displayName"], "Dr. Mina Rahimi")
            datetime.fromisoformat(workspace["currentDateTime"].replace("Z", "+00:00"))
            self.assertEqual(workspace["workspace"]["title"], "Workspace")
            self.assertEqual(
                [button["title"] for button in workspace["workspace"]["buttons"]],
                ["Add New Patient", "Patient Follow-up", "List of Patients", "Setting"],
            )
            self.assertNotIn("cards", workspace["workspace"])
            self.assertNotIn("patients", workspace)
            self.assertNotIn("drafts", workspace)
            self.assertNotIn("followUps", workspace)

            discovery = workspace["workspace"]["buttons"][0]["routeDiscovery"]
            self.assertEqual(discovery, {"method": "GET", "href": "/internal/dashboard/module-routes/add-new-patient"})
            status, route = request_json(base, discovery["href"], headers={"x-dashboard-session": created["sessionId"]})
            self.assertEqual(status, 200)
            self.assertEqual(route["href"], "/modules/add-new-patient")
            self.assertTrue(route["placeholder"])

    def test_admin_workspace_model_has_exact_buttons_only(self) -> None:
        with DashboardServer() as base:
            created = create_session(base, "admin-1")
            status, workspace = request_json(base, f"/internal/dashboard/workspace?session={created['sessionId']}")

            self.assertEqual(status, 200)
            self.assertEqual(workspace["displayName"], "Ari Morgan")
            datetime.fromisoformat(workspace["currentDateTime"].replace("Z", "+00:00"))
            self.assertEqual(workspace["workspace"]["title"], "Workspace")
            self.assertEqual(
                [button["title"] for button in workspace["workspace"]["buttons"]],
                ["Add New User", "Logs", "Backup", "List of Users"],
            )
            self.assertNotIn("cards", workspace["workspace"])
            self.assertNotIn("oversight", workspace)
            self.assertNotIn("guidelineRevisions", json.dumps(workspace))
            self.assertNotIn("Bayesian", json.dumps(workspace))
            self.assertNotIn("Admin oversight", json.dumps(workspace))

    def test_module_routes_are_role_scoped_placeholders(self) -> None:
        with DashboardServer() as base:
            admin = create_session(base, "admin-1")
            status, route = request_json(base, "/internal/dashboard/module-routes/logs", headers={"x-dashboard-session": admin["sessionId"]})
            self.assertEqual(status, 200)
            self.assertEqual(route["title"], "Logs")
            self.assertEqual(route["href"], "/modules/logs")
            self.assertTrue(route["placeholder"])

            psychiatrist = create_session(base, "psy-1")
            status, data = request_json(base, "/internal/dashboard/module-routes/logs", headers={"x-dashboard-session": psychiatrist["sessionId"]})
            self.assertEqual(status, 404)
            self.assertEqual(data["error"], "module_route_not_available")

    def test_dashboard_does_not_own_patient_mutation_endpoint(self) -> None:
        with DashboardServer() as base:
            created = create_session(base, "psy-1")
            status, _ = request_json(
                base,
                "/internal/dashboard/patients",
                method="POST",
                headers={"x-dashboard-session": created["sessionId"]},
                body={"name": "Boundary Patient"},
            )

            self.assertEqual(status, 404)

    def test_signed_out_dashboard_sessions_stop_workspace_access(self) -> None:
        with DashboardServer() as base:
            created = create_session(base, "admin-1")
            status, _ = request_json(
                base,
                "/internal/dashboard/session",
                method="DELETE",
                headers={"x-dashboard-session": created["sessionId"]},
            )
            self.assertEqual(status, 200)

            status, data = request_json(base, f"/internal/dashboard/workspace?session={created['sessionId']}")
            self.assertEqual(status, 401)
            self.assertEqual(data["error"], "dashboard_session_required")

    def test_contract_uses_mocked_authentication_session_endpoint(self) -> None:
        with MockAuthenticationServer() as auth:
            auth.set_payload(
                "auth-psy",
                auth_payload(
                    session={"id": AUTH_SESSION_ID},
                    user={"id": PSYCHIATRIST_ID, "username": "Verified Clinician"},
                ),
            )
            with DashboardServer(auth.url) as base:
                status, created = request_json(
                    base,
                    "/internal/dashboard/session",
                    method="POST",
                    headers={"x-auth-session": "auth-psy"},
                    body={"userId": "admin-1", "role": "ADMIN", "fullName": "Spoofed Admin"},
                )
                self.assertEqual(status, 201)
                self.assertEqual(created["user"]["id"], PSYCHIATRIST_ID)
                self.assertEqual(created["user"]["role"], "PSYCHIATRIST")

                status, workspace = request_json(base, f"/internal/dashboard/workspace?session={created['sessionId']}")
                self.assertEqual(status, 200)
                self.assertEqual(workspace["displayName"], "Dr. Verified Clinician")

        self.assertTrue(auth.requests)
        self.assertEqual({request["path"] for request in auth.requests}, {"/api/auth/v2/session"})
        self.assertIn("auth-psy", [request["x-auth-session"] for request in auth.requests])

    def test_invalid_auth_session_returns_401(self) -> None:
        with MockAuthenticationServer() as auth:
            with DashboardServer(auth.url) as base:
                status, data = request_json(
                    base,
                    "/internal/dashboard/session",
                    method="POST",
                    headers={"x-auth-session": "missing"},
                )

            self.assertEqual(status, 401)
            self.assertEqual(data["error"], "authentication_session_required")

    def test_session_expiry_is_enforced_after_dashboard_session_creation(self) -> None:
        with MockAuthenticationServer() as auth:
            auth.set_payload("auth-psy", auth_payload(session={"id": AUTH_SESSION_ID, "expiresAt": future_iso()}))
            with DashboardServer(auth.url) as base:
                status, created = request_json(
                    base,
                    "/internal/dashboard/session",
                    method="POST",
                    headers={"x-auth-session": "auth-psy"},
                )
                self.assertEqual(status, 201)

                auth.set_payload("auth-psy", auth_payload(session={"id": AUTH_SESSION_ID, "expiresAt": "2000-01-01T00:00:00Z"}))
                status, data = request_json(base, f"/internal/dashboard/workspace?session={created['sessionId']}")

            self.assertEqual(status, 401)
            self.assertEqual(data["error"], "authentication_session_required")

    def test_auth_revocation_is_immediate_after_dashboard_session_creation(self) -> None:
        with MockAuthenticationServer() as auth:
            auth.set_payload("auth-psy", auth_payload())
            with DashboardServer(auth.url) as base:
                status, created = request_json(
                    base,
                    "/internal/dashboard/session",
                    method="POST",
                    headers={"x-auth-session": "auth-psy"},
                )
                self.assertEqual(status, 201)

                auth.set_payload("auth-psy", auth_payload(authenticated=False), status=401)
                status, data = request_json(
                    base,
                    f"/internal/dashboard/workspace?session={created['sessionId']}",
                )

            self.assertEqual(status, 401)
            self.assertEqual(data["error"], "authentication_session_required")

    def test_auth_role_change_is_not_spoofable_by_request_body(self) -> None:
        with MockAuthenticationServer() as auth:
            auth.set_payload(
                "auth-admin",
                auth_payload(
                    session={"id": AUTH_SESSION_ID},
                    user={"id": ADMIN_ID, "role": "admin", "username": "Verified Admin"},
                    compatibility={"legacyUserId": 1, "legacyRole": None},
                ),
            )
            with DashboardServer(auth.url) as base:
                status, created = request_json(
                    base,
                    "/internal/dashboard/session",
                    method="POST",
                    headers={"x-auth-session": "auth-admin"},
                    body={"role": "PSYCHIATRIST", "fullName": "Spoofed Doctor"},
                )
                self.assertEqual(status, 201)
                self.assertEqual(created["user"]["role"], "ADMIN")

                status, workspace = request_json(base, f"/internal/dashboard/workspace?session={created['sessionId']}")
                self.assertEqual(status, 200)
                self.assertEqual(workspace["workspace"]["kind"], "ADMIN")
                self.assertEqual(
                    [button["title"] for button in workspace["workspace"]["buttons"]],
                    ["Add New User", "Logs", "Backup", "List of Users"],
                )


if __name__ == "__main__":
    unittest.main()

