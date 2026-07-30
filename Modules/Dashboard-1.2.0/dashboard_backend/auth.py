from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen
from uuid import UUID

from fastapi import Request

from .config import settings


class AuthSessionError(Exception):
    pass


INTERFACE_VERSION = "2.0.0"
ROLES = {"admin": "ADMIN", "psychiatrist": "PSYCHIATRIST"}
ROOT_FIELDS = {
    "authenticated",
    "authorized",
    "interfaceVersion",
    "session",
    "user",
    "gates",
    "compatibility",
}


def auth_session_url(request: Request) -> str:
    if settings.auth_session_url:
        return settings.auth_session_url
    if settings.auth_base_url:
        return f"{settings.auth_base_url.rstrip('/')}/api/auth/v2/session"
    if settings.use_mock_auth:
        return f"{request.url.scheme}://{request.headers.get('host')}/api/auth/v2/session"
    return ""


def forwarded_auth_headers(
    request: Request, session: dict[str, Any] | None = None
) -> dict[str, str]:
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


def _valid_uuid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def _valid_future_utc(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith("Z"):
        return False
    try:
        expires_at = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError:
        return False
    return expires_at.tzinfo == UTC and expires_at > datetime.now(UTC)


def normalize_auth_identity(data: dict[str, Any]) -> dict[str, Any] | None:
    if set(data) != ROOT_FIELDS:
        return None
    if (
        data.get("authenticated") is not True
        or data.get("authorized") is not True
        or data.get("interfaceVersion") != INTERFACE_VERSION
    ):
        return None

    session = data.get("session")
    user = data.get("user")
    gates = data.get("gates")
    compatibility = data.get("compatibility")
    if not all(isinstance(part, dict) for part in [session, user, gates, compatibility]):
        return None

    if set(session) != {"id", "active", "expiresAt"}:
        return None
    if (
        not _valid_uuid(session.get("id"))
        or session.get("active") is not True
        or not _valid_future_utc(session.get("expiresAt"))
    ):
        return None

    if set(user) != {"id", "username", "role"}:
        return None
    username = user.get("username")
    role = user.get("role")
    if (
        not _valid_uuid(user.get("id"))
        or not isinstance(username, str)
        or not 1 <= len(username) <= 64
        or role not in ROLES
    ):
        return None

    if set(gates) != {"passwordChangeRequired", "disclaimerRequired", "disclaimerVersion"}:
        return None
    if (
        gates.get("passwordChangeRequired") is not False
        or gates.get("disclaimerRequired") is not False
        or not isinstance(gates.get("disclaimerVersion"), str)
        or not gates["disclaimerVersion"]
    ):
        return None

    if set(compatibility) != {"legacyUserId", "legacyRole"}:
        return None
    legacy_user_id = compatibility.get("legacyUserId")
    if (
        isinstance(legacy_user_id, bool)
        or not isinstance(legacy_user_id, int)
        or legacy_user_id < 1
        or compatibility.get("legacyRole") not in {"user", None}
    ):
        return None

    dashboard_role = ROLES[role]
    return {
        "authSessionId": session["id"],
        "user": {
            "id": user["id"],
            "role": dashboard_role,
            "fullName": username,
            "title": "Dr." if dashboard_role == "PSYCHIATRIST" else "",
        },
    }


def _fetch_json(endpoint: str, headers: dict[str, str]) -> dict[str, Any] | None:
    req = UrlRequest(endpoint, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=settings.auth_session_timeout_seconds) as response:
            if response.status in [401, 403]:
                return None
            if response.status < 200 or response.status >= 300:
                raise AuthSessionError(
                    f"Authentication session check failed with {response.status}"
                )
            if response.headers.get("x-schema-version") != INTERFACE_VERSION:
                raise AuthSessionError("Authentication session schema version is unsupported")
            try:
                data = json.loads(response.read().decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise AuthSessionError("Authentication session response is invalid") from error
            if not isinstance(data, dict):
                raise AuthSessionError("Authentication session response is invalid")
            return data
    except HTTPError as error:
        try:
            if error.code in [401, 403]:
                return None
            raise AuthSessionError(
                f"Authentication session check failed with {error.code}"
            ) from error
        finally:
            if error.fp:
                error.fp.close()
            error.close()
    except URLError as error:
        raise AuthSessionError(str(error.reason)) from error


async def fetch_auth_identity(
    request: Request, session: dict[str, Any] | None = None
) -> dict[str, Any] | None:
    endpoint = auth_session_url(request)
    if not endpoint:
        raise AuthSessionError("Authentication session endpoint is not configured")
    data = await asyncio.to_thread(
        _fetch_json, endpoint, forwarded_auth_headers(request, session)
    )
    return normalize_auth_identity(data) if data else None
