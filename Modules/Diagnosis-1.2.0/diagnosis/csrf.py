"""Signed double-submit CSRF for Diagnosis write routes."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets

from fastapi import HTTPException, Request

from .config import settings

COOKIE_NAME = "csrf"
HEADER_NAME = "X-CSRF-Token"
_SECRET = settings.csrf_secret if settings.csrf_secret is not None else secrets.token_bytes(32)
_SECURE_COOKIE = settings.csrf_secure


def _sign(raw: str) -> str:
    signature = hmac.new(_SECRET, raw.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{raw}.{signature}"


def _verify(token: str) -> bool:
    if not token or "." not in token:
        return False
    raw, _, signature = token.rpartition(".")
    if not raw or not signature:
        return False
    expected = hmac.new(_SECRET, raw.encode("utf-8"), hashlib.sha256).hexdigest()
    return hmac.compare_digest(signature, expected)


def mint() -> str:
    return _sign(secrets.token_hex(16))


def set_cookie(response, token: str) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        httponly=False,
        secure=_SECURE_COOKIE,
        samesite="lax",
        path="/",
    )


def require_csrf(request: Request) -> None:
    if os.environ.get("DIAGNOSIS_AUTH_BYPASS") == "1":
        return
    cookie = request.cookies.get(COOKIE_NAME)
    header = request.headers.get(HEADER_NAME)
    if not cookie or not header:
        raise HTTPException(status_code=403, detail="CSRF token missing")
    if not hmac.compare_digest(cookie, header):
        raise HTTPException(status_code=403, detail="CSRF token mismatch")
    if not _verify(cookie) or not _verify(header):
        raise HTTPException(status_code=403, detail="CSRF token invalid")


def reset_secret_for_tests(secret: bytes | None = None) -> None:
    global _SECRET
    _SECRET = secrets.token_bytes(32) if secret is None else secret


__all__ = [
    "COOKIE_NAME", "HEADER_NAME", "mint", "set_cookie", "require_csrf",
    "reset_secret_for_tests", "_sign", "_verify",
]
