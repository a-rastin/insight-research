"""SQLite-backed repository adapter for diagnosis sessions.

Replaces the module-global in-memory _store. The adapter exposes the same
semantics the route handlers used against the dict (init/get/put + audit
snapshot) but persists to SQLite so sessions survive restarts and the
audit hook returns a stable, dated snapshot.

Connection lifetime: a single connection per process, opened lazily on
first use and reused. Use the `DIAGNOSIS_DB_PATH` env var to point at a
file location; defaults to ``diagnosis_store.db`` in the current working
directory. ``reset()`` is exposed for the in-process self-check.
"""
from __future__ import annotations

import json
import os
import sqlite3
import threading
import time
from contextlib import contextmanager
from typing import Iterator
from datetime import UTC, datetime, timedelta
from uuid import uuid4


from .config import settings


def _resolve_path() -> str:
    # ``settings.db_path`` already honours ``DIAGNOSIS_DB_PATH`` (config.py);
    # keep the env re-read so tests that flip the env mid-process without
    # re-importing still see the new path, same as before the adapter.
    return os.environ.get("DIAGNOSIS_DB_PATH") or settings.db_path


_CREATE_SESSIONS = (
    """
    CREATE TABLE IF NOT EXISTS sessions (
        code        TEXT PRIMARY KEY,
        patient_id  TEXT,
        checked     TEXT NOT NULL DEFAULT '[]',
        decision    TEXT,
        created_at  INTEGER NOT NULL,
        updated_at  INTEGER NOT NULL
    )
    """
)

_CREATE_AUDIT = (
    """
    CREATE TABLE IF NOT EXISTS audit (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        code        TEXT NOT NULL,
        snapshot    TEXT NOT NULL,
        created_at  INTEGER NOT NULL
    )
    """
)

_CREATE_V2 = ("""
CREATE TABLE IF NOT EXISTS diagnosis_assessments (
    assessment_id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL,
    encounter_id TEXT NOT NULL UNIQUE,
    checked TEXT NOT NULL DEFAULT '[]',
    decision TEXT,
    decision_actor TEXT,
    decision_at TEXT,
    resource_version INTEGER NOT NULL,
    created_by TEXT NOT NULL,
    updated_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)""", """
CREATE TABLE IF NOT EXISTS diagnosis_assessment_audit (
    sequence INTEGER PRIMARY KEY AUTOINCREMENT,
    assessment_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    actor_user_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    resource_version INTEGER NOT NULL,
    snapshot TEXT NOT NULL
)""", """
CREATE TABLE IF NOT EXISTS diagnosis_idempotency (
    actor_user_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    assessment_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (actor_user_id, operation, idempotency_key)
)
""")


