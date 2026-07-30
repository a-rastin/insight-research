from __future__ import annotations

import hmac
import secrets
from hashlib import sha256

from fastapi import Request
from fastapi.responses import JSONResponse

from .config import settings

CSRF_COOKIE_NAME = "add_new_patient_csrf"
CSRF_HEADER_NAME = "x-csrf-token"
CSRF_WRITE_METHODS = {"POST", "PATCH"}


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def sign_csrf_token(token: str) -> str:
    signature = hmac.new(settings.csrf_secret.encode("utf-8"), token.encode("utf-8"), sha256).hexdigest()
    return f"{token}.{signature}"


def verify_csrf_token(token: str, signed_cookie: str) -> bool:
    cookie_token, separator, _ = signed_cookie.partition(".")
    if separator != "." or not token or not cookie_token:
        return False
    if not hmac.compare_digest(token, cookie_token):
        return False
    return hmac.compare_digest(sign_csrf_token(cookie_token), signed_cookie)


def csrf_error() -> JSONResponse:
    return JSONResponse(status_code=403, content={"error": "csrf_token_invalid"})


def request_has_valid_csrf(request: Request) -> bool:
    token = request.headers.get(CSRF_HEADER_NAME, "")
    signed_cookie = request.cookies.get(CSRF_COOKIE_NAME, "")
    return verify_csrf_token(token, signed_cookie)
