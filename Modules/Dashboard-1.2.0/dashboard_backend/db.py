from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator, Protocol

SCHEMA = """
PRAGMA foreign_keys = ON;

DROP TABLE IF EXISTS dashboard_profiles;
DROP TABLE IF EXISTS logins;
DROP TABLE IF EXISTS mock_auth_sessions;

CREATE TABLE IF NOT EXISTS dashboard_sessions (
  id TEXT PRIMARY KEY,
  user_id TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('ADMIN', 'PSYCHIATRIST')),
  auth_session_id TEXT NOT NULL,
  active INTEGER NOT NULL DEFAULT 1,
  created_at TEXT NOT NULL,
  disclaimer_accepted_at TEXT
);

CREATE TABLE IF NOT EXISTS workspace_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  dashboard_session_id TEXT NOT NULL,
  user_id TEXT NOT NULL,
  role TEXT NOT NULL CHECK (role IN ('ADMIN', 'PSYCHIATRIST')),
  event_type TEXT NOT NULL,
  at TEXT NOT NULL,
  FOREIGN KEY (dashboard_session_id) REFERENCES dashboard_sessions(id)
);
"""


class DatabaseAdapter(Protocol):
    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        ...

    def initialize(self) -> None:
        ...

    def ping(self) -> bool:
        ...


class SQLiteAdapter:
    """SQLite adapter. Repository owns SQL, so Postgres can replace adapter later."""

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(SCHEMA)
            columns = {row["name"] for row in conn.execute("PRAGMA table_info(dashboard_sessions)").fetchall()}
            if "disclaimer_accepted_at" not in columns:
                conn.execute("ALTER TABLE dashboard_sessions ADD COLUMN disclaimer_accepted_at TEXT")

    def ping(self) -> bool:
        with self.connect() as conn:
            conn.execute("SELECT 1").fetchone()
        return True
