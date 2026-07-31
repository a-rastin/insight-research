from _support import AuthTestCase
from datetime import UTC, datetime
import json
from pathlib import Path
import uuid

from jsonschema import Draft202012Validator, FormatChecker

import security


class AuthContractTests(AuthTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.session_schema = json.loads(
            (Path(__file__).parents[1] / "docs" / "auth-session-v2.schema.json").read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(cls.session_schema)
        cls.session_validator = Draft202012Validator(
            cls.session_schema,
            format_checker=FormatChecker(),
        )

    def assert_valid_v2_session(self, response):
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.session_validator.validate(body)
        return body

    def test_v2_session_contract_uses_uuid_identity_and_explicit_gates(self):
        client = self.login_admin()
        response = client.get("/api/auth/v2/session")
        body = self.assert_valid_v2_session(response)
        self.assertEqual(response.headers["x-schema-version"], "2.0.0")
        self.assertEqual(
            set(body),
            {"authenticated", "authorized", "interfaceVersion", "session", "user", "gates", "compatibility"},
        )
        self.assertTrue(body["authenticated"])
        self.assertTrue(body["authorized"])
        self.assertEqual(body["interfaceVersion"], "2.0.0")
        uuid.UUID(body["session"]["id"])
        uuid.UUID(body["user"]["id"])
        self.assertEqual(body["user"]["role"], "admin")
        self.assertEqual(body["compatibility"]["legacyUserId"], security.get_user("Admin")["id"])
        self.assertIsNone(body["compatibility"]["legacyRole"])
        expires_at = datetime.fromisoformat(body["session"]["expiresAt"].replace("Z", "+00:00"))
        self.assertEqual(expires_at.tzinfo, UTC)
        self.assertNotIn("message", body)

        self.assertEqual(
            self.session_schema["properties"]["interfaceVersion"]["const"],
            body["interfaceVersion"],
        )
        self.assertEqual(
            self.session_schema["properties"]["user"]["properties"]["role"]["enum"],
            ["admin", "psychiatrist"],
        )

        noncanonical = json.loads(json.dumps(body))
        noncanonical["session"]["expiresAt"] = noncanonical["session"]["expiresAt"].replace("Z", "+00:00")
        self.assertTrue(list(self.session_validator.iter_errors(noncanonical)))

    def test_v2_session_exposes_password_and_disclaimer_gates(self):
        user_id = security.register_user("pending", "psychiatrist", "temporary")
        conn = security.get_conn()
        with security._tx(conn):
            conn.execute("UPDATE users SET must_change_password = 1 WHERE id = ?", (user_id,))
        client = self.client()
        login = client.post(
            "/api/auth/login",
            json={"username": "pending", "password": "temporary", "role": "psychiatrist"},
        )
        self.assertTrue(login.json()["password_change_required"])

        body = self.assert_valid_v2_session(client.get("/api/auth/v2/session"))
        self.assertTrue(body["authenticated"])
        self.assertFalse(body["authorized"])
        self.assertTrue(body["gates"]["passwordChangeRequired"])
        self.assertTrue(body["gates"]["disclaimerRequired"])
        self.assertEqual(body["compatibility"]["legacyRole"], "user")
        self.assertEqual(client.get("/api/auth/session").status_code, 401)

    def test_v2_revocation_disable_and_role_changes_are_immediate(self):
        user_id = security.register_user("current-state", "psychiatrist", "secret")
        security.set_disclaimer_signed(user_id)
        client = self.client()
        client.post(
            "/api/auth/login",
            json={"username": "current-state", "password": "secret", "role": "psychiatrist"},
        )
        token = client.cookies.get(security.cfg("AUTH_COOKIE_NAME"))
        self.assert_valid_v2_session(client.get("/api/auth/v2/session"))

        security.update_user_role(user_id, "admin")
        self.assertEqual(self.client_with_session_token(token).get("/api/auth/v2/session").status_code, 401)

        token = security.issue_token(user_id, "admin")
        self.assert_valid_v2_session(
            self.client_with_session_token(token).get("/api/auth/v2/session")
        )
        security.set_user_disabled(user_id, True)
        self.assertEqual(self.client_with_session_token(token).get("/api/auth/v2/session").status_code, 401)

    def test_v1_session_adapter_is_deprecated(self):
        response = self.login_admin().get("/api/auth/session")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["deprecation"], "true")
        self.assertEqual(response.headers["link"], '</api/auth/v2/session>; rel="successor-version"')
        self.assertIsInstance(response.json()["user_id"], int)

    def test_login_role_contract_and_safe_redirects(self):
        client = self.client()

        login_html = client.get("/").text
        self.assertIn("window.location.replace('/dashboard/')", login_html)
        self.assertNotIn("/dashboard/admin", login_html)
        self.assertNotIn("/dashboard/user", login_html)

        invalid_role = client.post(
            "/api/auth/login",
            json={"username": "Admin", "password": "Admin", "role": "clinician"},
        )
        self.assertEqual(invalid_role.status_code, 422)

        mismatch = client.post(
            "/api/auth/login",
            json={"username": "Admin", "password": "Admin", "role": "psychiatrist"},
        )
        self.assertEqual(mismatch.status_code, 403)
        self.assertEqual(mismatch.json()["detail"], "Wrong username or password")

        login = client.post(
            "/api/auth/login",
            json={
                "username": "Admin",
                "password": "Admin",
                "role": "admin",
                "next": "https://example.com/steal",
            },
        )
        self.assertEqual(login.status_code, 200)
        self.assertEqual(login.json()["next"], "/dashboard/")

    def test_admin_lifecycle_contract_revokes_stale_sessions(self):
        client = self.login_admin()
        created = client.post(
            "/api/auth/register",
            json={"username": "doc3", "password": "secret", "role": "psychiatrist"},
        )
        self.assertEqual(created.status_code, 201)
        doc = security.get_user("doc3")
        security.set_disclaimer_signed(doc["id"])

        user_client = self.client()
        self.assertEqual(
            user_client.post(
                "/api/auth/login",
                json={"username": "doc3", "password": "secret", "role": "psychiatrist"},
            ).status_code,
            200,
        )
        user_token = user_client.cookies.get(security.cfg("AUTH_COOKIE_NAME"))
        self.assertEqual(user_client.get("/api/auth/session").status_code, 200)

        reset = client.post(
            f"/api/auth/admin/users/{doc['id']}/reset-password",
            json={"temporary_password": "temp-doc3"},
        )
        self.assertEqual(reset.status_code, 200)
        self.assertEqual(reset.json()["temporary_password"], "temp-doc3")
        self.assertEqual(self.client_with_session_token(user_token).get("/api/auth/session").status_code, 401)

        temp_client = self.client()
        temp_login = temp_client.post(
            "/api/auth/login",
            json={"username": "doc3", "password": "temp-doc3", "role": "psychiatrist"},
        )
        self.assertEqual(temp_login.status_code, 200)
        self.assertTrue(temp_login.json()["password_change_required"])
        self.assertEqual(temp_client.get("/api/auth/session").status_code, 401)

        rotated = temp_client.post(
            "/api/auth/password/change",
            json={"current_password": "temp-doc3", "new_password": "rotated-doc3"},
        )
        self.assertEqual(rotated.status_code, 200)
        self.assertEqual(temp_client.get("/api/auth/session").status_code, 200)

        role_update = client.patch(f"/api/auth/admin/users/{doc['id']}/role", json={"role": "admin"})
        self.assertEqual(role_update.status_code, 200)
        self.assertEqual(temp_client.get("/api/auth/session").status_code, 401)

        admin_login = self.client()
        self.assertEqual(
            admin_login.post(
                "/api/auth/login",
                json={"username": "doc3", "password": "rotated-doc3", "role": "admin"},
            ).status_code,
            200,
        )

    def test_unauthorized_admin_contract(self):
        anonymous = self.client().get("/api/auth/admin/users")
        self.assertEqual(anonymous.status_code, 401)

        client = self.login_admin()
        admin = security.get_user("Admin")
        self_disable = client.post(f"/api/auth/admin/users/{admin['id']}/disable")
        self.assertEqual(self_disable.status_code, 403)
        self_demote = client.patch(f"/api/auth/admin/users/{admin['id']}/role", json={"role": "psychiatrist"})
        self.assertEqual(self_demote.status_code, 403)


if __name__ == "__main__":
    import unittest

    unittest.main()
