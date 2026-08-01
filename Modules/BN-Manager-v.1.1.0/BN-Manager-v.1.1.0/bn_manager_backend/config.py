from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
DEFAULT_AUTH_SESSION_URL = "http://127.0.0.1:8000/api/auth/v2/session"


@dataclass(frozen=True, slots=True)
class BnManagerSettings:
    module_id: str = "bn-manager"
    app_name: str = "BN Manager"
    api_prefix: str = "/api"
    ui_mount_path: str = "/modules/bn-manager"
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    static_dir: Path = Path(__file__).resolve().parent / "static"
    auth_session_url: str = DEFAULT_AUTH_SESSION_URL
    auth_timeout_seconds: float = 2.0
    csrf_header_name: str = "x-csrf-token"
    governance_db_path: Path = Path(os.environ.get(
        "BN_MANAGER_GOVERNANCE_DB",
        Path(os.environ.get("BN_REGISTRY_ROOT", Path(__file__).resolve().parent / "model_registry")) / "governance.sqlite3",
    ))

    @classmethod
    def from_env(cls) -> "BnManagerSettings":
        return cls(
            host=os.getenv("BN_MANAGER_HOST", DEFAULT_HOST),
            port=int(os.getenv("BN_MANAGER_PORT", str(DEFAULT_PORT))),
            auth_session_url=os.getenv("BN_MANAGER_AUTH_SESSION_URL", DEFAULT_AUTH_SESSION_URL),
            auth_timeout_seconds=float(os.getenv("BN_MANAGER_AUTH_TIMEOUT_SECONDS", "2.0")),
            csrf_header_name=os.getenv("BN_MANAGER_CSRF_HEADER_NAME", "x-csrf-token"),
            governance_db_path=Path(os.getenv(
                "BN_MANAGER_GOVERNANCE_DB",
                Path(os.getenv("BN_REGISTRY_ROOT", Path(__file__).resolve().parent / "model_registry")) / "governance.sqlite3",
            )),
        )


@lru_cache(maxsize=1)
def get_settings() -> BnManagerSettings:
    return BnManagerSettings.from_env()
