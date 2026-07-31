from __future__ import annotations

from contextlib import closing
from datetime import UTC, datetime
import json
from pathlib import Path
import sqlite3
from typing import Any


class GovernanceConflict(ValueError):
    pass


class GovernanceStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self._connect()) as connection, connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS model_lifecycle (
                    stable_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    updated_by TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS model_lifecycle_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    stable_id TEXT NOT NULL,
                    action TEXT NOT NULL,
                    from_status TEXT NOT NULL,
                    to_status TEXT NOT NULL,
                    actor_id TEXT NOT NULL,
                    rationale TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    validation_evidence TEXT NOT NULL
                );
                """
            )

    def get(self, stable_id: str) -> dict[str, Any]:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "SELECT status, version, updated_at, updated_by FROM model_lifecycle WHERE stable_id = ?",
                (stable_id,),
            ).fetchone()
            events = connection.execute(
                """SELECT action, from_status, to_status, actor_id, rationale, created_at,
                          validation_evidence
                   FROM model_lifecycle_events WHERE stable_id = ? ORDER BY event_id""",
                (stable_id,),
            ).fetchall()
        state = {
            "status": row[0] if row else "draft",
            "version": row[1] if row else 0,
            "updated_at": row[2] if row else None,
            "updated_by": row[3] if row else None,
            "history": [
                {
                    "action": event[0],
                    "from_status": event[1],
                    "to_status": event[2],
                    "actor_id": event[3],
                    "rationale": event[4],
                    "created_at": event[5],
                    "validation_evidence": json.loads(event[6]),
                }
                for event in events
            ],
        }
        return state

    def transition(
        self,
        stable_id: str,
        action: str,
        actor_id: str,
        rationale: str,
        validation_evidence: dict[str, Any],
    ) -> dict[str, Any]:
        transitions = {
            "review": ({"draft"}, "reviewed"),
            "activate": ({"reviewed", "retired"}, "active"),
            "retire": ({"reviewed", "active"}, "retired"),
        }
        if action not in transitions:
            raise GovernanceConflict("Unsupported lifecycle action.")
        allowed, target = transitions[action]
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT status, version FROM model_lifecycle WHERE stable_id = ?",
                (stable_id,),
            ).fetchone()
            current = row[0] if row else "draft"
            version = row[1] if row else 0
            if current not in allowed:
                raise GovernanceConflict(f"Cannot {action} a model in {current} status.")
            self._write_transition(
                connection, stable_id, action, current, target, actor_id, rationale,
                validation_evidence, now, version + 1,
            )
        return self.get(stable_id)

    def rollback(
        self,
        stable_id: str,
        actor_id: str,
        rationale: str,
        validation_evidence: dict[str, Any],
    ) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        with closing(self._connect()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT status, version FROM model_lifecycle WHERE stable_id = ?",
                (stable_id,),
            ).fetchone()
            if row is None:
                raise GovernanceConflict("No lifecycle transition is available to roll back.")
            previous = connection.execute(
                "SELECT from_status FROM model_lifecycle_events WHERE stable_id = ? ORDER BY event_id DESC LIMIT 1",
                (stable_id,),
            ).fetchone()
            if previous is None or previous[0] == row[0]:
                raise GovernanceConflict("No prior lifecycle status is available to roll back.")
            self._write_transition(
                connection, stable_id, "rollback", row[0], previous[0], actor_id,
                rationale, validation_evidence, now, row[1] + 1,
            )
        return self.get(stable_id)

    def _write_transition(
        self,
        connection: sqlite3.Connection,
        stable_id: str,
        action: str,
        current: str,
        target: str,
        actor_id: str,
        rationale: str,
        validation_evidence: dict[str, Any],
        now: str,
        version: int,
    ) -> None:
        connection.execute(
            """INSERT INTO model_lifecycle(stable_id, status, version, updated_at, updated_by)
               VALUES (?, ?, ?, ?, ?)
               ON CONFLICT(stable_id) DO UPDATE SET status=excluded.status,
                   version=excluded.version, updated_at=excluded.updated_at, updated_by=excluded.updated_by""",
            (stable_id, target, version, now, actor_id),
        )
        connection.execute(
            """INSERT INTO model_lifecycle_events(
                   stable_id, action, from_status, to_status, actor_id, rationale,
                   created_at, validation_evidence
               ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                stable_id, action, current, target, actor_id, rationale, now,
                json.dumps(validation_evidence, sort_keys=True, separators=(",", ":")),
            ),
        )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.path)
        connection.execute("PRAGMA foreign_keys = ON")
        return connection
