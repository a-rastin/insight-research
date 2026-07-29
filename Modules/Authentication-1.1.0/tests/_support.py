import os
import sys
import tempfile
import unittest
import warnings

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

warnings.filterwarnings(
    "ignore",
    message="Using `httpx` with `starlette.testclient` is deprecated.*",
)

from starlette.testclient import TestClient

import main
import security


TEST_SECRET = "x" * 48


class AuthTestCase(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory(prefix="insight_auth_tests_")
        self.db_path = os.path.join(self._tmpdir.name, "auth.sqlite3")
        self._env_backup = {
            key: os.environ.get(key)
            for key in (
                "AUTH_DB_PATH",
                "AUTH_JWT_SECRET",
                "AUTH_ADMIN_USERNAME",
                "AUTH_ADMIN_PASSWORD",
                "AUTH_LOGIN_FAILURE_LIMIT",
                "AUTH_LOGIN_LOCKOUT_SECONDS",
                "AUTH_LOGIN_FAILURE_WINDOW_SECONDS",
            )
        }
        os.environ["AUTH_DB_PATH"] = self.db_path
        os.environ["AUTH_JWT_SECRET"] = TEST_SECRET
        os.environ["AUTH_ADMIN_USERNAME"] = "Admin"
        os.environ["AUTH_ADMIN_PASSWORD"] = "Admin"
        os.environ["AUTH_LOGIN_FAILURE_LIMIT"] = "3"
        os.environ["AUTH_LOGIN_LOCKOUT_SECONDS"] = "30"
        os.environ["AUTH_LOGIN_FAILURE_WINDOW_SECONDS"] = "300"
        self.reset_connection()

    def tearDown(self):
        self.reset_connection()
        for key, value in self._env_backup.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        self._tmpdir.cleanup()

    def reset_connection(self):
        if security._conn is not None:
            security._conn.close()
            security._conn = None

    def raw_client(self):
        return TestClient(main.app)

    def csrf_headers(self, client):
        response = client.get("/api/auth/csrf")
        self.assertEqual(response.status_code, 200)
        token = response.json()["csrf_token"]
        self.assertTrue(token)
        self.assertEqual(client.cookies.get(security.cfg("AUTH_CSRF_COOKIE_NAME")), token)
        return {security.cfg("AUTH_CSRF_HEADER_NAME"): token}

    def client(self):
        client = self.raw_client()
        csrf_headers = self.csrf_headers(client)
        original_post = client.post
        original_patch = client.patch

        def add_csrf(kwargs):
            headers = dict(csrf_headers)
            headers.update(kwargs.pop("headers", {}) or {})
            kwargs["headers"] = headers

        def post(url, *args, **kwargs):
            add_csrf(kwargs)
            return original_post(url, *args, **kwargs)

        def patch(url, *args, **kwargs):
            add_csrf(kwargs)
            return original_patch(url, *args, **kwargs)

        client.post = post
        client.patch = patch
        return client

    def client_with_session_token(self, token):
        client = self.raw_client()
        client.cookies.set(security.cfg("AUTH_COOKIE_NAME"), token)
        return client

    def login_admin(self):
        client = self.client()
        response = client.post(
            "/api/auth/login",
            json={"username": "Admin", "password": "Admin", "role": "admin"},
        )
        self.assertEqual(response.status_code, 200)
        return client


def assert_auth_schema(testcase, conn):
    testcase.assertEqual(security.schema_version(conn), security.LATEST_SCHEMA_VERSION)
    tables = {
        row["name"]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
    }
    testcase.assertTrue(
        {
            "users",
            "sessions",
            "disclaimer_acceptances",
            "login_failures",
            "audit_log",
        }.issubset(tables)
    )

    user_columns = {row["name"] for row in conn.execute("PRAGMA table_info(users)")}
    testcase.assertTrue(
        {
            "id",
            "username",
            "role",
            "password_hash",
            "disabled",
            "must_change_password",
            "disclaimer_signed",
            "created_at",
            "user_uuid",
        }.issubset(user_columns)
    )

    session_columns = {row["name"] for row in conn.execute("PRAGMA table_info(sessions)")}
    testcase.assertTrue({"token", "user_id", "expires_at", "session_uuid"}.issubset(session_columns))
    testcase.assertEqual(
        conn.execute("SELECT COUNT(*) FROM users WHERE user_uuid IS NULL OR user_uuid = ''").fetchone()[0],
        0,
    )
    testcase.assertEqual(
        conn.execute("SELECT COUNT(*) FROM sessions WHERE session_uuid IS NULL OR session_uuid = ''").fetchone()[0],
        0,
    )

    disclaimer_columns = {
        row["name"] for row in conn.execute("PRAGMA table_info(disclaimer_acceptances)")
    }
    testcase.assertTrue({"user_id", "version", "accepted_at"}.issubset(disclaimer_columns))


def assert_safe_session(testcase, body, *, user_id, username, role):
    testcase.assertIs(body["ok"], True)
    testcase.assertEqual(body["user_id"], user_id)
    testcase.assertEqual(body["username"], username)
    testcase.assertEqual(body["role"], role)
    testcase.assertEqual(body["message"], role)
    testcase.assertIsInstance(body["expires_at"], int)
    for forbidden in ("token", "jwt", "secret", "sub", "iat", "jti", "exp"):
        testcase.assertNotIn(forbidden, body)
