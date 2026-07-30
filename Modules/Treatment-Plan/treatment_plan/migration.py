"""Dialect-aware, reversible migrations for the repository adapters."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal


Dialect = Literal["sqlite", "postgres"]
_UP_NAME = re.compile(r"^\d{4}_[^.]+\.sql$")


@dataclass(frozen=True)
class Migration:
    version: str
    up: str
    down: str


class MigrationRunner:
    """Apply or reverse the same ordered migration set on SQLite/PostgreSQL."""

    def __init__(self, directory: Path, dialect: Dialect) -> None:
        self.directory = directory
        self.dialect = dialect

    def migrations(self) -> tuple[Migration, ...]:
        result: list[Migration] = []
        for path in sorted(self.directory.glob("*.sql")):
            if not _UP_NAME.fullmatch(path.name):
                continue
            down_path = path.with_name(f"{path.stem}.down.sql")
            if not down_path.exists():
                raise RuntimeError(f"migration {path.name} has no down migration")
            result.append(
                Migration(
                    path.name,
                    self._render(path.read_text(encoding="utf-8"), path.name, down=False),
                    self._render(down_path.read_text(encoding="utf-8"), path.name, down=True),
                )
            )
        return tuple(result)

    def migrate(self, connection: Any) -> tuple[str, ...]:
        self._execute(connection, "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY NOT NULL)")
        applied = {str(row[0]) for row in self._fetchall(connection, "SELECT version FROM schema_migrations")}
        changed: list[str] = []
        for migration in self.migrations():
            if migration.version in applied:
                continue
            self._script(connection, migration.up)
            self._execute(connection, f"INSERT INTO schema_migrations(version) VALUES ({self.placeholder})", (migration.version,))
            changed.append(migration.version)
        connection.commit()
        return tuple(changed)

    def rollback(self, connection: Any, steps: int | None = None) -> tuple[str, ...]:
        self._execute(connection, "CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY NOT NULL)")
        applied = {str(row[0]) for row in self._fetchall(connection, "SELECT version FROM schema_migrations")}
        candidates = [migration for migration in reversed(self.migrations()) if migration.version in applied]
        if steps is not None:
            if steps < 0:
                raise ValueError("steps cannot be negative")
            candidates = candidates[:steps]
        changed: list[str] = []
        for migration in candidates:
            self._script(connection, migration.down)
            self._execute(connection, f"DELETE FROM schema_migrations WHERE version = {self.placeholder}", (migration.version,))
            changed.append(migration.version)
        connection.commit()
        return tuple(changed)

    @property
    def placeholder(self) -> str:
        return "?" if self.dialect == "sqlite" else "%s"

    def _render(self, sql: str, version: str, *, down: bool) -> str:
        def uuid_check(match: re.Match[str]) -> str:
            column = match.group(1)
            if self.dialect == "postgres":
                return "TRUE"
            return (
                f"length({column}) = 36 AND substr({column}, 9, 1) = '-' "
                f"AND substr({column}, 14, 1) = '-' AND substr({column}, 19, 1) = '-' "
                f"AND substr({column}, 24, 1) = '-' "
                f"AND length(replace({column}, '-', '')) = 32 "
                f"AND {column} NOT GLOB '*[^0-9A-Fa-f-]*'"
            )

        def json_check(match: re.Match[str]) -> str:
            column = match.group(1)
            return "TRUE" if self.dialect == "postgres" else f"json_valid({column})"

        sql = re.sub(r"\{\{UUID_CHECK:([A-Za-z_][A-Za-z0-9_]*)\}\}", uuid_check, sql)
        sql = re.sub(r"\{\{JSON_CHECK:([A-Za-z_][A-Za-z0-9_]*)\}\}", json_check, sql)
        replacements = {
            "{{UUID}}": "TEXT" if self.dialect == "sqlite" else "UUID",
            "{{JSON}}": "TEXT" if self.dialect == "sqlite" else "JSONB",
            "{{TIMESTAMP}}": "TEXT" if self.dialect == "sqlite" else "TIMESTAMPTZ",
            "{{BOOLEAN}}": "INTEGER" if self.dialect == "sqlite" else "BOOLEAN",
            "{{FALSE}}": "0" if self.dialect == "sqlite" else "FALSE",
        }
        for token, value in replacements.items():
            sql = sql.replace(token, value)
        if down and version == "0004_immutable_finalized_plans.sql":
            return (
                "DROP TRIGGER IF EXISTS finalized_plans_immutable_update;\nDROP TRIGGER IF EXISTS finalized_plans_immutable_delete;"
                if self.dialect == "sqlite"
                else "DROP TRIGGER IF EXISTS finalized_plans_immutable ON finalized_plans;\nDROP FUNCTION IF EXISTS reject_finalized_plans_mutation();"
            )
        if down and version == "0005_plan_supersessions.sql":
            return (
                "DROP TABLE IF EXISTS plan_supersessions;"
                if self.dialect == "sqlite"
                else "DROP TABLE IF EXISTS plan_supersessions;\nDROP FUNCTION IF EXISTS reject_plan_supersessions_mutation();"
            )
        if self.dialect == "postgres" and not down:
            sql = self._postgres_legacy_sql(sql, version)
        return sql

    @staticmethod
    def _postgres_legacy_sql(sql: str, version: str) -> str:
        if version == "0004_immutable_finalized_plans.sql":
            return _postgres_immutable_trigger("finalized_plans", "finalized plans are immutable")
        if version == "0005_plan_supersessions.sql":
            create_table = sql.split("CREATE TRIGGER", 1)[0]
            return create_table + _postgres_immutable_trigger("plan_supersessions", "plan supersession records are immutable")
        return sql

    def _script(self, connection: Any, sql: str) -> None:
        if self.dialect == "sqlite":
            connection.executescript(sql)
        else:
            self._execute(connection, sql)

    @staticmethod
    def _execute(connection: Any, sql: str, params: tuple[Any, ...] = ()) -> Any:
        return connection.execute(sql, params) if params else connection.execute(sql)

    @staticmethod
    def _fetchall(connection: Any, sql: str) -> list[Any]:
        return list(connection.execute(sql).fetchall())


def _postgres_immutable_trigger(table: str, message: str) -> str:
    function = f"reject_{table}_mutation"
    trigger = f"{table}_immutable"
    return f"""
CREATE OR REPLACE FUNCTION {function}() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION '{message}';
END;
$$ LANGUAGE plpgsql;
DROP TRIGGER IF EXISTS {trigger} ON {table};
CREATE TRIGGER {trigger}
BEFORE UPDATE OR DELETE ON {table}
FOR EACH ROW EXECUTE FUNCTION {function}();
"""
