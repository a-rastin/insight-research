from __future__ import annotations
import hmac, json
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Callable, Mapping, Protocol
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
    """The only implementation allowed to propagate the incoming Cookie header."""
    def __init__(self, session_url: str, timeout_seconds: float=3.0): self._session_url, self._timeout=session_url, timeout_seconds
    def verify(self, cookie: str) -> Session:
        if not cookie: raise AccessDenied("session cookie is required")
        request=Request(self._session_url, headers={"Cookie":cookie,"Accept":"application/json"})
        try:
            with urlopen(request, timeout=self._timeout) as response: payload=json.load(response)
        except HTTPError as exc:
            if exc.code in {401,403}: raise AccessDenied("session is invalid") from exc
            raise AuthenticationUnavailable("Authentication rejected the request") from exc
        except (URLError,TimeoutError,ValueError) as exc: raise AuthenticationUnavailable("Authentication is unavailable") from exc
        try:
            expires=datetime.fromisoformat(payload["expiresAt"].replace("Z","+00:00"))
            return Session(payload["userId"],frozenset(payload.get("roles",[])),expires,payload.get("csrfToken",""),payload.get("enabled",False),frozenset(payload.get("permissions",[])),payload["sessionId"])
        except (KeyError,TypeError,ValueError) as exc: raise AuthenticationUnavailable("Authentication returned an invalid session") from exc
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
    def authorize(self,cookie:str,capability:Capability,csrf_token:str|None=None)->Session:
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
            if capability==Capability.PLAN_MUTATE and (not session.csrf_token or not csrf_token or not hmac.compare_digest(session.csrf_token,csrf_token)):
                raise AccessDenied("CSRF token is missing or invalid")
        except (AccessDenied,AuthenticationUnavailable):
            observer.audit(action,"denied",actor_id=session.user_id if session else None)
            raise
        observer.audit(action,"success",actor_id=session.user_id)
        return session
