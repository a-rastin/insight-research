from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import unittest

from fastapi import Request
from fastapi.testclient import TestClient

from bn_manager_backend.auth_adapter import SessionState, session_from_payload
from bn_manager_backend.main import create_app

SESSION_ID = "e8c996c1-ab80-4de0-a9f4-70d36a80f301"
USER_ID = "35e65add-887d-4911-a970-97a4e5300a21"


def auth_v2_payload(role: str = "psychiatrist") -> dict:
    return {
        "authenticated": True,
        "authorized": True,
        "interfaceVersion": "2.0.0",
        "session": {
            "id": SESSION_ID,
            "active": True,
            "expiresAt": "2999-07-29T18:30:00Z",
        },
        "user": {
            "id": USER_ID,
            "username": "doc1",
            "role": role,
        },
        "gates": {
            "passwordChangeRequired": False,
            "disclaimerRequired": False,
            "disclaimerVersion": "2026-07-06",
        },
        "compatibility": {
            "legacyUserId": 2,
            "legacyRole": "user" if role == "psychiatrist" else None,
        },
    }


class FakeSessionAdapter:
    def __init__(self, session: SessionState) -> None:
        self.session = session

    def fetch_session(self, request: Request) -> SessionState:
        return self.session


class AuthenticationGuardTests(unittest.TestCase):
    def test_provider_authentication_v2_shape_derives_canonical_identity(self) -> None:
        session = session_from_payload(auth_v2_payload())

        self.assertTrue(session.active)
        self.assertEqual(session.subject, USER_ID)
        self.assertEqual(session.roles, frozenset({"psychiatrist"}))
        self.assertIsNone(session.csrf_token)
        self.assertFalse(session.expired)

    def test_rejects_invalid_authentication_v2_contract_fields(self) -> None:
        mutations = (
            (("authenticated",), False),
            (("authorized",), False),
            (("interfaceVersion",), "1.0.0"),
            (("session", "active"), False),
            (("session", "expiresAt"), "2000-01-01T00:00:00Z"),
            (("session", "expiresAt"), "2999-01-01T00:00:00"),
            (("session", "id"), SESSION_ID.upper()),
            (("user", "id"), "not-a-uuid"),
            (("user", "role"), "Administrator"),
            (("user", "role"), ["psychiatrist"]),
            (("gates", "passwordChangeRequired"), True),
            (("gates", "disclaimerRequired"), True),
        )
        for path, value in mutations:
            with self.subTest(path=path, value=value):
                payload = deepcopy(auth_v2_payload())
                target = payload
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                self.assertFalse(session_from_payload(payload).active)

        self.assertFalse(session_from_payload([auth_v2_payload()]).active)

    def test_valid_psychiatrist_can_evaluate_registered_xml_model(self) -> None:
        client = self._client(auth_v2_payload(), "csrf-1")
        response = client.post(
            "/api/bn-manager/v1/dashboard/evaluate",
            json={
                "model": {"model_id": "bnm.clozapine-suicide-risk"},
                "evidence": {
                    "Schizophrenia_Suicide_Indication": "Met",
                },
            },
            headers={"x-csrf-token": "csrf-1"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["target"], "Clinical_Action_Pattern")
        self.assertAlmostEqual(sum(payload["data"]["values"].values()), 1.0)
        self.assertTrue(all("probability" in row for row in payload["data"]["rankings"]))

    def test_valid_admin_can_validate_registered_xml_model(self) -> None:
        client = self._client(auth_v2_payload("admin"), "csrf-2")
        response = client.post(
            "/api/bn-manager/v1/models/validate",
            json={"model": {"model_id": "bnm.pharmacotherapy"}},
            headers={"x-csrf-token": "csrf-2"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["data"]["valid"])
        self.assertEqual(payload["data"]["checked_by"], USER_ID)

    def test_expired_session_is_rejected_before_model_loading(self) -> None:
        payload = auth_v2_payload()
        payload["session"]["expiresAt"] = "2000-01-01T00:00:00Z"
        client = self._client(payload, "csrf-3")
        response = client.post(
            "/api/bn-manager/v1/dashboard/evaluate",
            json={},
            headers={"x-csrf-token": "csrf-3"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "BNM_UNAUTHORIZED")

    def test_disclaimer_and_forced_password_sessions_are_blocked(self) -> None:
        blocked_payloads = (("disclaimerRequired", "disclaimer_required"), ("passwordChangeRequired", "forced_password_change"))
        for gate, reason in blocked_payloads:
            with self.subTest(reason=reason):
                payload = auth_v2_payload()
                payload["authorized"] = False
                payload["gates"][gate] = True
                client = self._client(payload, "csrf-blocked")
                response = client.post(
                    "/api/bn-manager/v1/dashboard/evaluate",
                    json={},
                    headers={"x-csrf-token": "csrf-blocked"},
                )
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()["error"]["details"]["reason"], reason)

    def test_csrf_rejection_blocks_write_route(self) -> None:
        client = self._client(auth_v2_payload(), "csrf-good")
        response = client.post(
            "/api/bn-manager/v1/dashboard/evaluate",
            json={},
            headers={"x-csrf-token": "csrf-bad"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "BNM_FORBIDDEN")

    def _client(self, payload: dict, csrf_token: str) -> TestClient:
        session = replace(session_from_payload(payload), csrf_token=csrf_token)
        return TestClient(create_app(session_adapter=FakeSessionAdapter(session)))


if __name__ == "__main__":
    unittest.main()
