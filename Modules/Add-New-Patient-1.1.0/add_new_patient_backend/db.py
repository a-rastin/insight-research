from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterator, Protocol
from uuid import NAMESPACE_URL, UUID, uuid4, uuid5

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS patients (
  id TEXT PRIMARY KEY,
  patient_code TEXT NOT NULL UNIQUE,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  sex TEXT NOT NULL CHECK (sex IN ('Male', 'Female')),
  dob TEXT NOT NULL,
  phone_number TEXT,
  created_by_user_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  schema_version TEXT NOT NULL DEFAULT '2.0.0',
  resource_version INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS patient_code_aliases (
  alias_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL UNIQUE REFERENCES patients(id) ON DELETE CASCADE,
  patient_code TEXT NOT NULL COLLATE NOCASE UNIQUE,
  schema_version TEXT NOT NULL DEFAULT '2.0.0',
  resource_version INTEGER NOT NULL DEFAULT 1,
  created_by_user_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS encounters (
  encounter_id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  encounter_type TEXT NOT NULL CHECK (encounter_type IN ('initial', 'follow-up')),
  occurred_at TEXT NOT NULL,
  legacy_intake_id TEXT UNIQUE,
  schema_version TEXT NOT NULL DEFAULT '2.0.0',
  resource_version INTEGER NOT NULL DEFAULT 1,
  created_by_user_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS patient_intake_records (
  id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  encounter_date TEXT NOT NULL,
  presenting_complaint TEXT NOT NULL DEFAULT '',
  provisional_diagnosis TEXT NOT NULL DEFAULT '',
  treatment_history TEXT NOT NULL DEFAULT '[]',
  allergies_snapshot TEXT NOT NULL DEFAULT '[]',
  current_medications_snapshot TEXT NOT NULL DEFAULT '[]',
  suicidality TEXT NOT NULL DEFAULT 'suicidality_none' CHECK (suicidality IN ('suicidality_none', 'ideation', 'plan', 'attempt')),
  substance_use INTEGER NOT NULL DEFAULT 0 CHECK (substance_use IN (0, 1)),
  created_by_user_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  encounter_id TEXT REFERENCES encounters(encounter_id),
  schema_version TEXT NOT NULL DEFAULT '2.0.0',
  resource_version INTEGER NOT NULL DEFAULT 1
);

CREATE INDEX IF NOT EXISTS idx_patient_intake_records_patient_id
  ON patient_intake_records(patient_id);

CREATE TABLE IF NOT EXISTS idempotency_records (
  actor_id TEXT NOT NULL,
  operation TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  request_fingerprint TEXT NOT NULL,
  response_status INTEGER NOT NULL,
  response_body TEXT NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (actor_id, operation, idempotency_key)
);
"""

PATIENT_IDENTITY_COLUMNS = {
    "id",
    "patient_code",
    "first_name",
    "last_name",
    "sex",
    "dob",
    "phone_number",
    "created_by_user_id",
    "created_at",
    "updated_at",
}

LEGACY_INTAKE_COLUMNS = {
    "presenting_complaint",
    "provisional_diagnosis",
    "treatment_history",
    "allergies",
    "current_medications",
    "suicidality",
    "substance_use",
}

PATIENT_TABLE_SQL = """
CREATE TABLE patients (
  id TEXT PRIMARY KEY,
  patient_code TEXT NOT NULL UNIQUE,
  first_name TEXT NOT NULL,
  last_name TEXT NOT NULL,
  sex TEXT NOT NULL CHECK (sex IN ('Male', 'Female')),
  dob TEXT NOT NULL,
  phone_number TEXT,
  created_by_user_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
)
"""

INTAKE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS patient_intake_records (
  id TEXT PRIMARY KEY,
  patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
  encounter_date TEXT NOT NULL,
  presenting_complaint TEXT NOT NULL DEFAULT '',
  provisional_diagnosis TEXT NOT NULL DEFAULT '',
  treatment_history TEXT NOT NULL DEFAULT '[]',
  allergies_snapshot TEXT NOT NULL DEFAULT '[]',
  current_medications_snapshot TEXT NOT NULL DEFAULT '[]',
  suicidality TEXT NOT NULL DEFAULT 'suicidality_none' CHECK (suicidality IN ('suicidality_none', 'ideation', 'plan', 'attempt')),
  substance_use INTEGER NOT NULL DEFAULT 0 CHECK (substance_use IN (0, 1)),
  created_by_user_id TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
)
"""


class DatabaseAdapter(Protocol):
    @contextmanager
    def connect(self) -> Iterator[Any]:
        ...

    def initialize(self) -> None:
        ...

    def ping(self) -> bool:
        ...


class SQLiteAdapter:
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
            existing_tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
            if "patients" in existing_tables:
                migrate_patients_to_identity_table(conn)
                preflight_v2_migration(conn)
            conn.executescript(SCHEMA)
            migrate_v2_contracts(conn)

    def ping(self) -> bool:
        with self.connect() as conn:
            conn.execute("SELECT 1").fetchone()
        return True


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def migrate_patients_to_identity_table(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(patients)").fetchall()}
    if PATIENT_IDENTITY_COLUMNS.issubset(columns) and not (columns & LEGACY_INTAKE_COLUMNS) and "age" not in columns:
        return

    rows = conn.execute("SELECT * FROM patients ORDER BY created_at ASC").fetchall()
    conn.execute("ALTER TABLE patients RENAME TO patients_legacy")
    conn.execute(PATIENT_TABLE_SQL)
    conn.execute(INTAKE_TABLE_SQL)

    for row in rows:
        row_keys = set(row.keys())
        created_at = row["created_at"] if "created_at" in row_keys else now_iso()
        updated_at = row["updated_at"] if "updated_at" in row_keys else created_at
        created_by_user_id = row["created_by_user_id"] if "created_by_user_id" in row_keys else "unknown"
        if "dob" not in row_keys:
            continue
        conn.execute(
            """
            INSERT INTO patients
              (id, patient_code, first_name, last_name, sex, dob, phone_number, created_by_user_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                row["id"],
                row["patient_code"],
                row["first_name"],
                row["last_name"],
                row["sex"],
                row["dob"],
                row["phone_number"] if "phone_number" in row_keys else None,
                created_by_user_id,
                created_at,
                updated_at,
            ),
        )

        if LEGACY_INTAKE_COLUMNS.issubset(row_keys):
            conn.execute(
                """
                INSERT INTO patient_intake_records
                  (
                    id, patient_id, encounter_date, presenting_complaint, provisional_diagnosis,
                    treatment_history, allergies_snapshot, current_medications_snapshot,
                    suicidality, substance_use, created_by_user_id, created_at, updated_at
                  )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    str(uuid4()),
                    row["id"],
                    created_at,
                    row["presenting_complaint"],
                    row["provisional_diagnosis"],
                    row["treatment_history"],
                    row["allergies"],
                    row["current_medications"],
                    row["suicidality"],
                    row["substance_use"],
                    created_by_user_id,
                    created_at,
                    updated_at,
                ),
            )

    conn.execute("DROP TABLE patients_legacy")


def _require_uuid(value: str, field: str) -> str:
    try:
        return str(UUID(value))
    except (ValueError, AttributeError) as error:
        raise RuntimeError(f"Cannot migrate invalid {field} UUID") from error


def _require_utc(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise RuntimeError(f"Cannot migrate non-UTC {field}")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise RuntimeError(f"Cannot migrate invalid {field}") from error
    return value


def preflight_v2_migration(conn: sqlite3.Connection) -> None:
    collisions = conn.execute(
        "SELECT UPPER(patient_code) FROM patients GROUP BY UPPER(patient_code) HAVING COUNT(*) > 1"
    ).fetchall()
    if collisions:
        raise RuntimeError("Cannot migrate case-insensitive patient-code collision")
    for patient in conn.execute("SELECT id, created_at, updated_at FROM patients").fetchall():
        _require_uuid(patient["id"], "patient")
        _require_utc(patient["created_at"], "patient created timestamp")
        _require_utc(patient["updated_at"], "patient updated timestamp")
    tables = {row["name"] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
    if "patient_intake_records" not in tables:
        return
    for intake in conn.execute(
        "SELECT id, patient_id, encounter_date, created_at, updated_at FROM patient_intake_records"
    ).fetchall():
        _require_uuid(intake["id"], "intake")
        _require_uuid(intake["patient_id"], "patient")
        _require_utc(intake["encounter_date"], "encounter timestamp")
        _require_utc(intake["created_at"], "intake created timestamp")
        _require_utc(intake["updated_at"], "intake updated timestamp")


def migrate_v2_contracts(conn: sqlite3.Connection) -> None:
    collisions = conn.execute(
        "SELECT UPPER(patient_code) FROM patients GROUP BY UPPER(patient_code) HAVING COUNT(*) > 1"
    ).fetchall()
    if collisions:
        raise RuntimeError("Cannot migrate case-insensitive patient-code collision")

    patient_columns = {row["name"] for row in conn.execute("PRAGMA table_info(patients)").fetchall()}
    if "schema_version" not in patient_columns:
        conn.execute("ALTER TABLE patients ADD COLUMN schema_version TEXT NOT NULL DEFAULT '2.0.0'")
    if "resource_version" not in patient_columns:
        conn.execute("ALTER TABLE patients ADD COLUMN resource_version INTEGER NOT NULL DEFAULT 1")

    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS patient_code_aliases (
          alias_id TEXT PRIMARY KEY,
          patient_id TEXT NOT NULL UNIQUE REFERENCES patients(id) ON DELETE CASCADE,
          patient_code TEXT NOT NULL COLLATE NOCASE UNIQUE,
          schema_version TEXT NOT NULL DEFAULT '2.0.0',
          resource_version INTEGER NOT NULL DEFAULT 1,
          created_by_user_id TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS encounters (
          encounter_id TEXT PRIMARY KEY,
          patient_id TEXT NOT NULL REFERENCES patients(id) ON DELETE CASCADE,
          encounter_type TEXT NOT NULL CHECK (encounter_type IN ('initial', 'follow-up')),
          occurred_at TEXT NOT NULL,
          legacy_intake_id TEXT UNIQUE,
          schema_version TEXT NOT NULL DEFAULT '2.0.0',
          resource_version INTEGER NOT NULL DEFAULT 1,
          created_by_user_id TEXT NOT NULL,
          created_at TEXT NOT NULL,
          updated_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS idempotency_records (
          actor_id TEXT NOT NULL,
          operation TEXT NOT NULL,
          idempotency_key TEXT NOT NULL,
          request_fingerprint TEXT NOT NULL,
          response_status INTEGER NOT NULL,
          response_body TEXT NOT NULL,
          created_at TEXT NOT NULL,
          PRIMARY KEY (actor_id, operation, idempotency_key)
        );
        """
    )

    intake_columns = {row["name"] for row in conn.execute("PRAGMA table_info(patient_intake_records)").fetchall()}
    if "encounter_id" not in intake_columns:
        conn.execute("ALTER TABLE patient_intake_records ADD COLUMN encounter_id TEXT REFERENCES encounters(encounter_id)")
    if "schema_version" not in intake_columns:
        conn.execute("ALTER TABLE patient_intake_records ADD COLUMN schema_version TEXT NOT NULL DEFAULT '2.0.0'")
    if "resource_version" not in intake_columns:
        conn.execute("ALTER TABLE patient_intake_records ADD COLUMN resource_version INTEGER NOT NULL DEFAULT 1")
    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_patient_intake_records_encounter_id "
        "ON patient_intake_records(encounter_id) WHERE encounter_id IS NOT NULL"
    )

    for patient in conn.execute("SELECT * FROM patients ORDER BY created_at, id").fetchall():
        patient_id = _require_uuid(patient["id"], "patient")
        alias_id = str(uuid5(NAMESPACE_URL, f"insight:add-new-patient:alias:{patient_id}"))
        patient_code = patient["patient_code"].upper()
        existing_alias = conn.execute(
            """
            SELECT * FROM patient_code_aliases
            WHERE alias_id = ? OR patient_id = ? OR patient_code = ? COLLATE NOCASE
            """,
            (alias_id, patient_id, patient_code),
        ).fetchall()
        if existing_alias:
            consistent = (
                len(existing_alias) == 1
                and existing_alias[0]["alias_id"] == alias_id
                and existing_alias[0]["patient_id"] == patient_id
                and existing_alias[0]["patient_code"].upper() == patient_code
            )
            if not consistent:
                raise RuntimeError("Cannot migrate inconsistent patient-code alias mapping")
            continue
        conn.execute(
            """
            INSERT INTO patient_code_aliases
              (alias_id, patient_id, patient_code, created_by_user_id, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                alias_id,
                patient_id,
                patient_code,
                patient["created_by_user_id"],
                patient["created_at"],
                patient["updated_at"],
            ),
        )

    intakes = conn.execute(
        "SELECT * FROM patient_intake_records WHERE encounter_id IS NULL ORDER BY created_at, id"
    ).fetchall()
    for intake in intakes:
        intake_id = _require_uuid(intake["id"], "intake")
        patient_id = _require_uuid(intake["patient_id"], "patient")
        encounter_id = str(uuid5(NAMESPACE_URL, f"insight:add-new-patient:encounter:{intake_id}"))
        conn.execute(
            """
            INSERT INTO encounters
              (encounter_id, patient_id, encounter_type, occurred_at, legacy_intake_id,
               created_by_user_id, created_at, updated_at)
            VALUES (?, ?, 'initial', ?, ?, ?, ?, ?)
            """,
            (
                encounter_id,
                patient_id,
                _require_utc(intake["encounter_date"], "encounter timestamp"),
                intake["id"],
                intake["created_by_user_id"],
                intake["created_at"],
                intake["updated_at"],
            ),
        )
        conn.execute(
            "UPDATE patient_intake_records SET encounter_id = ? WHERE id = ?",
            (encounter_id, intake["id"]),
        )
