"""Authentication v2 contract tests for Diagnosis.

Run: ``python -m test_auth``.
"""
from __future__ import annotations

import unittest
from copy import deepcopy
from unittest import mock

from fastapi import HTTPException

from diagnosis import auth


def payload(role: str = "psychiatrist") -> dict:
    return {
        "authenticated": True,
        "authorized": True,
        "interfaceVersion": "2.0.0",
        "session": {"id": "11111111-1111-4111-8111-111111111111", "active": True, "expiresAt": "2999-01-01T00:00:00Z"},
        "user": {"id": "22222222-2222-4222-8222-222222222222", "username": "clinician", "role": role},
        "gates": {"passwordChangeRequired": False, "disclaimerRequired": False, "disclaimerVersion": "test-v1"},
        "compatibility": {"legacyUserId": 1, "legacyRole": "user"},
    }


class AuthenticationV2Test(unittest.TestCase):
    def test_accepts_authorized_canonical_role_and_uuids(self) -> None:
        session = auth._build_session(payload(), "2.4.0")
        self.assertEqual(session.roles, frozenset({"psychiatrist"}))
        self.assertEqual(session.user_id, "22222222-2222-4222-8222-222222222222")

    def test_rejects_wrong_interface_or_schema_major(self) -> None:
        wrong_interface = payload()
        wrong_interface["interfaceVersion"] = "1.0.0"
        for body, schema in ((wrong_interface, "2.0.0"), (payload(), "1.0.0")):
            with self.subTest(body=body, schema=schema), self.assertRaises(HTTPException):
                auth._build_session(body, schema)

    def test_rejects_unauthorized_gated_invalid_uuid_and_noncanonical_role(self) -> None:
        mutations = []
        for path, value in (
            (("authorized",), False),
            (("gates", "passwordChangeRequired"), True),
            (("gates", "disclaimerRequired"), True),
            (("session", "id"), "not-a-uuid"),
            (("user", "id"), "not-a-uuid"),
            (("user", "username"), ""),
            (("user", "role"), "PSYCHIATRIST"),
            (("compatibility", "legacyUserId"), 0),
        ):
            body = deepcopy(payload())
            target = body
            for key in path[:-1]:
                target = target[key]
            target[path[-1]] = value
            mutations.append(body)
        for body in mutations:
            with self.subTest(body=body), self.assertRaises(HTTPException):
                auth._build_session(body, "2.0.0")

    def test_role_dependency_forwards_cookie_and_enforces_role(self) -> None:
        request = mock.Mock()
        request.headers.get.return_value = "insight_session=test"
        with mock.patch.object(auth, "_fetch_session", return_value=(payload("admin"), "2.0.0")):
            with self.assertRaises(HTTPException) as raised:
                auth.require_role("psychiatrist")(request)
        self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main(verbosity=2)
