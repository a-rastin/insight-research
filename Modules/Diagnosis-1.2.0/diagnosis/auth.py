"""Strict Authentication v2 adapter for the Diagnosis module."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Iterable
from uuid import UUID

from fastapi import HTTPException, Request

from .config import settings

AUTH_BASE_URL = settings.auth_url
AUTH_TIMEOUT_S = settings.auth_timeout_s
AUTH_SESSION_PATH = "/api/auth/v2/session"
CANONICAL_ROLES = frozenset({"admin", "psychiatrist"})


@dataclass(frozen=True)
class Session:
    user_id: str
    roles: frozenset[str]
    session_id: str

    def has_any(self, allowed: Iterable[str]) -> bool:
        return any(role in self.roles for role in allowed)


class _AuthUnavailable(Exception):
    pass


def _major_is_2(value: object) -> bool:
    return isinstance(value, str) and value.split(".", 1)[0] == "2"


def _valid_uuid(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        UUID(value)
    except ValueError:
        return False
    return True


def _future_utc(value: object) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.astimezone(UTC) > datetime.now(UTC)


def _fetch_session(cookie_header: str | None) -> tuple[dict, str]:
    req = urllib.request.Request(f"{AUTH_BASE_URL.rstrip('/')}{AUTH_SESSION_PATH}", method="GET")
    if cookie_header:
        req.add_header("Cookie", cookie_header)
    try:
        with urllib.request.urlopen(req, timeout=AUTH_TIMEOUT_S) as response:
            body = response.read().decode("utf-8")
            schema_version = response.headers.get("X-Schema-Version", "")
    except urllib.error.HTTPError as error:
        try:
            if error.code in (401, 403):
                raise HTTPException(status_code=401, detail="Not authenticated") from error
            raise _AuthUnavailable(str(error)) from error
        finally:
            if error.fp:
                error.fp.close()
            error.close()
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        raise _AuthUnavailable(str(error)) from error
    try:
        payload = json.loads(body)
    except json.JSONDecodeError as error:
        raise _AuthUnavailable("non-JSON auth response") from error
    if not isinstance(payload, dict):
        raise _AuthUnavailable("auth response must be an object")
    return payload, schema_version


def _build_session(payload: dict, schema_version: str = "2.0.0") -> Session:
    session = payload.get("session")
    user = payload.get("user")
    gates = payload.get("gates")
    compatibility = payload.get("compatibility")
    if (
        not _major_is_2(payload.get("interfaceVersion"))
        or not _major_is_2(schema_version)
        or payload.get("authenticated") is not True
        or payload.get("authorized") is not True
        or not isinstance(session, dict)
        or not isinstance(user, dict)
        or not isinstance(gates, dict)
        or not isinstance(compatibility, dict)
        or not _valid_uuid(session.get("id"))
        or session.get("active") is not True
        or not _future_utc(session.get("expiresAt"))
        or not _valid_uuid(user.get("id"))
        or not isinstance(user.get("username"), str)
        or not user["username"]
        or user.get("role") not in CANONICAL_ROLES
        or gates.get("passwordChangeRequired") is not False
        or gates.get("disclaimerRequired") is not False
        or not isinstance(gates.get("disclaimerVersion"), str)
        or not gates["disclaimerVersion"]
        or isinstance(compatibility.get("legacyUserId"), bool)
        or not isinstance(compatibility.get("legacyUserId"), int)
        or compatibility["legacyUserId"] < 1
        or compatibility.get("legacyRole") not in ("user", None)
    ):
        raise HTTPException(status_code=401, detail="Not authenticated")
    return Session(
        user_id=user["id"],
        roles=frozenset({user["role"]}),
        session_id=session["id"],
    )


def require_role(*allowed: str):
    allowed_set = frozenset(allowed)

    def _dep(request: Request) -> Session:
        try:
            payload, schema_version = _fetch_session(request.headers.get("cookie"))
        except HTTPException:
            raise
        except _AuthUnavailable:
            raise HTTPException(status_code=401, detail="Not authenticated")
        session = _build_session(payload, schema_version)
        if not session.has_any(allowed_set):
            raise HTTPException(status_code=403, detail="Forbidden")
        return session

    return _dep


def reset_auth_for_tests(base_url: str | None = None) -> None:
    global AUTH_BASE_URL
    AUTH_BASE_URL = base_url if base_url is not None else settings.auth_url


__all__ = ["Session", "require_role", "reset_auth_for_tests", "AUTH_BASE_URL"]
