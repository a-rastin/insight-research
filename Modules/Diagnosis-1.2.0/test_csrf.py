"""Signed double-submit CSRF tests for Diagnosis.

Run: ``python -m test_csrf``.
"""
from __future__ import annotations

import os
import unittest
from unittest import mock

from fastapi import HTTPException

from diagnosis import csrf


class CsrfTest(unittest.TestCase):
    def setUp(self) -> None:
        self.auth_bypass = os.environ.get("DIAGNOSIS_AUTH_BYPASS")
        os.environ.pop("DIAGNOSIS_AUTH_BYPASS", None)
        csrf.reset_secret_for_tests(b"csrf-test-secret")

    def tearDown(self) -> None:
        csrf.reset_secret_for_tests()
        if self.auth_bypass is None:
            os.environ.pop("DIAGNOSIS_AUTH_BYPASS", None)
        else:
            os.environ["DIAGNOSIS_AUTH_BYPASS"] = self.auth_bypass

    def request(self, cookie: str | None, header: str | None):
        request = mock.Mock()
        request.cookies.get.return_value = cookie
        request.headers.get.return_value = header
        return request

    def test_signed_token_round_trip(self) -> None:
        token = csrf.mint()
        self.assertTrue(csrf._verify(token))
        csrf.require_csrf(self.request(token, token))

    def test_missing_mismatched_and_invalid_tokens_fail_closed(self) -> None:
        valid = csrf.mint()
        invalid = "0" * 32 + ".invalid"
        for cookie, header in ((None, None), (valid, None), (None, valid), (valid, csrf.mint()), (invalid, invalid)):
            with self.subTest(cookie=cookie, header=header), self.assertRaises(HTTPException) as raised:
                csrf.require_csrf(self.request(cookie, header))
            self.assertEqual(raised.exception.status_code, 403)


if __name__ == "__main__":
    unittest.main(verbosity=2)
