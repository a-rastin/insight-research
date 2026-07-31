import os
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from io import BytesIO
from fastapi.testclient import TestClient
from treatment_plan.app import create_app
from treatment_plan.config import ConfigurationError, Settings
from treatment_plan.repository import InMemoryRepository
from treatment_plan.security import AccessDenied, Capability, HttpAuthenticationAdapter, InMemoryAuthenticationAdapter, Security, Session

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
        with patch.dict(os.environ, {
            "TP_ENV": "production",
            "TP_AUTHENTICATION_SESSION_URL": "http://127.0.0.1:8101/api/auth/v2/session",
            "TP_TRUSTED_INTERNAL_ORIGINS": "http://127.0.0.1:8101",
        }, clear=True):
            with self.assertRaisesRegex(ConfigurationError, "requires DDI REST"):
                Settings.from_env()

    def test_http_adapter_strictly_accepts_only_authorized_authentication_v2_contract(self):
        payload = {
            "authenticated": True,
            "authorized": True,
            "interfaceVersion": "2.0.0",
            "session": {"id": "00000000-0000-4000-8000-000000000071", "active": True, "expiresAt": "2026-08-01T00:00:00Z"},
            "user": {"id": "00000000-0000-4000-8000-000000000072", "username": "clinician", "role": "psychiatrist"},
            "gates": {"passwordChangeRequired": False, "disclaimerRequired": False, "disclaimerVersion": "2026-01"},
            "compatibility": {"legacyUserId": 7, "legacyRole": "user"},
        }
        class Response(BytesIO):
            def __enter__(self): return self
            def __exit__(self, *_args): return None
        response = Response(__import__("json").dumps(payload).encode())
        with patch("treatment_plan.security.urlopen", return_value=response):
            session = HttpAuthenticationAdapter("https://auth.internal/api/auth/v2/session").verify("insight_session=opaque")
        self.assertEqual(payload["user"]["id"], session.user_id)
        self.assertEqual(payload["session"]["id"], session.session_id)
        self.assertEqual(frozenset({"psychiatrist"}), session.roles)

        for mutate in (
            lambda value: value.update(authorized=False),
            lambda value: value["gates"].update(disclaimerRequired=True),
            lambda value: value["session"].update(active=False),
            lambda value: value.update(expiresAt="legacy-flat-field"),
        ):
            invalid = __import__("copy").deepcopy(payload)
            mutate(invalid)
            with self.assertRaises((AccessDenied, ValueError)):
                HttpAuthenticationAdapter._parse(invalid)

    def test_http_session_uses_auth_csrf_cookie_for_mutation(self):
        payload = {
            "authenticated": True, "authorized": True, "interfaceVersion": "2.0.0",
            "session": {"id": "00000000-0000-4000-8000-000000000071", "active": True, "expiresAt": "2026-08-01T00:00:00Z"},
            "user": {"id": "00000000-0000-4000-8000-000000000072", "username": "clinician", "role": "psychiatrist"},
            "gates": {"passwordChangeRequired": False, "disclaimerRequired": False, "disclaimerVersion": "2026-01"},
            "compatibility": {"legacyUserId": 7, "legacyRole": "user"},
        }
        security = Security(type("Adapter", (), {"verify": lambda _self, _cookie: HttpAuthenticationAdapter._parse(payload)})(), now=lambda: NOW)
        self.assertEqual(payload["user"]["id"], security.authorize("cookie", Capability.PLAN_MUTATE, "signed-token", "signed-token").user_id)
        with self.assertRaisesRegex(AccessDenied, "CSRF"):
            security.authorize("cookie", Capability.PLAN_MUTATE, "wrong", "signed-token")

if __name__ == "__main__": unittest.main()
