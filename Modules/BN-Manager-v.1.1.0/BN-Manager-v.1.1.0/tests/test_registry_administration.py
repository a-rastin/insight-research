from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from fastapi import Request
from fastapi.testclient import TestClient

from bn_manager_backend.auth_adapter import SessionState, session_from_payload
from bn_manager_backend.config import BnManagerSettings
from bn_manager_backend.main import create_app


class SessionAdapter:
    def __init__(self, role: str) -> None:
        canonical_role = "admin" if role == "Administrator" else "psychiatrist"
        self.session = replace(session_from_payload({
            "authenticated": True,
            "authorized": True,
            "interfaceVersion": "2.0.0",
            "session": {
                "id": "11111111-1111-4111-8111-111111111111",
                "active": True,
                "expiresAt": "2999-01-01T00:00:00Z",
            },
            "user": {
                "id": "22222222-2222-4222-8222-222222222222",
                "username": canonical_role,
                "role": canonical_role,
            },
            "gates": {
                "passwordChangeRequired": False,
                "disclaimerRequired": False,
                "disclaimerVersion": "test-v1",
            },
        }), csrf_token="csrf-admin")

    def fetch_session(self, request: Request) -> SessionState:
        return self.session


class RegistryAdministrationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        settings = replace(
            BnManagerSettings(),
            governance_db_path=Path(self.temporary.name) / "governance.sqlite3",
        )
        self.client = TestClient(create_app(settings=settings, session_adapter=SessionAdapter("Administrator")))

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_inventory_exposes_only_manifest_owned_models_and_evidence(self) -> None:
        response = self.client.get("/api/bn-manager/v3/admin/models")

        self.assertEqual(response.status_code, 200)
        inventory = response.json()["data"]["models"]
        self.assertEqual(len(inventory), 4)
        for model in inventory:
            self.assertTrue(model["manifest"]["artifact_id"].startswith("registry."))
            self.assertTrue(model["validation_evidence"]["valid"])
            self.assertTrue(model["validation_evidence"]["model_hash_matches_manifest"])
            self.assertEqual(model["lifecycle"]["status"], "draft")
            self.assertFalse(model["activation_eligible"])
            self.assertNotIn("text", model)

    def test_review_retire_and_rollback_are_attributable_and_persistent(self) -> None:
        stable_id = "bnm.treatment-setting"
        headers = {"x-csrf-token": "csrf-admin"}
        review = self.client.post(
            f"/api/bn-manager/v3/admin/models/{stable_id}/review",
            json={"rationale": "Structural and semantic evidence reviewed."},
            headers=headers,
        )
        self.assertEqual(review.status_code, 200)
        self.assertEqual(review.json()["data"]["model"]["lifecycle"]["status"], "reviewed")

        retire = self.client.post(
            f"/api/bn-manager/v3/admin/models/{stable_id}/retire",
            json={"rationale": "Retired pending formal manifest approval."},
            headers=headers,
        )
        self.assertEqual(retire.status_code, 200)
        rollback = self.client.post(
            f"/api/bn-manager/v3/admin/models/{stable_id}/rollback",
            json={"rationale": "Restore prior reviewed state after correction."},
            headers=headers,
        )
        lifecycle = rollback.json()["data"]["model"]["lifecycle"]
        self.assertEqual(lifecycle["status"], "reviewed")
        self.assertEqual(lifecycle["history"][-1]["action"], "rollback")
        self.assertEqual(lifecycle["history"][-1]["actor_id"], "22222222-2222-4222-8222-222222222222")

        detail = self.client.get(f"/api/bn-manager/v3/admin/models/{stable_id}")
        self.assertEqual(detail.json()["data"]["model"]["lifecycle"]["version"], 3)

    def test_activation_succeeds_when_manifest_approved(self) -> None:
        stable_id = "bnm.pharmacotherapy"
        headers = {"x-csrf-token": "csrf-admin"}
        self.client.post(
            f"/api/bn-manager/v3/admin/models/{stable_id}/review",
            json={"rationale": "Validation evidence reviewed for research use."},
            headers=headers,
        )
        response = self.client.post(
            f"/api/bn-manager/v3/admin/models/{stable_id}/activate",
            json={"rationale": "Request activation after evidence review."},
            headers=headers,
        )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["data"]["model"]["lifecycle"]["status"], "active")

    def test_non_admin_cannot_open_inventory_or_ui(self) -> None:
        settings = replace(
            BnManagerSettings(),
            governance_db_path=Path(self.temporary.name) / "other.sqlite3",
        )
        client = TestClient(create_app(settings=settings, session_adapter=SessionAdapter("Psychiatrist")))
        self.assertEqual(client.get("/api/bn-manager/v3/admin/models").status_code, 403)
        self.assertEqual(client.get("/modules/bn-manager").status_code, 403)

    def test_ui_is_bounded_relative_and_has_accessible_failure_state(self) -> None:
        response = self.client.get("/modules/bn-manager")
        self.assertEqual(response.status_code, 200)
        html = response.text
        self.assertIn('role="alert"', html)
        self.assertIn('aria-live="polite"', html)
        self.assertIn('const api = "/api/bn-manager/v3/admin/models"', html)
        self.assertNotIn("localStorage", html)
        self.assertNotIn("http://localhost", html)


if __name__ == "__main__":
    unittest.main()