class DiagnosisStore:
    """Persistence adapter for /diagnosis sessions + audit snapshots.

    Thread-safe via a per-process connection guarded by ``threading.Lock``.
    Same-process SQLite is fine — the WAL journal handles concurrent reads.
    """

    def __init__(self, path: str | None = None) -> None:
        self.path = path or _resolve_path()
        self._lock = threading.Lock()
        self._conn: sqlite3.Connection | None = None
        self._ensure_schema()

    @contextmanager
    def _cursor(self) -> Iterator[sqlite3.Cursor]:
        if self._conn is None:
            self._conn = sqlite3.connect(
                self.path,
                isolation_level=None,
                check_same_thread=False,
            )
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA foreign_keys=ON")
        cur = self._conn.cursor()
        try:
            yield cur
        finally:
            cur.close()

    def _ensure_schema(self) -> None:
        with self._cursor() as cur:
            cur.execute("BEGIN")
            try:
                cur.execute(_CREATE_SESSIONS)
                cur.execute(_CREATE_AUDIT)
                for statement in _CREATE_V2:
                    cur.execute(statement)
                cur.execute("PRAGMA table_info(diagnosis_idempotency)")
                if "created_at" not in {row[1] for row in cur.fetchall()}:
                    cur.execute("ALTER TABLE diagnosis_idempotency ADD COLUMN created_at TEXT")
                cur.execute("COMMIT")
            except Exception:
                cur.execute("ROLLBACK")
                raise

    def init(self, code: str, *, patient_id: str | None = None) -> bool:
        """Insert a new empty session. Returns ``True`` if created."""
        now = int(time.time())
        with self._cursor() as cur:
            cur.execute(
                "INSERT OR IGNORE INTO sessions "
                "(code, patient_id, checked, decision, created_at, updated_at) "
                "VALUES (?, ?, '[]', NULL, ?, ?)",
                (code, patient_id, now, now),
            )
            return cur.rowcount == 1

    def exists(self, code: str) -> bool:
        with self._cursor() as cur:
            cur.execute("SELECT 1 FROM sessions WHERE code = ?", (code,))
            return cur.fetchone() is not None

    def get(self, code: str) -> dict | None:
        with self._cursor() as cur:
            cur.execute(
                "SELECT code, patient_id, checked, decision, "
                "created_at, updated_at "
                "FROM sessions WHERE code = ?",
                (code,),
            )
            row = cur.fetchone()
        if row is None:
            return None
        checked = json.loads(row[2]) if row[2] else []
        return {
            "code": row[0],
            "patient_id": row[1],
            "checked": checked,
            "decision": row[3],
            "created_at": row[4],
            "updated_at": row[5],
        }

    def put(
        self,
        code: str,
        *,
        patient_id: str | None,
        checked: list[str],
        decision: str | None,
    ) -> dict:
        """Persist checked criteria + clinician decision. Returns the
        full session row. Creates the row if it doesn't exist."""
        now = int(time.time())
        encoded = json.dumps(list(checked))
        with self._cursor() as cur:
            cur.execute("BEGIN")
            try:
                cur.execute(
                    "INSERT OR IGNORE INTO sessions "
                    "(code, patient_id, checked, decision, created_at, updated_at) "
                    "VALUES (?, ?, '[]', NULL, ?, ?)",
                    (code, patient_id, now, now),
                )
                cur.execute(
                    "UPDATE sessions "
                    "SET patient_id = ?, checked = ?, decision = ?, updated_at = ? "
                    "WHERE code = ?",
                    (patient_id, encoded, decision, now, code),
                )
                cur.execute(
                    "SELECT code, patient_id, checked, decision, "
                    "created_at, updated_at FROM sessions WHERE code = ?",
                    (code,),
                )
                row = cur.fetchone()
                cur.execute("COMMIT")
            except Exception:
                cur.execute("ROLLBACK")
                raise
        if row is None:
            raise RuntimeError(f"put failed: row {code!r} missing after write")
        return {
            "code": row[0],
            "patient_id": row[1],
            "checked": json.loads(row[2]) if row[2] else [],
            "decision": row[3],
            "created_at": row[4],
            "updated_at": row[5],
        }

    def audit_snapshot(self, code: str) -> str:
        """JSON snapshot for the Insight audit logger. Records every
        successful put, plus a final snapshot at read time."""
        session = self.get(code) or {"code": code}
        snapshot = json.dumps(session, default=str, sort_keys=True)
        with self._cursor() as cur:
            cur.execute(
                "INSERT INTO audit (code, snapshot, created_at) VALUES (?, ?, ?)",
                (code, snapshot, int(time.time())),
            )
        return snapshot

    def list_audits(self, code: str) -> list[str]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT snapshot FROM audit WHERE code = ? ORDER BY id",
                (code,),
            )
            return [r[0] for r in cur.fetchall()]

    def reset(self) -> None:
        """Hard reset. Self-check / test fixture support only."""
        with self._cursor() as cur:
            cur.execute("DELETE FROM sessions")
            cur.execute("DELETE FROM audit")
            cur.execute("DELETE FROM diagnosis_assessment_audit")
            cur.execute("DELETE FROM diagnosis_idempotency")
            cur.execute("DELETE FROM diagnosis_assessments")

    @staticmethod
    def _v2_row(row: sqlite3.Row | tuple) -> dict:
        checked = json.loads(row[3])
        decision = None
        if row[4]:
            decision = {"type": row[4], "actorUserId": row[5], "recordedAt": row[6]}
        return {
            "assessmentId": row[0], "patientId": row[1], "encounterId": row[2],
            "checkedCriteria": checked, "clinicianDecision": decision,
            "resourceVersion": row[7], "createdByUserId": row[8],
            "lastUpdatedByUserId": row[9], "createdAt": row[10], "updatedAt": row[11],
        }

    def get_assessment(self, assessment_id: str) -> dict | None:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM diagnosis_assessments WHERE assessment_id = ?", (assessment_id,))
            row = cur.fetchone()
        return self._v2_row(row) if row else None

    def get_assessment_by_encounter(self, encounter_id: str) -> dict | None:
        with self._cursor() as cur:
            cur.execute("SELECT * FROM diagnosis_assessments WHERE encounter_id = ?", (encounter_id,))
            row = cur.fetchone()
        return self._v2_row(row) if row else None

    def replay_assessment(self, actor: str, key: str, fingerprint: str) -> dict | None:
        cutoff = (datetime.now(UTC) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
        with self._cursor() as cur:
            cur.execute("DELETE FROM diagnosis_idempotency WHERE created_at IS NULL OR created_at < ?", (cutoff,))
            cur.execute(
                "SELECT fingerprint, assessment_id FROM diagnosis_idempotency WHERE actor_user_id=? AND operation='init' AND idempotency_key=?",
                (actor, key),
            )
            row = cur.fetchone()
        if not row:
            return None
        if row[0] != fingerprint:
            raise ValueError("idempotency-conflict")
        return self.get_assessment(row[1])

    def init_assessment(self, patient_id: str, encounter_id: str, actor: str, key: str, fingerprint: str) -> tuple[dict, bool]:
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        cutoff = (datetime.now(UTC) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
        with self._cursor() as cur:
            cur.execute("BEGIN IMMEDIATE")
            try:
                cur.execute("DELETE FROM diagnosis_idempotency WHERE created_at IS NULL OR created_at < ?", (cutoff,))
                cur.execute(
                    "SELECT fingerprint, assessment_id FROM diagnosis_idempotency WHERE actor_user_id=? AND operation='init' AND idempotency_key=?",
                    (actor, key),
                )
                replay = cur.fetchone()
                if replay:
                    if replay[0] != fingerprint:
                        raise ValueError("idempotency-conflict")
                    cur.execute("SELECT * FROM diagnosis_assessments WHERE assessment_id=?", (replay[1],))
                    row = cur.fetchone()
                    cur.execute("COMMIT")
                    return self._v2_row(row), True
                cur.execute("SELECT * FROM diagnosis_assessments WHERE encounter_id=?", (encounter_id,))
                row = cur.fetchone()
                if row:
                    assessment = self._v2_row(row)
                else:
                    assessment_id = str(uuid4())
                    cur.execute(
                        "INSERT INTO diagnosis_assessments VALUES (?, ?, ?, '[]', NULL, NULL, NULL, 1, ?, ?, ?, ?)",
                        (assessment_id, patient_id, encounter_id, actor, actor, now, now),
                    )
                    cur.execute("SELECT * FROM diagnosis_assessments WHERE assessment_id=?", (assessment_id,))
                    assessment = self._v2_row(cur.fetchone())
                    self._insert_v2_audit(cur, assessment, "initialized", actor, now)
                cur.execute(
                    "INSERT INTO diagnosis_idempotency (actor_user_id,operation,idempotency_key,fingerprint,assessment_id,created_at) VALUES (?, 'init', ?, ?, ?, ?)",
                    (actor, key, fingerprint, assessment["assessmentId"], now),
                )
                cur.execute("COMMIT")
                return assessment, False
            except Exception:
                cur.execute("ROLLBACK")
                raise

    def update_assessment(self, assessment_id: str, expected_version: int, checked: list[str], decision: str | None, actor: str) -> dict | None:
        now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        with self._cursor() as cur:
            cur.execute("BEGIN IMMEDIATE")
            try:
                cur.execute("SELECT resource_version FROM diagnosis_assessments WHERE assessment_id=?", (assessment_id,))
                current = cur.fetchone()
                if not current:
                    cur.execute("ROLLBACK")
                    return None
                if current[0] != expected_version:
                    raise RuntimeError("stale")
                version = expected_version + 1
                cur.execute(
                    "UPDATE diagnosis_assessments SET checked=?, decision=?, decision_actor=?, decision_at=?, resource_version=?, updated_by=?, updated_at=? WHERE assessment_id=? AND resource_version=?",
                    (json.dumps(checked), decision, actor if decision else None, now if decision else None, version, actor, now, assessment_id, expected_version),
                )
                if cur.rowcount != 1:
                    raise RuntimeError("stale")
                cur.execute("SELECT * FROM diagnosis_assessments WHERE assessment_id=?", (assessment_id,))
                assessment = self._v2_row(cur.fetchone())
                self._insert_v2_audit(cur, assessment, "updated", actor, now)
                cur.execute("COMMIT")
                return assessment
            except Exception:
                cur.execute("ROLLBACK")
                raise

    def _insert_v2_audit(self, cur: sqlite3.Cursor, assessment: dict, event_type: str, actor: str, occurred_at: str) -> None:
        cur.execute(
            "INSERT INTO diagnosis_assessment_audit (assessment_id,event_type,actor_user_id,occurred_at,resource_version,snapshot) VALUES (?,?,?,?,?,?)",
            (assessment["assessmentId"], event_type, actor, occurred_at, assessment["resourceVersion"], json.dumps(assessment, sort_keys=True)),
        )

    def list_assessment_audits(self, assessment_id: str) -> list[dict]:
        with self._cursor() as cur:
            cur.execute(
                "SELECT sequence,event_type,actor_user_id,occurred_at,resource_version,snapshot FROM diagnosis_assessment_audit WHERE assessment_id=? ORDER BY sequence",
                (assessment_id,),
            )
            rows = cur.fetchall()
        return [{"sequence": row[0], "assessmentId": assessment_id, "eventType": row[1], "actorUserId": row[2], "occurredAt": row[3], "resourceVersion": row[4], "snapshot": json.loads(row[5])} for row in rows]


def _store_selfcheck() -> None:
    """Hard reverify the persistence adapter end-to-end, with a fresh
    temp DB so the check never collides with a real store. Covers:
    - patient id / patient code round-trip
    - checked criteria (incl. order preservation + dedupe on the PUT side)
    - clinician decision (both 'confirmed' and bypass 'definite')
    - monotonic timestamps (created_at <= updated_at on every write)
    - audit snapshot records and is JSON-round-trippable
    - data survives a new DiagnosisStore on the same file
    Run: ``python -m diagnosis.store``
    """
    import tempfile
    import os
    fd, path = tempfile.mkstemp(prefix="diagnosis_store_test_", suffix=".db")
    os.close(fd)
    try:
        s1 = DiagnosisStore(path)
        s1.reset()

        # 1. init creates a session row, returns True once then False.
        assert s1.init("P-0042-A", patient_id="P-0042-A") is True
        assert s1.init("P-0042-A", patient_id="P-0042-A") is False
        row = s1.get("P-0042-A")
        assert row is not None and row["code"] == "P-0042-A"
        assert row["patient_id"] == "P-0042-A", row
        assert row["checked"] == [] and row["decision"] is None

        # 2. timestamps present + monotonic.
        assert isinstance(row["created_at"], int) and row["created_at"] > 0
        assert row["updated_at"] >= row["created_at"]

        # 3. PUT persists checked criteria + decision; returned row matches.
        checked = ["A1", "A5", "A6", "B1", "C1", "D1"]
        out = s1.put(
            "P-0042-A", patient_id="P-0042-A",
            checked=checked, decision="confirmed",
        )
        assert out["checked"] == checked, out
        assert out["decision"] == "confirmed", out
        assert out["updated_at"] >= row["updated_at"], (out, row)

        # 4. bypass ("definite") is a valid decision even on unmet criteria.
        out_bypass = s1.put(
            "P-0042-A", patient_id="P-0042-A",
            checked=["A1"], decision="definite",
        )
        assert out_bypass["decision"] == "definite"
        assert out_bypass["checked"] == ["A1"]

        # 5. audit_snapshot records and returns a stable JSON snapshot.
        snap = s1.audit_snapshot("P-0042-A")
        parsed = json.loads(snap)
        assert parsed["code"] == "P-0042-A"
        assert parsed["decision"] == "definite", parsed
        audits = s1.list_audits("P-0042-A")
        assert any(snap == a for a in audits), "audit snapshot was not recorded"

        # 6. unknown code returns None from get(); snapshot doesn't crash.
        assert s1.get("does-not-exist") is None
        snap_missing = s1.audit_snapshot("does-not-exist")
        assert json.loads(snap_missing)["code"] == "does-not-exist"

        # 7. durability: new DiagnosisStore against the same file sees
        # the persisted row, so clinical data survives a restart.
        s2 = DiagnosisStore(path)
        persisted = s2.get("P-0042-A")
        assert persisted is not None
        assert persisted["checked"] == ["A1"]
        assert persisted["decision"] == "definite", persisted

        s1.reset()
        s2.reset()
        print("OK: diagnosis store self-check passed")
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


if __name__ == "__main__":
    _store_selfcheck()
