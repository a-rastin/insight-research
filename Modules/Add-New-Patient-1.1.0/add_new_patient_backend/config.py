from __future__ import annotations

import os
from pathlib import Path
import secrets

ROOT = Path(__file__).resolve().parent.parent


class Settings:
    def __init__(self) -> None:
        self.port = int(os.environ.get("PORT", "4173"))
        self.db_path = os.environ.get("ADD_NEW_PATIENT_DB_PATH", str(ROOT / "add_new_patient.sqlite3"))
        self.auth_session_url = os.environ.get("AUTH_SESSION_URL", "")
        self.auth_base_url = os.environ.get("AUTH_BASE_URL", "")
        self.auth_session_timeout_seconds = float(os.environ.get("AUTH_SESSION_TIMEOUT_MS", "2000")) / 1000
        self.csrf_secret = os.environ.get("ADD_NEW_PATIENT_CSRF_SECRET", secrets.token_urlsafe(32))
        self.csrf_secure = os.environ.get("ADD_NEW_PATIENT_CSRF_SECURE", "false").lower() == "true"
        # ponytail: mock auth mirrors Dashboard — on by default when no auth URL set, off if =0.
        self.use_mock_auth = os.environ.get("ADD_NEW_PATIENT_MOCK_AUTH") == "1" or (
            not self.auth_session_url
            and not self.auth_base_url
            and os.environ.get("ADD_NEW_PATIENT_MOCK_AUTH") != "0"
        )


settings = Settings()
