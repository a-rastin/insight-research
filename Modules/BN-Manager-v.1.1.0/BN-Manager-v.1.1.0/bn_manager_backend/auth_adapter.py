from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest
from urllib.request import urlopen
from uuid import UUID

from fastapi import Request

CANONICAL_ROLES = frozenset({"admin", "psychiatrist"})


@dataclass(frozen=True, slots=True)
class SessionState:
    active: bool
    subject: str | None = None
    roles: frozenset[str] = frozenset()
    csrf_token: str | None = None
    blocked_reason: str | None = None
    expired: bool = False


class SessionAdapter(Protocol):
    def fetch_session(self, request: Request) -> SessionState:
        ...


class AuthenticationRestAdapter:
    def __init__(self, session_url: str, timeout_seconds: float = 2.0) -> None:
        self.session_url = session_url
        self.timeout_seconds = timeout_seconds

    def fetch_session(self, request: Request) -> SessionState:
        outbound = UrlRequest(self.session_url, method="GET")
        for header_name in ("authorization", "cookie", "x-request-id"):
            value = request.headers.get(header_name)
            if value:
                outbound.add_header(header_name, value)

        try:
            with urlopen(outbound, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return SessionState(active=False, expired=exc.code == 401)
        except (OSError, URLError, ValueError):
            return SessionState(active=False)

        return session_from_payload(payload)


def session_from_payload(payload: Any) -> SessionState:
    if not isinstance(payload, dict):
        return SessionState(active=False)
    session = _as_dict(payload.get("session"))
    user = _as_dict(payload.get("user"))
    gates = _as_dict(payload.get("gates"))
    subject = user.get("id") if _is_canonical_uuid(user.get("id")) else None
    role = user.get("role")
    roles = frozenset({role}) if isinstance(role, str) and role in CANONICAL_ROLES else frozenset()
    expires_at = _parse_expiry(session.get("expiresAt"))
    expired = expires_at is not None and expires_at <= datetime.now(UTC)
    blocked_reason = _blocked_reason(gates)

    active = (
        payload.get("authenticated") is True
        and payload.get("authorized") is True
        and payload.get("interfaceVersion") == "2.0.0"
        and _is_canonical_uuid(session.get("id"))
        and session.get("active") is True
        and expires_at is not None
        and not expired
        and subject is not None
        and bool(roles)
        and gates.get("passwordChangeRequired") is False
        and gates.get("disclaimerRequired") is False
    )
    return SessionState(
        active=active,
        subject=subject,
        roles=roles,
        blocked_reason=blocked_reason,
        expired=expired,
    )


def assert_csrf_token(request: Request, session: SessionState, header_name: str) -> None:
    supplied = request.headers.get(header_name)
    expected = (
        session.csrf_token
        or request.cookies.get("csrf_token")
        or request.cookies.get("XSRF-TOKEN")
        or request.cookies.get("xsrf_token")
    )
    if not supplied or not expected or not secrets.compare_digest(supplied, expected):
        raise CsrfError


class CsrfError(Exception):
    pass


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _parse_expiry(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return None
    return parsed.astimezone(UTC)


def _is_canonical_uuid(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        return str(UUID(value)) == value
    except ValueError:
        return False


def _blocked_reason(gates: dict[str, Any]) -> str | None:
    if gates.get("passwordChangeRequired") is True:
        return "forced_password_change"
    if gates.get("disclaimerRequired") is True:
        return "disclaimer_required"
    return None
