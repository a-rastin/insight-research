from _support import AuthTestCase, assert_auth_schema
import security


class SecurityUnitTests(AuthTestCase):
    def test_password_hashing_token_roundtrip_and_csrf(self):
        user = security.get_user("Admin")
        self.assertIsNotNone(user)
        self.assertEqual(user["role"], "admin")

        password_hash = security.hash_password("secret")
        self.assertTrue(security.verify_password("secret", password_hash))
        self.assertFalse(security.verify_password("wrong", password_hash))
        self.assertNotIn("secret", password_hash)

        token = security.issue_token(user["id"], "admin")
        payload = security.verify_token(token)
        self.assertEqual(payload["sub"], str(user["id"]))
        self.assertEqual(payload["role"], "admin")
        self.assertIsNone(security.verify_token("garbage"))

        csrf = security.issue_csrf_token()
        self.assertTrue(security.verify_csrf_token(csrf, csrf))
        self.assertFalse(security.verify_csrf_token(csrf, "wrong"))
        self.assertFalse(security.verify_csrf_token(None, csrf))

    def test_role_normalization_and_timing_safe_username_compare(self):
        self.assertEqual(security.normalize_role("user"), "psychiatrist")
        self.assertEqual(security.normalize_role("psychiatrist"), "psychiatrist")
        self.assertEqual(security.normalize_role("admin"), "admin")
        with self.assertRaises(security.InvalidRoleError):
            security.normalize_role("clinician")

        self.assertTrue(security.username_eq("Admin", "Admin"))
        self.assertFalse(security.username_eq("Admin", "admin"))
        self.assertFalse(security.username_eq("Admin", "Admin "))

    def test_schema_initializes_default_admin_in_temp_database(self):
        conn = security.get_conn()
        assert_auth_schema(self, conn)
        user = security.get_user("Admin")
        self.assertEqual(user["role"], "admin")
        self.assertTrue(security.verify_password("Admin", user["password_hash"]))
        self.assertTrue(self.db_path.endswith("auth.sqlite3"))


if __name__ == "__main__":
    import unittest

    unittest.main()
