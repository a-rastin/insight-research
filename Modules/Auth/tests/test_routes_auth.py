from _support import AuthTestCase, assert_safe_session
import security


class AuthRouteTests(AuthTestCase):
    def test_health_readiness_and_csrf_protection(self):
        client = self.raw_client()
        for path in ("/api/auth/health", "/healthz"):
            response = client.get(path)
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"ok": True, "service": "auth", "status": "alive"})

        for path in ("/api/auth/ready", "/readyz"):
            response = client.get(path)
            self.assertEqual(response.status_code, 200)
            body = response.json()
            self.assertIs(body["ok"], True)
            self.assertEqual(body["checks"]["database"], {"ok": True, "status": "reachable"})
            self.assertTrue(body["checks"]["auth_jwt_secret"]["ok"])
            flattened = repr(body)
            self.assertNotIn(self.db_path, flattened)
            self.assertNotIn("Admin", flattened)

        missing = client.post(
            "/api/auth/login",
            json={"username": "Admin", "password": "Admin", "role": "admin"},
        )
        self.assertEqual(missing.status_code, 403)
        self.assertEqual(missing.json()["detail"], "Invalid CSRF token")

        self.csrf_headers(client)
        bad = client.post(
            "/api/auth/login",
            headers={security.cfg("AUTH_CSRF_HEADER_NAME"): "wrong"},
            json={"username": "Admin", "password": "Admin", "role": "admin"},
        )
        self.assertEqual(bad.status_code, 403)

    def test_admin_login_session_register_and_logout_flow(self):
        client = self.login_admin()
        admin = security.get_user("Admin")
        token = client.cookies.get(security.cfg("AUTH_COOKIE_NAME"))
        self.assertTrue(token)
        self.assertIsNotNone(security.resolve_session(token))

        session = client.get("/api/auth/session")
        self.assertEqual(session.status_code, 200)
        body = session.json()
        assert_safe_session(self, body, user_id=admin["id"], username="Admin", role="admin")
        self.assertEqual(body["display_role"], "Administrator")
        self.assertEqual(body["disclaimer_status"], "not_required")
        self.assertIsNone(body["clinical_role"])
        self.assertIsNone(body["legacy_role"])

        created = client.post(
            "/api/auth/register",
            json={"username": "doc1", "password": "secret", "role": "psychiatrist"},
        )
        self.assertEqual(created.status_code, 201)
        duplicate = client.post(
            "/api/auth/register",
            json={"username": "doc1", "password": "secret", "role": "psychiatrist"},
        )
        self.assertEqual(duplicate.status_code, 409)

        accounts = client.get("/api/auth/admin/users")
        self.assertEqual(accounts.status_code, 200)
        users = accounts.json()["users"]
        self.assertTrue(any(user["username"] == "doc1" for user in users))
        for account in users:
            self.assertEqual(
                set(account),
                {
                    "id",
                    "username",
                    "role",
                    "disabled",
                    "must_change_password",
                    "disclaimer_signed",
                    "created_at",
                },
            )

        logout = client.post("/api/auth/logout")
        self.assertEqual(logout.status_code, 200)
        self.assertIsNone(security.resolve_session(token))
        self.assertEqual(self.client_with_session_token(token).get("/api/auth/session").status_code, 401)

    def test_psychiatrist_disclaimer_gate(self):
        admin_client = self.login_admin()
        created = admin_client.post(
            "/api/auth/register",
            json={"username": "doc2", "password": "secret", "role": "user"},
        )
        self.assertEqual(created.status_code, 201)

        user_client = self.client()
        login = user_client.post(
            "/api/auth/login",
            json={"username": "doc2", "password": "secret", "role": "psychiatrist"},
        )
        self.assertEqual(login.status_code, 200)
        self.assertIs(login.json()["disclaimer_required"], True)
        self.assertEqual(user_client.get("/api/auth/session").status_code, 401)

        disclaimer = user_client.get("/api/auth/disclaimer")
        self.assertEqual(disclaimer.status_code, 200)
        disclaimer_body = disclaimer.json()
        self.assertEqual(disclaimer_body["version"], security.active_disclaimer_version())
        self.assertFalse(disclaimer_body["accepted"])

        accept = user_client.post("/api/auth/disclaimer/accept")
        self.assertEqual(accept.status_code, 200)
        self.assertEqual(accept.json()["next"], "/dashboard/")

        session = user_client.get("/api/auth/session")
        self.assertEqual(session.status_code, 200)
        doc = security.get_user("doc2")
        body = session.json()
        assert_safe_session(self, body, user_id=doc["id"], username="doc2", role="psychiatrist")
        self.assertEqual(body["display_role"], "Psychiatrist")
        self.assertEqual(body["disclaimer_status"], "accepted")
        self.assertEqual(body["clinical_role"], "psychiatrist")
        self.assertEqual(body["legacy_role"], "user")


if __name__ == "__main__":
    import unittest

    unittest.main()
