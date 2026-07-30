import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from fastapi.testclient import TestClient
from treatment_plan.app import create_app
from treatment_plan.config import ConfigurationError, Settings
from treatment_plan.repository import InMemoryRepository
from treatment_plan.security import AccessDenied, Capability, InMemoryAuthenticationAdapter, Security, Session

NOW = datetime(2026, 7, 13, tzinfo=timezone.utc)

class SecurityTests(unittest.TestCase):
    def session(self, roles=(), enabled=True, expires=None, permissions=()):
        return Session("user-1", frozenset(roles), expires or NOW + timedelta(hours=1), "csrf-secret", enabled, frozenset(permissions))

    def security(self, session):
        adapter = InMemoryAuthenticationAdapter({"sid=trusted": session})
        return Security(adapter, now=lambda: NOW), adapter

    def test_deny_by_default_and_admin_cannot_read_or_mutate_plans(self):
        security, _ = self.security(self.session(("admin",)))
        for capability in (Capability.PLAN_READ, Capability.PLAN_MUTATE, Capability.SUPPORT_READ):
            with self.assertRaises(AccessDenied): security.authorize("sid=trusted", capability, "csrf-secret")

    def test_expired_and_disabled_sessions_are_denied(self):
        for session in (self.session(("psychiatrist",), expires=NOW), self.session(("psychiatrist",), enabled=False)):
            security, _ = self.security(session)
            with self.assertRaisesRegex(AccessDenied, "expired or disabled"):
                security.authorize("sid=trusted", Capability.PLAN_READ)

    def test_psychiatrist_mutation_requires_csrf(self):
        security, _ = self.security(self.session(("psychiatrist",)))
        for token in (None, "wrong"):
            with self.assertRaisesRegex(AccessDenied, "CSRF"):
                security.authorize("sid=trusted", Capability.PLAN_MUTATE, token)
        self.assertEqual("user-1", security.authorize("sid=trusted", Capability.PLAN_MUTATE, "csrf-secret").user_id)

    def test_admin_support_requires_explicit_approval_and_is_read_only(self):
        security, _ = self.security(self.session(("admin",), permissions=("treatment-plan:support",)))
        self.assertEqual("user-1", security.authorize("sid=trusted", Capability.SUPPORT_READ).user_id)
        with self.assertRaises(AccessDenied): security.authorize("sid=trusted", Capability.PLAN_MUTATE, "csrf-secret")

    def test_cookie_reaches_only_injected_authentication_adapter(self):
        security, adapter = self.security(self.session(("psychiatrist",)))
        with TestClient(create_app(Settings(environment="test"), InMemoryRepository(), security)) as client:
            response = client.get("/api/treatment-plan/v1/session", headers={"Cookie": "sid=trusted"})
        self.assertEqual(200, response.status_code)
        self.assertEqual(["sid=trusted"], adapter.received_cookies)

    def test_plan_routes_reject_non_uuid_ids_and_missing_request_id(self):
        security, _ = self.security(self.session(("psychiatrist",)))
        app = create_app(Settings(environment="test"), InMemoryRepository(), security)
        with TestClient(app) as client:
            invalid_plan = client.get(
                "/api/treatment-plan/v1/plans/not-a-uuid",
                headers={"Cookie": "sid=trusted"},
            )
            missing_request_id = client.post(
                "/api/treatment-plan/v1/plans/00000000-0000-4000-8000-000000000001/finalize",
                headers={
                    "Cookie": "sid=trusted",
                    "X-CSRF-Token": "csrf-secret",
                    "If-Match": '"1"',
                    "Idempotency-Key": "tp-request-key-0001",
                },
                json={"attestation": "I reviewed and attest to this exact plan."},
            )
        self.assertEqual(422, invalid_plan.status_code)
        self.assertEqual(422, missing_request_id.status_code)

    def test_ssrf_allowlist_rejects_untrusted_and_malformed_urls(self):
        cases = [
            {"TP_AUTHENTICATION_SESSION_URL":"http://169.254.169.254/session","TP_TRUSTED_INTERNAL_ORIGINS":"https://auth.internal"},
            {"TP_AUTHENTICATION_SESSION_URL":"https://auth.internal.evil/session","TP_TRUSTED_INTERNAL_ORIGINS":"https://auth.internal"},
            {"TP_AUTHENTICATION_SESSION_URL":"https://user@auth.internal/session","TP_TRUSTED_INTERNAL_ORIGINS":"https://auth.internal"},
        ]
        for values in cases:
            with patch.dict(os.environ, {"TP_ENV":"test", **values}, clear=True):
                with self.assertRaises(ConfigurationError): Settings.from_env()

    def test_production_has_no_stub_or_missing_auth_bypass(self):
        with patch.dict(os.environ, {"TP_ENV":"production"}, clear=True):
            with self.assertRaisesRegex(ConfigurationError, "requires the Authentication"):
                Settings.from_env()
        with patch.dict(os.environ, {"TP_ENV":"production","TP_AUTH_STUB_ENABLED":"true"}, clear=True):
            with self.assertRaises(ConfigurationError): Settings.from_env()

if __name__ == "__main__": unittest.main()
