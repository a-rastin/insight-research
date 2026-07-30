from _support import AuthTestCase
import security


class SecurityBehaviorTests(AuthTestCase):
    def test_failed_login_limit_is_generic_and_recovers_after_lockout(self):
        original_now = security._now
        now = [1_800_000_000]
        security._now = lambda: now[0]
        try:
            client = self.client()
            generic_failure = {"detail": "Wrong username or password"}
            for _ in range(3):
                failed = client.post(
                    "/api/auth/login",
                    json={"username": "Admin", "password": "wrong", "role": "admin"},
                )
                self.assertEqual(failed.status_code, 401)
                self.assertEqual(failed.json(), generic_failure)

            locked = client.post(
                "/api/auth/login",
                json={"username": "Admin", "password": "Admin", "role": "admin"},
            )
            self.assertEqual(locked.status_code, 401)
            self.assertEqual(locked.json(), generic_failure)

            now[0] += 31
            recovered = client.post(
                "/api/auth/login",
                json={"username": "Admin", "password": "Admin", "role": "admin"},
            )
            self.assertEqual(recovered.status_code, 200)
            self.assertEqual(recovered.json()["next"], "/dashboard/admin")
        finally:
            security._now = original_now

    def test_session_requires_live_server_row_current_role_and_enabled_account(self):
        user_id = security.register_user("doc-sec", "psychiatrist", "secret")
        security.set_disclaimer_signed(user_id)
        token = security.issue_token(user_id, "psychiatrist")
        security.record_session(token, user_id, security.verify_token(token)["exp"])
        self.assertIsNotNone(security.resolve_session(token))

        conn = security.get_conn()
        with security._tx(conn):
            conn.execute("UPDATE users SET role = 'admin' WHERE id = ?", (user_id,))
        self.assertIsNone(security.resolve_session(token), "current role must match token role")

        with security._tx(conn):
            conn.execute("UPDATE users SET role = 'psychiatrist', disabled = 1 WHERE id = ?", (user_id,))
        self.assertIsNone(security.resolve_session(token), "disabled users must not authorize")

        with security._tx(conn):
            conn.execute("UPDATE users SET disabled = 0 WHERE id = ?", (user_id,))
        security.record_session(token, user_id, security.verify_token(token)["exp"])
        self.assertIsNotNone(security.resolve_session(token))
        security.revoke_session(token)
        self.assertIsNone(security.resolve_session(token), "server-side session row is required")

    def test_expired_deleted_and_new_disclaimer_version_sessions_fail_closed(self):
        admin = security.get_user("Admin")
        expired = security.issue_token(admin["id"], "admin", expires_in=-60)
        self.assertEqual(self.client_with_session_token(expired).get("/api/auth/session").status_code, 401)

        user_id = security.register_user("doc-version", "psychiatrist", "secret")
        security.set_disclaimer_signed(user_id)
        token = security.issue_token(user_id, "psychiatrist")
        security.record_session(token, user_id, security.verify_token(token)["exp"])
        self.assertIsNotNone(security.resolve_session(token))

        original_version = security.disclaimer_contract.CURRENT_DISCLAIMER_VERSION
        security.disclaimer_contract.CURRENT_DISCLAIMER_VERSION = "2099-01-01"
        try:
            self.assertIsNone(security.resolve_session(token))
            pending = security.resolve_session(token, require_disclaimer=False)
            self.assertIsNotNone(pending)
            self.assertFalse(pending["disclaimer_signed"])
        finally:
            security.disclaimer_contract.CURRENT_DISCLAIMER_VERSION = original_version

        with security._tx(security.get_conn()):
            security.get_conn().execute("DELETE FROM users WHERE id = ?", (user_id,))
        self.assertIsNone(security.resolve_session(token, require_disclaimer=False))


if __name__ == "__main__":
    import unittest

    unittest.main()
