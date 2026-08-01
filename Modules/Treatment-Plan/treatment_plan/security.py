from __future__ import annotations

import hmac
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Mapping, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from .observability import Observability, current_observability
class AuthenticationUnavailable(RuntimeError): pass
class AccessDenied(RuntimeError): pass
class Capability(str, Enum):
    SESSION="session"; PLAN_READ="plan:read"; PLAN_MUTATE="plan:mutate"
    SUPPORT_READ="support:read"; AUDIT_READ="audit:read"
@dataclass(frozen=True)
class Session:
    user_id: str; roles: frozenset[str]; expires_at: datetime; csrf_token: str
    enabled: bool=True; permissions: frozenset[str]=frozenset(); session_id: str=""
class AuthenticationPort(Protocol):
    def verify(self, cookie: str) -> Session: ...
class HttpAuthenticationAdapter:
    """Parse only Authentication's canonical nested v2 session contract."""

    def __init__(self, session_url: str, timeout_seconds: float = 3.0):
        self._session_url, self._timeout = session_url, timeout_seconds

    def configured_for(self, session_url: str) -> bool:
        return self._session_url == session_url and self._timeout > 0

    def verify(self, cookie: str) -> Session:
        if not cookie:
            raise AccessDenied("session cookie is required")
        request = Request(self._session_url, headers={"Cookie": cookie, "Accept": "application/json"})
        try:
            with urlopen(request, timeout=self._timeout) as response:
                payload = json.load(response)
        except HTTPError as exc:
            if exc.code in {401, 403}:
                raise AccessDenied("session is invalid") from exc
            raise AuthenticationUnavailable("Authentication rejected the request") from exc
        except (URLError, TimeoutError, ValueError) as exc:
            raise AuthenticationUnavailable("Authentication is unavailable") from exc
        try:
            return self._parse(payload)
        except (KeyError, TypeError, ValueError) as exc:
            raise AuthenticationUnavailable("Authentication returned an invalid session") from exc

    @staticmethod
    def _parse(payload: Any) -> Session:
        _exact_object(payload, {"authenticated", "authorized", "interfaceVersion", "session", "user", "gates", "compatibility"})
        if payload["authenticated"] is not True or payload["authorized"] is not True:
            raise AccessDenied("Authentication session gates are not satisfied")
        if payload["interfaceVersion"] != "2.0.0":
            raise ValueError("unsupported Authentication interface")

        session = payload["session"]
        user = payload["user"]
        gates = payload["gates"]
        compatibility = payload["compatibility"]
        _exact_object(session, {"id", "active", "expiresAt"})
        _exact_object(user, {"id", "username", "role"})
        _exact_object(gates, {"passwordChangeRequired", "disclaimerRequired", "disclaimerVersion"})
        _exact_object(compatibility, {"legacyUserId", "legacyRole"})
        if session["active"] is not True:
            raise AccessDenied("Authentication session is inactive")
        if gates["passwordChangeRequired"] is not False or gates["disclaimerRequired"] is not False:
            raise AccessDenied("Authentication session gates are not satisfied")
        if not isinstance(gates["disclaimerVersion"], str) or not gates["disclaimerVersion"].strip():
            raise ValueError("invalid disclaimer version")
        if not isinstance(user["username"], str) or not user["username"].strip():
            raise ValueError("invalid username")
        if user["role"] not in {"admin", "psychiatrist"}:
            raise ValueError("invalid role")
        user_id = _canonical_uuid(user["id"])
        session_id = _canonical_uuid(session["id"])
        expires_at = session["expiresAt"]
        if not isinstance(expires_at, str) or not expires_at.endswith("Z"):
            raise ValueError("invalid expiry")
        expires = datetime.fromisoformat(expires_at[:-1] + "+00:00")
        if expires.utcoffset() != timezone.utc.utcoffset(expires):
            raise ValueError("invalid expiry timezone")
        if not isinstance(compatibility["legacyUserId"], int) or isinstance(compatibility["legacyUserId"], bool) or compatibility["legacyUserId"] < 1:
            raise ValueError("invalid legacy user ID")
        expected_legacy_role = "user" if user["role"] == "psychiatrist" else None
        if compatibility["legacyRole"] != expected_legacy_role:
            raise ValueError("invalid legacy role mapping")
        return Session(user_id, frozenset({user["role"]}), expires, "", True, session_id=session_id)


def _exact_object(value: Any, fields: set[str]) -> None:
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError("Authentication object does not match the v2 contract")


def _canonical_uuid(value: Any) -> str:
    from uuid import UUID

    if not isinstance(value, str):
        raise ValueError("invalid UUID")
    parsed = UUID(value)
    if parsed.int == 0 or str(parsed) != value:
        raise ValueError("invalid UUID")
    return value
class InMemoryAuthenticationAdapter:
    def __init__(self, sessions: Mapping[str,Session]|None=None): self.sessions,self.received_cookies=dict(sessions or {}),[]
    def verify(self,cookie: str)->Session:
        self.received_cookies.append(cookie)
        try: return self.sessions[cookie]
        except KeyError as exc: raise AccessDenied("session is invalid") from exc
class Security:
    """Authenticate and authorize through one deny-by-default interface."""
    def __init__(self,authentication:AuthenticationPort,now:Callable[[],datetime]|None=None,observer:Observability|None=None):
        self._authentication=authentication; self._now=now or (lambda:datetime.now(timezone.utc)); self._observer=observer
    def authentication_configured_for(self, session_url: str) -> bool:
        return isinstance(self._authentication, HttpAuthenticationAdapter) and self._authentication.configured_for(session_url)
    def authorize(self,cookie:str,capability:Capability,csrf_token:str|None=None,csrf_cookie:str|None=None)->Session:
        observer=self._observer or current_observability(); session=None
        action="security."+capability.value.replace(":",".")
        try:
            session=self._authentication.verify(cookie)
            expires=session.expires_at if session.expires_at.tzinfo else session.expires_at.replace(tzinfo=timezone.utc)
            if not session.enabled or expires<=self._now(): raise AccessDenied("session is expired or disabled")
            allowed=capability==Capability.SESSION
            if capability in {Capability.PLAN_READ,Capability.PLAN_MUTATE}: allowed="psychiatrist" in session.roles
            elif capability==Capability.SUPPORT_READ: allowed="admin" in session.roles and "treatment-plan:support" in session.permissions
            elif capability==Capability.AUDIT_READ: allowed="admin" in session.roles and "treatment-plan:audit" in session.permissions
            if not allowed: raise AccessDenied("principal is not authorized")
            expected_csrf = session.csrf_token or csrf_cookie or ""
            if capability==Capability.PLAN_MUTATE and (not expected_csrf or not csrf_token or not hmac.compare_digest(expected_csrf,csrf_token)):
                raise AccessDenied("CSRF token is missing or invalid")
        except (AccessDenied,AuthenticationUnavailable):
            observer.audit(action,"denied",actor_id=session.user_id if session else None)
            raise
        observer.audit(action,"success",actor_id=session.user_id)
        return session
