from __future__ import annotations

import unittest

from fastapi import Request
from fastapi.testclient import TestClient

from bn_manager_backend.auth_adapter import SessionState, session_from_payload
from bn_manager_backend.main import create_app


class FakeSessionAdapter:
    def __init__(self, session: SessionState) -> None:
        self.session = session

    def fetch_session(self, request: Request) -> SessionState:
        return self.session


class AuthenticationGuardTests(unittest.TestCase):
    def test_valid_psychiatrist_can_evaluate_registered_xml_model(self) -> None:
        client = self._client(
            {
                "authenticated": True,
                "user": {"id": "psy-1", "roles": [" PSYCHIATRIST "]},
                "csrfToken": "csrf-1",
            }
        )
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
        client = self._client(
            {
                "authenticated": True,
                "user": {"id": "admin-1", "roles": ["Administrator"]},
                "csrfToken": "csrf-2",
            }
        )
        response = client.post(
            "/api/bn-manager/v1/models/validate",
            json={"model": {"model_id": "bnm.pharmacotherapy"}},
            headers={"x-csrf-token": "csrf-2"},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["data"]["valid"])
        self.assertEqual(payload["data"]["checked_by"], "admin-1")

    def test_expired_session_is_rejected_before_model_loading(self) -> None:
        client = self._client(
            {
                "authenticated": True,
                "roles": ["Psychiatrist"],
                "csrfToken": "csrf-3",
                "expiresAt": "2000-01-01T00:00:00Z",
            }
        )
        response = client.post(
            "/api/bn-manager/v1/dashboard/evaluate",
            json={},
            headers={"x-csrf-token": "csrf-3"},
        )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"]["code"], "BNM_UNAUTHORIZED")

    def test_disclaimer_and_forced_password_sessions_are_blocked(self) -> None:
        blocked_payloads = (
            ({"authenticated": True, "roles": ["Psychiatrist"], "csrfToken": "csrf-4", "disclaimerAccepted": False}, "disclaimer_required"),
            ({"authenticated": True, "roles": ["Psychiatrist"], "csrfToken": "csrf-5", "forcePasswordChange": True}, "forced_password_change"),
        )
        for session_payload, reason in blocked_payloads:
            with self.subTest(reason=reason):
                client = self._client(session_payload)
                response = client.post(
                    "/api/bn-manager/v1/dashboard/evaluate",
                    json={},
                    headers={"x-csrf-token": str(session_payload["csrfToken"])},
                )
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.json()["error"]["details"]["reason"], reason)

    def test_csrf_rejection_blocks_write_route(self) -> None:
        client = self._client(
            {
                "authenticated": True,
                "roles": ["Psychiatrist"],
                "csrfToken": "csrf-good",
            }
        )
        response = client.post(
            "/api/bn-manager/v1/dashboard/evaluate",
            json={},
            headers={"x-csrf-token": "csrf-bad"},
        )

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["error"]["code"], "BNM_FORBIDDEN")

    def _client(self, payload: dict) -> TestClient:
        return TestClient(create_app(session_adapter=FakeSessionAdapter(session_from_payload(payload))))


if __name__ == "__main__":
    unittest.main()
