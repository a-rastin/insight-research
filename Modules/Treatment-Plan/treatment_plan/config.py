import os
from dataclasses import dataclass
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlsplit


class ConfigurationError(ValueError):
    pass


def _bool(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigurationError(f"{name} must be a boolean")


@dataclass(frozen=True)
class Settings:
    environment: str = "development"
    database_path: Path = Path("var/treatment-plan.db")
    auth_stub_enabled: bool = False
    log_level: str = "INFO"
    authentication_session_url: str | None = None
    trusted_internal_origins: tuple[str, ...] = ()
    assistant_provider_url: str | None = None
    assistant_timeout_seconds: float = 10.0

    @classmethod
    def from_env(cls) -> "Settings":
        environment = os.getenv("TP_ENV", "development").strip().lower()
        if environment not in {"development", "test", "production"}:
            raise ConfigurationError("TP_ENV must be development, test, or production")
        stub = _bool(os.getenv("TP_AUTH_STUB_ENABLED", "false"), "TP_AUTH_STUB_ENABLED")
        if stub and environment != "development":
            raise ConfigurationError("standalone auth stub is allowed only in development")
        level = os.getenv("TP_LOG_LEVEL", "INFO").upper()
        if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
            raise ConfigurationError("TP_LOG_LEVEL is invalid")
        origins = tuple(value.strip().rstrip("/") for value in os.getenv("TP_TRUSTED_INTERNAL_ORIGINS", "").split(",") if value.strip())
        for origin in origins:
            parsed = urlsplit(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
                raise ConfigurationError("TP_TRUSTED_INTERNAL_ORIGINS must contain origins only")
            loopback_http = parsed.scheme == "http" and _loopback(parsed.hostname)
            if environment == "production" and parsed.scheme != "https" and not loopback_http:
                raise ConfigurationError("trusted internal origins must use HTTPS in production")
        session_url = os.getenv("TP_AUTHENTICATION_SESSION_URL") or None
        if session_url:
            parsed = urlsplit(session_url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or f"{parsed.scheme}://{parsed.netloc}" not in origins:
                raise ConfigurationError("TP_AUTHENTICATION_SESSION_URL must use a trusted internal origin")
        if environment == "production" and not session_url:
            raise ConfigurationError("production requires the Authentication REST interface")
        assistant_url = os.getenv("TP_ASSISTANT_PROVIDER_URL") or None
        if assistant_url:
            parsed = urlsplit(assistant_url)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or f"{parsed.scheme}://{parsed.netloc}" not in origins:
                raise ConfigurationError("TP_ASSISTANT_PROVIDER_URL must use a trusted internal origin")
            if environment == "production" and parsed.scheme != "https":
                raise ConfigurationError("assistant provider must use HTTPS in production")
        try:
            assistant_timeout = float(os.getenv("TP_ASSISTANT_TIMEOUT_SECONDS", "10"))
        except ValueError as exc:
            raise ConfigurationError("TP_ASSISTANT_TIMEOUT_SECONDS must be numeric") from exc
        if not 0 < assistant_timeout <= 30:
            raise ConfigurationError("TP_ASSISTANT_TIMEOUT_SECONDS must be greater than 0 and at most 30")
        return cls(
            environment=environment,
            database_path=Path(os.getenv("TP_DATABASE_PATH", "var/treatment-plan.db")),
            auth_stub_enabled=stub,
            log_level=level,
            authentication_session_url=session_url,
            trusted_internal_origins=origins,
            assistant_provider_url=assistant_url,
            assistant_timeout_seconds=assistant_timeout,
        )


def _loopback(hostname: str | None) -> bool:
    try:
        return bool(hostname) and ip_address(hostname).is_loopback
    except ValueError:
        return False


