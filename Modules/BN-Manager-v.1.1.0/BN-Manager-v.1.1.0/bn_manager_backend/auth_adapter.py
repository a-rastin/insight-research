from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest
from urllib.request import urlopen

from fastapi import Request


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


def session_from_payload(payload: dict[str, Any]) -> SessionState:
    session = _unwrap_session_payload(payload)
    user = _as_dict(session.get("user"))
    subject = _first_text(session, user, keys=("id", "userId", "sub", "subject", "email"))
    roles = frozenset(_collect_roles(session, user))
    csrf_token = _first_text(session, user, keys=("csrfToken", "csrf_token", "xsrfToken", "xsrf_token"))
    expired = _is_expired(session)
    blocked_reason = _blocked_reason(session, user)

    active = _is_active(session) and not expired and blocked_reason is None
    return SessionState(
        active=active,
        subject=subject,
        roles=roles,
        csrf_token=csrf_token,
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


def _unwrap_session_payload(payload: dict[str, Any]) -> dict[str, Any]:
    data = payload.get("data")
    if isinstance(data, dict):
        session = data.get("session")
        if isinstance(session, dict):
            return session
        return data
    session = payload.get("session")
    if isinstance(session, dict):
        return session
    return payload


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _is_active(session: dict[str, Any]) -> bool:
    for key in ("authenticated", "isAuthenticated", "active", "valid"):
        if key in session:
            return bool(session[key])
    if session.get("status") in {"expired", "invalid", "anonymous"}:
        return False
    return True


def _is_expired(session: dict[str, Any]) -> bool:
    if bool(session.get("expired")) or session.get("status") == "expired":
        return True
    expires_at = _first_text(session, {}, keys=("expiresAt", "expires_at", "expires"))
    if not expires_at:
        return False
    try:
        parsed = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    except ValueError:
        return False
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed <= datetime.now(UTC)


def _blocked_reason(session: dict[str, Any], user: dict[str, Any]) -> str | None:
    for source in (session, user):
        if source.get("forcePasswordChange") or source.get("forcedPasswordChange"):
            return "forced_password_change"
        if source.get("passwordChangeRequired") or source.get("mustChangePassword"):
            return "forced_password_change"
        for key in ("disclaimerAccepted", "acceptedDisclaimer", "clinicalDisclaimerAccepted"):
            if key in source and not bool(source[key]):
                return "disclaimer_required"
    status = str(session.get("status", ""))
    if status in {"disclaimer_required", "forced_password_change", "password_change_required"}:
        return status
    return None


def _first_text(*sources: dict[str, Any], keys: tuple[str, ...]) -> str | None:
    for source in sources:
        for key in keys:
            value = source.get(key)
            if value is not None:
                text = str(value).strip()
                if text:
                    return text
    return None


def _collect_roles(session: dict[str, Any], user: dict[str, Any]) -> set[str]:
    raw_roles: list[Any] = []
    for source in (session, user):
        for key in ("roles", "role", "groups"):
            value = source.get(key)
            if isinstance(value, list | tuple | set):
                raw_roles.extend(value)
            elif value is not None:
                raw_roles.append(value)
    return {_normalize_role(str(role)) for role in raw_roles if str(role).strip()}


def _normalize_role(role: str) -> str:
    compact = re.sub(r"[\s_]+", "-", role.strip().lower())
    aliases = {
        "administrator": "admin",
        "system-admin": "admin",
        "psychiatry": "psychiatrist",
        "psychiatrist-clinician": "psychiatrist",
        "careteam": "care-team",
        "care-team-member": "care-team",
        "intakeclinician": "intake-clinician",
        "modelmanager": "model-manager",
    }
    return aliases.get(compact, compact)
