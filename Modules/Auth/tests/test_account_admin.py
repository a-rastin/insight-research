from _support import AuthTestCase

from starlette.testclient import TestClient

import main
import security


class AccountAdministrationTests(AuthTestCase):
    def test_admin_can_create_page_update_disable_and_reset_with_revocation(self):
        admin = self.login_admin()
        created = admin.post(
            "/api/auth/v2/admin/accounts",
            json={"username": "account-doc", "password": "safe-pass-1", "role": "psychiatrist"},
        )
        self.assertEqual(created.status_code, 201)
        account = created.json()
        self.assertEqual(account["username"], "account-doc")
        self.assertEqual(account["role"], "psychiatrist")
        self.assertNotIn("password_hash", repr(account).lower())

        duplicate = admin.post(
            "/api/auth/v2/admin/accounts",
            json={"username": "account-doc", "password": "safe-pass-2", "role": "psychiatrist"},
        )
        self.assertEqual(duplicate.status_code, 409)
        weak = admin.post(
            "/api/auth/v2/admin/accounts",
            json={"username": "weak-doc", "password": "short", "role": "psychiatrist"},
        )
        self.assertEqual(weak.status_code, 422)

        page = admin.get("/api/auth/v2/admin/accounts?limit=1&offset=1")
        self.assertEqual(page.status_code, 200)
        self.assertEqual(page.json()["pagination"]["limit"], 1)
        self.assertEqual(page.json()["pagination"]["offset"], 1)
        self.assertGreaterEqual(page.json()["pagination"]["total"], 2)
        self.assertNotIn("password_hash", repr(page.json()))

        row = security.get_user("account-doc")
        security.set_disclaimer_signed(row["id"])
        psychiatrist = self.client()
        login = psychiatrist.post(
            "/api/auth/login",
            json={"username": "account-doc", "password": "safe-pass-1", "role": "psychiatrist"},
        )
        self.assertEqual(login.status_code, 200)
        stale_token = psychiatrist.cookies.get(security.cfg("AUTH_COOKIE_NAME"))

        role_update = admin.patch(
            f"/api/auth/v2/admin/accounts/{account['id']}",
            json={"role": "admin"},
        )
        self.assertEqual(role_update.status_code, 200)
        self.assertEqual(role_update.json()["role"], "admin")
        self.assertEqual(self.client_with_session_token(stale_token).get("/api/auth/v2/session").status_code, 401)

        new_admin = self.client()
        self.assertEqual(
            new_admin.post(
                "/api/auth/login",
                json={"username": "account-doc", "password": "safe-pass-1", "role": "admin"},
            ).status_code,
            200,
        )
        admin_token = new_admin.cookies.get(security.cfg("AUTH_COOKIE_NAME"))
        reset = admin.post(
            f"/api/auth/v2/admin/accounts/{account['id']}/reset-password",
            json={"temporary_password": "temporary-2"},
        )
        self.assertEqual(reset.status_code, 200)
        self.assertEqual(reset.json()["temporaryPassword"], "temporary-2")
        self.assertEqual(self.client_with_session_token(admin_token).get("/api/auth/v2/session").status_code, 401)

        disabled = admin.patch(
            f"/api/auth/v2/admin/accounts/{account['id']}",
            json={"disabled": True},
        )
        self.assertEqual(disabled.status_code, 200)
        self.assertTrue(disabled.json()["disabled"])
        audit_text = repr(security.list_audit_entries()).lower()
        self.assertNotIn("safe-pass-1", audit_text)
        self.assertNotIn("temporary-2", audit_text)

    def test_authorization_csrf_validation_and_owner_hosted_ui(self):
        anonymous = self.raw_client()
        self.assertEqual(anonymous.get("/api/auth/v2/admin/accounts").status_code, 401)

        user_id = security.register_user("not-admin", "psychiatrist", "safe-pass-3")
        security.set_disclaimer_signed(user_id)
        psychiatrist = self.client()
        psychiatrist.post(
            "/api/auth/login",
            json={"username": "not-admin", "password": "safe-pass-3", "role": "psychiatrist"},
        )
        self.assertEqual(psychiatrist.get("/api/auth/v2/admin/accounts").status_code, 403)
        self.assertEqual(psychiatrist.get("/modules/auth/accounts").status_code, 403)

        admin = self.login_admin()
        no_csrf = self.raw_client()
        no_csrf.cookies.set(
            security.cfg("AUTH_COOKIE_NAME"),
            admin.cookies.get(security.cfg("AUTH_COOKIE_NAME")),
        )
        rejected = no_csrf.post(
            "/api/auth/v2/admin/accounts",
            json={"username": "csrf-doc", "password": "safe-pass-4", "role": "psychiatrist"},
        )
        self.assertEqual(rejected.status_code, 403)

        invalid = admin.patch(
            f"/api/auth/v2/admin/accounts/{security.get_user('Admin')['user_uuid']}",
            json={},
        )
        self.assertEqual(invalid.status_code, 422)
        mixed = admin.patch(
            f"/api/auth/v2/admin/accounts/{security.get_user('Admin')['user_uuid']}",
            json={"role": "admin", "disabled": False},
        )
        self.assertEqual(mixed.status_code, 422)
        weak_reset = admin.post(
            f"/api/auth/v2/admin/accounts/{security.get_user('Admin')['user_uuid']}/reset-password",
            json={"temporary_password": "short"},
        )
        self.assertEqual(weak_reset.status_code, 422)

        for path in ("/modules/auth/accounts", "/modules/auth/accounts/new"):
            ui = admin.get(path)
            self.assertEqual(ui.status_code, 200)
            html = ui.text
            self.assertIn("Account Administration", html)
            self.assertIn('scope="col"', html)
            self.assertIn('role="status"', html)
            self.assertIn("prefers-reduced-motion", html)
            self.assertIn("/api/auth/v2/admin/accounts", html)
            self.assertNotIn("localStorage", html)

        original_list_users = security.list_users
        security.list_users = lambda *_: (_ for _ in ()).throw(RuntimeError("storage unavailable"))
        try:
            failure_client = TestClient(main.app, raise_server_exceptions=False)
            failure_client.cookies.set(
                security.cfg("AUTH_COOKIE_NAME"),
                admin.cookies.get(security.cfg("AUTH_COOKIE_NAME")),
            )
            failure = failure_client.get("/api/auth/v2/admin/accounts")
            self.assertEqual(failure.status_code, 500)
            self.assertNotIn("insight_session", failure.text)
            self.assertNotIn("password", failure.text.lower())
        finally:
            security.list_users = original_list_users


if __name__ == "__main__":
    import unittest

    unittest.main()
