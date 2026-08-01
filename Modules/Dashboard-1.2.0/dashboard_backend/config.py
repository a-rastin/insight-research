from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class Settings:
    def __init__(self) -> None:
        self.port = int(os.environ.get("PORT", "4173"))
        self.db_path = os.environ.get("DASHBOARD_DB_PATH", str(ROOT / "dashboard.sqlite3"))
        self.auth_session_url = os.environ.get("AUTH_SESSION_URL", "")
        self.auth_base_url = os.environ.get("AUTH_BASE_URL", "")
        self.auth_session_timeout_seconds = float(os.environ.get("AUTH_SESSION_TIMEOUT_MS", "2000")) / 1000
        self.provider_timeout_seconds = float(os.environ.get("DASHBOARD_PROVIDER_TIMEOUT_MS", "2000")) / 1000
        self.ddi_readiness_url = os.environ.get("DDI_READINESS_URL", "")
        self.bn_readiness_url = os.environ.get("BN_MANAGER_READINESS_URL", "")
        self.bn_status_url = os.environ.get("BN_MANAGER_STATUS_URL", "")
        self.use_mock_auth = os.environ.get("DASHBOARD_MOCK_AUTH") == "1" or (
            not self.auth_session_url
            and not self.auth_base_url
            and os.environ.get("DASHBOARD_MOCK_AUTH") != "0"
        )


settings = Settings()
