"""Container startup and migration readiness gate (TP-22)."""

from __future__ import annotations

import argparse
import os
import sqlite3
from contextlib import closing
from pathlib import Path

import uvicorn

from .config import ConfigurationError, Settings
from .migration import MigrationRunner
from .sqlite_repository import SQLiteRepository


def settings_from_environment() -> Settings:
    """Resolve supported Docker secret files before crossing the Settings seam."""
    direct = os.getenv("TP_AUTHENTICATION_SESSION_URL")
    mounted = os.getenv("TP_AUTHENTICATION_SESSION_URL_FILE")
    if direct and mounted:
        raise ConfigurationError("set only TP_AUTHENTICATION_SESSION_URL or its _FILE variant")
    if mounted:
        path = Path(mounted)
        if path.stat().st_size > 16_384:
            raise ConfigurationError("authentication configuration secret is unexpectedly large")
        value = path.read_text(encoding="utf-8").strip()
        if not value:
            raise ConfigurationError("authentication configuration secret is empty")
        os.environ["TP_AUTHENTICATION_SESSION_URL"] = value
    return Settings.from_env()


def migration_gate(settings: Settings) -> tuple[str, ...]:
    repository = SQLiteRepository(settings.database_path)
    changed = repository.migrate()
    expected = tuple(migration.version for migration in MigrationRunner(repository.migrations, "sqlite").migrations())
    with closing(sqlite3.connect(settings.database_path)) as connection:
        actual = tuple(row[0] for row in connection.execute("SELECT version FROM schema_migrations ORDER BY version"))
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
    if actual != expected:
        raise RuntimeError("migration gate found a partial or unexpected schema version set")
    if integrity is None or integrity[0] != "ok":
        raise RuntimeError("migration gate database integrity check failed")
    if not repository.ping():
        raise RuntimeError("migration gate repository readiness check failed")
    return changed


def serve(settings: Settings) -> None:
    migration_gate(settings)
    graceful = int(os.getenv("TP_GRACEFUL_SHUTDOWN_SECONDS", "30"))
    if not 1 <= graceful <= 300:
        raise ConfigurationError("TP_GRACEFUL_SHUTDOWN_SECONDS must be between 1 and 300")
    host = os.getenv("TP_HOST", "127.0.0.1")
    port = int(os.getenv("TP_PORT", "8000"))
    uvicorn.run(
        "treatment_plan.app:app", host=host, port=port, reload=False,
        timeout_graceful_shutdown=graceful, proxy_headers=True, forwarded_allow_ips="127.0.0.1",
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("migration-gate", "serve"), nargs="?", default="serve")
    args = parser.parse_args()
    settings = settings_from_environment()
    if args.command == "migration-gate":
        changed = migration_gate(settings)
        print("migration gate passed" + (": " + ", ".join(changed) if changed else ": current"))
        return 0
    serve(settings)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
