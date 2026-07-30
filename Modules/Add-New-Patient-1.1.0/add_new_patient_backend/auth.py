from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from fastapi import Request

from .config import settings


class AuthSessionError(Exception):
    pass


AUTH_INTERFACE_MAJOR = 2
CANONICAL_ROLES = frozenset({"admin", "psychiatrist"})


def auth_session_url(request: Request) -> str:
    if settings.auth_session_url:
        return settings.auth_session_url
    if settings.auth_base_url:
        return f"{settings.auth_base_url.rstrip('/')}/api/auth/v2/session"
    if settings.use_mock_auth:
        return f"{request.url.scheme}://{request.headers.get('host')}/api/auth/v2/session"
    return ""


def forwarded_auth_headers(request: Request, session: dict[str, Any] | None = None) -> dict[str, str]:
    headers = {"accept": "application/json"}
    for name in ["authorization", "cookie", "x-auth-session", "x-auth-session-id"]:
        value = request.headers.get(name)
        if value:
            headers[name] = value
    demo_user = request.headers.get("x-demo-auth-user")
    if settings.use_mock_auth and demo_user:
        headers["x-demo-auth-user"] = demo_user
    if session and session.get("authSessionId") and "x-auth-session" not in headers:
        headers["x-auth-session"] = session["authSessionId"]
    return headers


def _parse_expiry(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _is_uuid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def _has_major_2(value: Any) -> bool:
    return isinstance(value, str) and value.split(".", 1)[0] == str(AUTH_INTERFACE_MAJOR)


PSYCHIATRIST_ROLE = "psychiatrist"


def normalize_authenticated_session(data: dict[str, Any], schema_version: str = "2.0.0") -> dict[str, Any] | None:
    if not _has_major_2(data.get("interfaceVersion")) or not _has_major_2(schema_version):
        return None
    if data.get("authenticated") is not True or data.get("authorized") is not True:
        return None
    session = data.get("session")
    user = data.get("user")
    gates = data.get("gates")
    compatibility = data.get("compatibility")
    if not all(isinstance(part, dict) for part in (session, user, gates, compatibility)):
        return None
    auth_session_id = session.get("id")
    user_id = user.get("id")
    role = user.get("role")
    expiry = _parse_expiry(session.get("expiresAt"))
    if (
        not _is_uuid(auth_session_id)
        or session.get("active") is not True
        or expiry is None
        or expiry <= datetime.now(UTC)
        or not _is_uuid(user_id)
        or not isinstance(user.get("username"), str)
        or not user["username"]
        or role not in CANONICAL_ROLES
        or gates.get("passwordChangeRequired") is not False
        or gates.get("disclaimerRequired") is not False
        or not isinstance(gates.get("disclaimerVersion"), str)
        or not gates["disclaimerVersion"]
        or isinstance(compatibility.get("legacyUserId"), bool)
        or not isinstance(compatibility.get("legacyUserId"), int)
        or compatibility["legacyUserId"] < 1
        or compatibility.get("legacyRole") not in ("user", None)
    ):
        return None
    return {
        "authSessionId": auth_session_id,
        "user": {
            "id": user_id,
            "role": role,
            "username": user["username"],
        },
    }


def normalize_psychiatrist_session(data: dict[str, Any], schema_version: str = "2.0.0") -> dict[str, Any] | None:
    identity = normalize_authenticated_session(data, schema_version)
    if not identity or identity["user"].get("role") != PSYCHIATRIST_ROLE:
        return None
    return identity


def _fetch_json(endpoint: str, headers: dict[str, str]) -> tuple[dict[str, Any], str] | None:
    req = UrlRequest(endpoint, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=settings.auth_session_timeout_seconds) as response:
            if response.status in [401, 403]:
                return None
            if response.status < 200 or response.status >= 300:
                raise AuthSessionError(f"Authentication session check failed with {response.status}")
            try:
                payload = json.loads(response.read().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise AuthSessionError("Authentication session response was not valid JSON") from error
            if not isinstance(payload, dict):
                raise AuthSessionError("Authentication session response must be an object")
            return payload, response.headers.get("X-Schema-Version", "")
    except HTTPError as error:
        try:
            if error.code in [401, 403]:
                return None
            raise AuthSessionError(f"Authentication session check failed with {error.code}") from error
        finally:
            if error.fp:
                error.fp.close()
            error.close()
    except URLError as error:
        raise AuthSessionError(str(error.reason)) from error


async def fetch_auth_identity(
    request: Request,
    session: dict[str, Any] | None = None,
    *,
    require_psychiatrist: bool = False,
) -> dict[str, Any] | None:
    endpoint = auth_session_url(request)
    if not endpoint:
        raise AuthSessionError("Authentication session endpoint is not configured")
    response = await asyncio.to_thread(_fetch_json, endpoint, forwarded_auth_headers(request, session))
    if not response:
        return None
    data, schema_version = response
    normalizer = normalize_psychiatrist_session if require_psychiatrist else normalize_authenticated_session
    return normalizer(data, schema_version)


normalize_auth_identity = normalize_psychiatrist_session
