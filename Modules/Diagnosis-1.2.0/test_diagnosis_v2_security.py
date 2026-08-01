from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from uuid import uuid4

from fastapi import HTTPException
from fastapi.testclient import TestClient

from diagnosis import auth, csrf, v2
from diagnosis.app import app
from diagnosis.store import DiagnosisStore


def auth_payload(role: str) -> dict:
    return {
        "authenticated": True,
        "authorized": True,
        "interfaceVersion": "2.0.0",
        "session": {
            "id": str(uuid4()),
            "active": True,
            "expiresAt": "2999-01-01T00:00:00Z",
        },
        "user": {"id": str(uuid4()), "username": "clinician", "role": role},
        "gates": {
            "passwordChangeRequired": False,
            "disclaimerRequired": False,
            "disclaimerVersion": "test-v1",
        },
        "compatibility": {"legacyUserId": 1, "legacyRole": "user"},
    }


class DiagnosisV2SecurityTest(unittest.TestCase):
    def setUp(self) -> None:
        self.auth_bypass = os.environ.pop("DIAGNOSIS_AUTH_BYPASS", None)
        self.temp = tempfile.TemporaryDirectory()
        self.store = DiagnosisStore(str(Path(self.temp.name) / "diagnosis.db"))
        self.store_patch = mock.patch.object(v2, "store", self.store)
        self.patient_patch = mock.patch.object(v2, "validate_patient_encounter", return_value=None)
        self.store_patch.start()
        self.patient_patch.start()
        csrf.reset_secret_for_tests(b"diagnosis-v2-security")
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.patient_patch.stop()
        self.store_patch.stop()
        csrf.reset_secret_for_tests()
        if self.store._conn is not None:
            self.store._conn.close()
        self.temp.cleanup()
        if self.auth_bypass is not None:
            os.environ["DIAGNOSIS_AUTH_BYPASS"] = self.auth_bypass

    def create(self):
        token = csrf.mint()
        self.client.cookies.set("csrf", token)
        return self.client.post(
            "/api/diagnosis/v2/assessments",
            headers={
                "X-Schema-Version": "2.0.0",
                "Idempotency-Key": "diagnosis-security-key",
                "X-CSRF-Token": token,
            },
            json={"patientId": str(uuid4()), "encounterId": str(uuid4())},
        )

    def test_unauthenticated_create_fails_before_csrf(self) -> None:
        with mock.patch.object(
            auth,
            "_fetch_session",
            side_effect=HTTPException(status_code=401, detail="Not authenticated"),
        ):
            response = self.client.post(
                "/api/diagnosis/v2/assessments",
                headers={"X-Schema-Version": "2.0.0", "Idempotency-Key": "diagnosis-security-key"},
                json={"patientId": str(uuid4()), "encounterId": str(uuid4())},
            )
        self.assertEqual(response.status_code, 401, response.text)
        self.assertEqual(response.json()["code"], "COMMON_AUTHENTICATION_REQUIRED")

    def test_admin_cannot_create_and_missing_csrf_is_rejected(self) -> None:
        with mock.patch.object(auth, "_fetch_session", return_value=(auth_payload("admin"), "2.0.0")):
            admin = self.create()
        self.assertEqual(admin.status_code, 403, admin.text)
        self.assertEqual(admin.json()["code"], "COMMON_FORBIDDEN")

        self.client.cookies.clear()
        with mock.patch.object(auth, "_fetch_session", return_value=(auth_payload("psychiatrist"), "2.0.0")):
            no_csrf = self.client.post(
                "/api/diagnosis/v2/assessments",
                headers={"X-Schema-Version": "2.0.0", "Idempotency-Key": "diagnosis-security-key"},
                json={"patientId": str(uuid4()), "encounterId": str(uuid4())},
            )
        self.assertEqual(no_csrf.status_code, 403, no_csrf.text)

    def test_psychiatrist_with_csrf_can_create(self) -> None:
        with mock.patch.object(auth, "_fetch_session", return_value=(auth_payload("psychiatrist"), "2.0.0")):
            response = self.create()
        self.assertEqual(response.status_code, 201, response.text)
        self.assertIn("ETag", response.headers)
        self.assertIn("X-Request-ID", response.headers)


if __name__ == "__main__":
    unittest.main(verbosity=2)
