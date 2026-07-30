from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock
from uuid import uuid4

os.environ["DIAGNOSIS_AUTH_BYPASS"] = "1"
os.environ.pop("DIAGNOSIS_PATIENT_LOOKUP", None)

from fastapi import HTTPException
from fastapi.testclient import TestClient

from diagnosis import dashboard, diagnosis_api, v2
from diagnosis.app import app
from diagnosis.store import DiagnosisStore


ROOT = Path(__file__).resolve().parent
SCHEMA = ROOT / "schema" / "diagnosis-assessment-v2.schema.json"
OPENAPI = ROOT / "schema" / "diagnosis-assessment-v2.openapi.json"
PREFIX = "/api/diagnosis/v2"


class DiagnosisV2ContractTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = DiagnosisStore(str(Path(self.temp.name) / "diagnosis.db"))
        self.patches = [
            mock.patch.object(v2, "store", self.store),
            mock.patch.object(diagnosis_api, "store", self.store),
            mock.patch.object(dashboard, "store", self.store),
            mock.patch.object(v2, "validate_patient_encounter", return_value=None),
        ]
        for patch in self.patches:
            patch.start()
        self.client = TestClient(app)
        self.patient_id = str(uuid4())
        self.encounter_id = str(uuid4())

    def tearDown(self) -> None:
        for patch in reversed(self.patches):
            patch.stop()
        if self.store._conn is not None:
            self.store._conn.close()
        self.temp.cleanup()

    def create(self, key: str = "diagnosis-v2-key-0001"):
        return self.client.post(
            f"{PREFIX}/assessments",
            headers={"X-Schema-Version": "2.0.0", "Idempotency-Key": key},
            json={"patientId": self.patient_id, "encounterId": self.encounter_id},
        )

    def test_contract_live_route_parity_and_uuid_only_urls(self) -> None:
        schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        openapi = json.loads(OPENAPI.read_text(encoding="utf-8"))
        self.assertEqual(schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(openapi["openapi"], "3.1.0")
        self.assertEqual(openapi["info"]["version"], "2.0.0")
        documented = set(openapi["paths"])
        live = {path for path in app.openapi()["paths"] if path.startswith(PREFIX)}
        self.assertEqual(documented, live)
        self.assertFalse(any("code" in path.lower() or "alias" in path.lower() for path in live))
        discovery = self.client.get(f"{PREFIX}/contract")
        self.assertEqual(discovery.status_code, 200)
        self.assertEqual(discovery.json()["ruleVersions"], ["diagnosis-rules-1.0.0"])
        self.assertEqual(self.client.get(discovery.json()["openapiPath"]).json(), openapi)
        self.assertEqual(self.client.get(f"{PREFIX}/diagnosis-assessment-v2.schema.json").json(), schema)

    def test_idempotent_init_and_unknown_patient_encounter(self) -> None:
        first = self.create()
        replay = self.create()
        self.assertEqual(first.status_code, 201, first.text)
        self.assertEqual(first.json(), replay.json())
        self.assertEqual(replay.headers["Idempotency-Replayed"], "true")
        self.assertEqual(first.json()["patientId"], self.patient_id)
        self.assertEqual(first.json()["encounterId"], self.encounter_id)
        self.assertEqual(first.json()["status"], "initialized")
        self.assertIsNone(first.json()["clinicianDecision"])

        with mock.patch.object(v2, "validate_patient_encounter", side_effect=HTTPException(404, "Patient or encounter was not found")):
            missing = self.client.post(
                f"{PREFIX}/assessments",
                headers={"X-Schema-Version": "2.0.0", "Idempotency-Key": "diagnosis-v2-key-0002"},
                json={"patientId": str(uuid4()), "encounterId": str(uuid4())},
            )
        self.assertEqual(missing.status_code, 404)

    def test_idempotency_key_rejects_changed_payload(self) -> None:
        first = self.create("diagnosis-v2-key-changed")
        self.assertEqual(first.status_code, 201, first.text)
        changed = self.client.post(
            f"{PREFIX}/assessments",
            headers={"X-Schema-Version": "2.0.0", "Idempotency-Key": "diagnosis-v2-key-changed"},
            json={"patientId": self.patient_id, "encounterId": str(uuid4())},
        )
        self.assertEqual(changed.status_code, 409, changed.text)
        self.assertEqual(changed.json()["code"], "COMMON_IDEMPOTENCY_KEY_REUSED")

    def test_update_requires_if_match(self) -> None:
        created = self.create("diagnosis-v2-key-if-match")
        assessment_id = created.json()["assessmentId"]
        response = self.client.put(
            f"{PREFIX}/assessments/{assessment_id}",
            headers={"X-Schema-Version": "2.0.0"},
            json={"checkedCriteria": [], "clinicianDecision": None},
        )
        self.assertEqual(response.status_code, 428, response.text)
        self.assertEqual(response.json()["code"], "COMMON_PRECONDITION_REQUIRED")

    def test_confirmed_requires_met_server_evaluation_but_bypass_remains_valid(self) -> None:
        created = self.create("diagnosis-v2-key-confirm-gate")
        assessment_id = created.json()["assessmentId"]
        confirmed = self.client.put(
            f"{PREFIX}/assessments/{assessment_id}",
            headers={"X-Schema-Version": "2.0.0", "If-Match": created.headers["ETag"]},
            json={"checkedCriteria": ["A1"], "clinicianDecision": {"type": "confirmed"}},
        )
        self.assertEqual(confirmed.status_code, 422, confirmed.text)
        self.assertEqual(confirmed.json()["code"], "DIAGNOSIS_CONFIRMATION_REQUIRES_MET_CRITERIA")

        bypass = self.client.put(
            f"{PREFIX}/assessments/{assessment_id}",
            headers={"X-Schema-Version": "2.0.0", "If-Match": created.headers["ETag"]},
            json={"checkedCriteria": ["A1"], "clinicianDecision": {"type": "bypass"}},
        )
        self.assertEqual(bypass.status_code, 200, bypass.text)
        self.assertFalse(bypass.json()["evaluation"]["met"])
        self.assertEqual(bypass.json()["clinicianDecision"]["type"], "bypass")

    def test_authority_stale_write_snapshot_and_audit_order(self) -> None:
        created = self.create()
        assessment_id = created.json()["assessmentId"]
        initial_etag = created.headers["ETag"]

        undecided = self.client.put(
            f"{PREFIX}/assessments/{assessment_id}",
            headers={"X-Schema-Version": "2.0.0", "If-Match": initial_etag},
            json={
                "checkedCriteria": ["A1", "A5", "A6", "B1", "C1", "D1"],
                "clinicianDecision": None,
            },
        )
        self.assertEqual(undecided.status_code, 200, undecided.text)
        self.assertTrue(undecided.json()["evaluation"]["met"])
        self.assertIsNone(undecided.json()["clinicianDecision"])
        self.assertEqual(undecided.json()["status"], "in-progress")

        stale = self.client.put(
            f"{PREFIX}/assessments/{assessment_id}",
            headers={"X-Schema-Version": "2.0.0", "If-Match": initial_etag},
            json={"checkedCriteria": ["A1"], "clinicianDecision": {"type": "bypass"}},
        )
        self.assertEqual(stale.status_code, 412)

        bypass = self.client.put(
            f"{PREFIX}/assessments/{assessment_id}",
            headers={"X-Schema-Version": "2.0.0", "If-Match": undecided.headers["ETag"]},
            json={"checkedCriteria": ["A1"], "clinicianDecision": {"type": "bypass"}},
        )
        self.assertEqual(bypass.status_code, 200, bypass.text)
        self.assertFalse(bypass.json()["evaluation"]["met"])
        self.assertEqual(bypass.json()["clinicianDecision"]["type"], "bypass")
        self.assertEqual(bypass.json()["clinicianDecision"]["actorUserId"], "selfcheck")
        self.assertEqual(bypass.json()["status"], "decided")

        snapshot = self.client.get(f"{PREFIX}/encounters/{self.encounter_id}/assessment-snapshot")
        self.assertEqual(snapshot.status_code, 200)
        self.assertEqual(snapshot.json(), bypass.json())
        audit = self.client.get(f"{PREFIX}/assessments/{assessment_id}/audit").json()["events"]
        self.assertEqual([event["eventType"] for event in audit], ["initialized", "updated", "updated"])
        self.assertEqual([event["resourceVersion"] for event in audit], [1, 2, 3])

    def test_legacy_adapter_evaluation_and_decision_equivalence(self) -> None:
        checked = ["A1", "A5", "A6", "B1", "C1", "D1"]
        legacy = self.client.put("/diagnosis/LEGACY1", json={"checked": checked, "decision": "confirmed"})
        created = self.create()
        current = created.json()
        modern = self.client.put(
            f"{PREFIX}/assessments/{current['assessmentId']}",
            headers={"X-Schema-Version": "2.0.0", "If-Match": created.headers["ETag"]},
            json={"checkedCriteria": checked, "clinicianDecision": {"type": "confirmed"}},
        )
        self.assertEqual(legacy.status_code, 200, legacy.text)
        self.assertEqual(modern.status_code, 200, modern.text)
        self.assertEqual(legacy.json()["evaluation"]["met"], modern.json()["evaluation"]["met"])
        self.assertEqual(legacy.json()["evaluation"]["a_count"], modern.json()["evaluation"]["aCount"])
        self.assertEqual(legacy.json()["decision"], modern.json()["clinicianDecision"]["type"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
