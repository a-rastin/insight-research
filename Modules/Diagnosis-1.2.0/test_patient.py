"""Patient adapter tests restored for the documented Diagnosis suite.

Run: ``python -m test_patient``.
"""
from __future__ import annotations

import unittest
import os
from unittest import mock

from fastapi import HTTPException

from diagnosis import patient


class PatientAdapterTest(unittest.TestCase):
    def test_disabled_lookup_preserves_explicit_legacy_adapter(self) -> None:
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("DIAGNOSIS_PATIENT_LOOKUP", None)
            result = patient.resolve_patient("P-0042-A", None)
        self.assertEqual(result.id, "P-0042-A")
        self.assertEqual(result.patient_code, "P-0042-A")

    def test_payload_requires_canonical_id(self) -> None:
        with self.assertRaises(HTTPException) as raised:
            patient._build_patient({"patient_code": "P-0042-A"}, "P-0042-A")
        self.assertEqual(raised.exception.status_code, 422)

    def test_enabled_lookup_forwards_cookie_and_returns_registry_identity(self) -> None:
        with mock.patch.dict(os.environ, {"DIAGNOSIS_PATIENT_LOOKUP": "1"}), mock.patch.object(
            patient,
            "_fetch_patient",
            return_value={"id": "11111111-1111-4111-8111-111111111111", "patient_code": "P-0042-A", "display_name": "Test"},
        ) as fetch:
            result = patient.resolve_patient("P-0042-A", "insight_session=test")
        fetch.assert_called_once_with("P-0042-A", "insight_session=test")
        self.assertEqual(result.id, "11111111-1111-4111-8111-111111111111")


if __name__ == "__main__":
    unittest.main(verbosity=2)
