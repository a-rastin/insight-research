import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from .migration import MigrationRunner
from .repository import RuntimeRecord
from .retention import RetentionPolicy, RetentionResult, apply_retention


class SQLiteRepository:
    def __init__(self, path: Path, migrations: Path | None = None) -> None:
        self.path = path
        self.migrations = migrations or Path(__file__).with_name("migrations")

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def migrate(self) -> tuple[str, ...]:
        with closing(self._connect()) as connection:
            return MigrationRunner(self.migrations, "sqlite").migrate(connection)

    def rollback(self, steps: int | None = None) -> tuple[str, ...]:
        with closing(self._connect()) as connection:
            return MigrationRunner(self.migrations, "sqlite").rollback(connection, steps)

    def backup(self, destination: Path) -> None:
        if destination.resolve() == self.path.resolve():
            raise ValueError("backup destination must differ from the live database")
        destination.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as source, closing(sqlite3.connect(destination)) as target:
            source.backup(target)
            target.commit()

    def restore(self, source: Path) -> None:
        if not source.is_file():
            raise FileNotFoundError(source)
        if source.resolve() == self.path.resolve():
            raise ValueError("restore source must differ from the live database")
        with closing(sqlite3.connect(source)) as backup:
            result = backup.execute("PRAGMA integrity_check").fetchone()
            if result is None or result[0] != "ok":
                raise ValueError("backup database failed its integrity check")
            with closing(self._connect()) as target:
                backup.backup(target)
                target.commit()

    def apply_retention(
        self, policy: RetentionPolicy, now: datetime
    ) -> RetentionResult:
        with closing(self._connect()) as connection:
            return apply_retention(connection, "sqlite", policy, now)

    def ping(self) -> bool:
        try:
            with closing(self._connect()) as connection:
                connection.execute("SELECT 1")
            return True
        except sqlite3.Error:
            return False

    def put(self, record: RuntimeRecord) -> None:
        with closing(self._connect()) as connection:
            connection.execute("INSERT INTO runtime_records(key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (record.key, record.value))
            connection.commit()

    def get(self, key: str) -> RuntimeRecord | None:
        with closing(self._connect()) as connection:
            row = connection.execute("SELECT key,value FROM runtime_records WHERE key=?", (key,)).fetchone()
        return RuntimeRecord(*row) if row else None




