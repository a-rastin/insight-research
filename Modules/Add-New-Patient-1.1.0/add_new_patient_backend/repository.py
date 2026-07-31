from __future__ import annotations

import json
import sqlite3
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import uuid4

from .db import DatabaseAdapter

SCHEMA_VERSION_V2 = "2.0.0"


class AliasCollisionError(Exception):
    pass


class IdempotencyConflictError(Exception):
    pass


class StaleResourceError(Exception):
    pass


def now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def json_list(value: str | None) -> list[str]:
    if not value:
        return []
    parsed = json.loads(value)
    return parsed if isinstance(parsed, list) else []


def canonical_suicidality(value: str | None) -> str:
    return "suicidality_none" if value in (None, "", "none") else value


def compute_age(dob_value: str) -> int:
    dob = date.fromisoformat(dob_value)
    today = datetime.now(UTC).date()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def patient_row(row: Any) -> dict[str, Any]:
    record = {
        "id": row["id"],
        "patientCode": row["patient_code"],
        "firstName": row["first_name"],
        "lastName": row["last_name"],
        "sex": row["sex"],
        "dob": row["dob"],
        "age": compute_age(row["dob"]),
        "phoneNumber": row["phone_number"],
        "createdByUserId": row["created_by_user_id"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }
    if "intake_id" not in row.keys() or row["intake_id"] is None:
        return record
    return {
        **record,
        "intakeId": row["intake_id"],
        "encounterDate": row["encounter_date"],
        "presentingComplaint": row["presenting_complaint"],
        "provisionalDiagnosis": row["provisional_diagnosis"],
        "treatmentHistory": json_list(row["treatment_history"]),
        "allergies": json_list(row["allergies_snapshot"]),
        "currentMedications": json_list(row["current_medications_snapshot"]),
        "riskFlags": {
            "suicidality": canonical_suicidality(row["suicidality"]),
            "substanceUse": bool(row["substance_use"]),
        },
    }


def intake_row(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "patientId": row["patient_id"],
        "encounterDate": row["encounter_date"],
        "presentingComplaint": row["presenting_complaint"],
        "provisionalDiagnosis": row["provisional_diagnosis"],
        "treatmentHistory": json_list(row["treatment_history"]),
        "allergies": json_list(row["allergies_snapshot"]),
        "currentMedications": json_list(row["current_medications_snapshot"]),
        "riskFlags": {
            "suicidality": canonical_suicidality(row["suicidality"]),
            "substanceUse": bool(row["substance_use"]),
        },
        "createdByUserId": row["created_by_user_id"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }


def provenance(row: Any, *, legacy_intake_id: str | None = None) -> dict[str, Any]:
    result = {
        "sourceModule": "add-new-patient",
        "createdByUserId": row["created_by_user_id"],
        "createdAt": row["created_at"],
        "updatedAt": row["updated_at"],
    }
    if legacy_intake_id:
        result["legacyIntakeId"] = legacy_intake_id
    return result


def patient_v2_row(row: Any) -> dict[str, Any]:
    return {
        "patientId": row["id"],
        "schemaVersion": row["schema_version"],
        "resourceVersion": row["resource_version"],
        "firstName": row["first_name"],
        "lastName": row["last_name"],
        "sex": row["sex"],
        "dob": row["dob"],
        "phoneNumber": row["phone_number"],
        "provenance": provenance(row),
    }


def alias_v2_row(row: Any) -> dict[str, Any]:
    return {
        "aliasId": row["alias_id"],
        "patientId": row["patient_id"],
        "patientCode": row["patient_code"],
        "schemaVersion": row["schema_version"],
        "resourceVersion": row["resource_version"],
        "provenance": provenance(row),
    }


def encounter_v2_row(row: Any) -> dict[str, Any]:
    return {
        "encounterId": row["encounter_id"],
        "patientId": row["patient_id"],
        "encounterType": row["encounter_type"],
        "occurredAt": row["occurred_at"],
        "schemaVersion": row["schema_version"],
        "resourceVersion": row["resource_version"],
        "provenance": provenance(row, legacy_intake_id=row["legacy_intake_id"]),
    }


def intake_v2_row(row: Any) -> dict[str, Any]:
    return {
        "intakeSnapshotId": row["id"],
        "patientId": row["patient_id"],
        "encounterId": row["encounter_id"],
        "schemaVersion": row["schema_version"],
        "resourceVersion": row["resource_version"],
        "presentingComplaint": row["presenting_complaint"],
        "provisionalDiagnosis": row["provisional_diagnosis"],
        "treatmentHistory": json_list(row["treatment_history"]),
        "allergies": json_list(row["allergies_snapshot"]),
        "currentMedications": json_list(row["current_medications_snapshot"]),
        "riskFlags": {
            "suicidality": canonical_suicidality(row["suicidality"]),
            "substanceUse": bool(row["substance_use"]),
        },
        "provenance": provenance(row, legacy_intake_id=row["legacy_intake_id"]),
    }


def follow_up_delta_row(row: Any) -> dict[str, Any]:
    return {
        "schemaVersion": row["schema_version"],
        "deltaId": row["delta_id"],
        "patientId": row["patient_id"],
        "priorEncounterId": row["prior_encounter_id"],
        "encounterId": row["encounter_id"],
        "priorFinalPlanId": row["prior_final_plan_id"],
        "recordedAt": row["recorded_at"],
        "changes": json.loads(row["changes_json"]),
    }


def _find_patient_id_row(conn: Any, id_or_code: str) -> Any:
    return conn.execute(
        "SELECT id FROM patients WHERE id = ? OR patient_code = ?",
        (id_or_code, id_or_code.upper()),
    ).fetchone()


CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


class PatientRepository:
    def __init__(self, adapter: DatabaseAdapter) -> None:
        self.adapter = adapter

    def initialize(self) -> None:
        self.adapter.initialize()

    def ping(self) -> bool:
        return self.adapter.ping()

    def list_patients(self) -> list[dict[str, Any]]:
        with self.adapter.connect() as conn:
            rows = conn.execute(
                """
                SELECT
                  p.*,
                  i.id AS intake_id,
                  i.encounter_date,
                  i.presenting_complaint,
                  i.provisional_diagnosis,
                  i.treatment_history,
                  i.allergies_snapshot,
                  i.current_medications_snapshot,
                  i.suicidality,
                  i.substance_use
                FROM patients p
                LEFT JOIN patient_intake_records i ON i.id = (
                  SELECT id FROM patient_intake_records
                  WHERE patient_id = p.id
                  ORDER BY encounter_date DESC, created_at DESC
                  LIMIT 1
                )
                ORDER BY p.created_at ASC
                """
            ).fetchall()
        return [patient_row(row) for row in rows]

    def get_patient(self, id_or_code: str) -> dict[str, Any] | None:
        with self.adapter.connect() as conn:
            row = conn.execute(
                """
                SELECT
                  p.*,
                  i.id AS intake_id,
                  i.encounter_date,
                  i.presenting_complaint,
                  i.provisional_diagnosis,
                  i.treatment_history,
                  i.allergies_snapshot,
                  i.current_medications_snapshot,
                  i.suicidality,
                  i.substance_use
                FROM patients p
                LEFT JOIN patient_intake_records i ON i.id = (
                  SELECT id FROM patient_intake_records
                  WHERE patient_id = p.id
                  ORDER BY encounter_date DESC, created_at DESC
                  LIMIT 1
                )
                WHERE p.id = ? OR p.patient_code = ?
                """,
                (id_or_code, id_or_code.upper()),
            ).fetchone()
        return patient_row(row) if row else None

    def list_intake_records(self, id_or_code: str) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
        with self.adapter.connect() as conn:
            patient = conn.execute(
                """
                SELECT
                  p.*,
                  i.id AS intake_id,
                  i.encounter_date,
                  i.presenting_complaint,
                  i.provisional_diagnosis,
                  i.treatment_history,
                  i.allergies_snapshot,
                  i.current_medications_snapshot,
                  i.suicidality,
                  i.substance_use
                FROM patients p
                LEFT JOIN patient_intake_records i ON i.id = (
                  SELECT id FROM patient_intake_records
                  WHERE patient_id = p.id
                  ORDER BY encounter_date DESC, created_at DESC
                  LIMIT 1
                )
                WHERE p.id = ? OR p.patient_code = ?
                """,
                (id_or_code, id_or_code.upper()),
            ).fetchone()
            if not patient:
                return None
            patient_dict = patient_row(patient)
            intake_rows = conn.execute(
                """
                SELECT id, patient_id, encounter_date, presenting_complaint, provisional_diagnosis,
                       treatment_history, allergies_snapshot, current_medications_snapshot,
                       suicidality, substance_use, created_by_user_id, created_at, updated_at
                FROM patient_intake_records
                WHERE patient_id = ?
                ORDER BY encounter_date DESC, created_at DESC
                """,
                (patient_dict["id"],),
            ).fetchall()
        return patient_dict, [intake_row(row) for row in intake_rows]

    def create_patient(self, patient: dict[str, Any], created_by_user_id: str) -> dict[str, Any]:
        encounter_date = patient.get("encounterDate") or now_iso()
        data = {
            "patient": {
                "patientCode": patient["patientCode"],
                "firstName": patient["firstName"],
                "lastName": patient["lastName"],
                "sex": patient["sex"],
                "dob": patient["dob"],
                "phoneNumber": patient.get("phoneNumber") or None,
            },
            "encounter": {"encounterType": "initial", "occurredAt": encounter_date},
            "intakeSnapshot": {
                "presentingComplaint": patient["presentingComplaint"],
                "provisionalDiagnosis": patient["provisionalDiagnosis"],
                "treatmentHistory": patient.get("treatmentHistory") or [],
                "allergies": patient.get("allergies") or [],
                "currentMedications": patient.get("currentMedications") or [],
                "riskFlags": patient.get("riskFlags") or {},
            },
        }
        adapter_key = f"legacy-adapter-{uuid4()}"
        fingerprint = json.dumps(data, sort_keys=True, separators=(",", ":"))
        body, _ = self.create_patient_encounter_v2(
            data,
            created_by_user_id,
            adapter_key,
            fingerprint,
            operation="legacy-create-patient-adapter",
        )
        return self.get_patient(body["patient"]["patientId"])  # type: ignore[return-value]

    def existing_codes(self) -> set[str]:
        with self.adapter.connect() as conn:
            rows = conn.execute("SELECT patient_code FROM patients").fetchall()
        return {row["patient_code"] for row in rows}

    def get_patient_v2(self, patient_id: str) -> dict[str, Any] | None:
        with self.adapter.connect() as conn:
            row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
        return patient_v2_row(row) if row else None

    def get_alias_v2(self, patient_code: str) -> dict[str, Any] | None:
        with self.adapter.connect() as conn:
            rows = conn.execute(
                "SELECT * FROM patient_code_aliases WHERE patient_code = ? COLLATE NOCASE",
                (patient_code,),
            ).fetchall()
        if len(rows) > 1:
            raise AliasCollisionError("Patient-code alias is ambiguous")
        return alias_v2_row(rows[0]) if rows else None

    def get_encounter_v2(self, encounter_id: str) -> dict[str, Any] | None:
        with self.adapter.connect() as conn:
            row = conn.execute("SELECT * FROM encounters WHERE encounter_id = ?", (encounter_id,)).fetchone()
        return encounter_v2_row(row) if row else None

    def get_intake_snapshot_v2(self, encounter_id: str) -> dict[str, Any] | None:
        with self.adapter.connect() as conn:
            row = conn.execute(
                """
                SELECT i.*, e.legacy_intake_id
                FROM patient_intake_records i
                JOIN encounters e ON e.encounter_id = i.encounter_id
                WHERE i.encounter_id = ?
                """,
                (encounter_id,),
            ).fetchone()
        return intake_v2_row(row) if row else None

    def list_history_v2(self, patient_id: str) -> list[dict[str, Any]] | None:
        with self.adapter.connect() as conn:
            if not conn.execute("SELECT 1 FROM patients WHERE id = ?", (patient_id,)).fetchone():
                return None
            rows = conn.execute(
                """
                SELECT e.*, d.delta_id, d.prior_encounter_id, d.prior_final_plan_id,
                       d.changes_json, d.recorded_at, d.schema_version AS delta_schema_version
                FROM encounters e
                LEFT JOIN follow_up_deltas d ON d.encounter_id = e.encounter_id
                WHERE e.patient_id = ?
                ORDER BY e.occurred_at DESC, e.created_at DESC
                """,
                (patient_id,),
            ).fetchall()
        history = []
        for row in rows:
            item: dict[str, Any] = {"encounter": encounter_v2_row(row), "followUpDelta": None}
            if row["delta_id"]:
                item["followUpDelta"] = {
                    "schemaVersion": row["delta_schema_version"],
                    "deltaId": row["delta_id"],
                    "patientId": row["patient_id"],
                    "priorEncounterId": row["prior_encounter_id"],
                    "encounterId": row["encounter_id"],
                    "priorFinalPlanId": row["prior_final_plan_id"],
                    "recordedAt": row["recorded_at"],
                    "changes": json.loads(row["changes_json"]),
                }
            history.append(item)
        return history

    def create_follow_up_v1(
        self,
        patient_id: str,
        data: dict[str, Any],
        actor_id: str,
        idempotency_key: str,
        request_fingerprint: str,
        expected_patient_version: int,
    ) -> tuple[dict[str, Any], bool]:
        operation = f"create-follow-up-v1:{patient_id}"
        with self.adapter.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            now = now_iso()
            retention_cutoff = (datetime.now(UTC) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
            conn.execute("DELETE FROM idempotency_records WHERE created_at < ?", (retention_cutoff,))
            previous = conn.execute(
                "SELECT request_fingerprint, response_body FROM idempotency_records "
                "WHERE actor_id = ? AND operation = ? AND idempotency_key = ?",
                (actor_id, operation, idempotency_key),
            ).fetchone()
            if previous:
                if previous["request_fingerprint"] != request_fingerprint:
                    raise IdempotencyConflictError("Idempotency key was reused with a different request")
                return json.loads(previous["response_body"]), True
            patient = conn.execute(
                "SELECT resource_version FROM patients WHERE id = ?", (patient_id,)
            ).fetchone()
            if not patient:
                raise KeyError("patient")
            if patient["resource_version"] != expected_patient_version:
                raise StaleResourceError("Patient resource version is stale")
            prior = conn.execute(
                "SELECT * FROM encounters WHERE encounter_id = ? AND patient_id = ?",
                (data["priorEncounterId"], patient_id),
            ).fetchone()
            if not prior:
                raise KeyError("priorEncounter")
            if data["occurredAt"] <= prior["occurred_at"]:
                raise ValueError("Follow-up Encounter must occur after the prior Encounter")
            encounter_id = str(uuid4())
            delta_id = str(uuid4())
            conn.execute(
                """
                INSERT INTO encounters
                  (encounter_id, patient_id, encounter_type, occurred_at, schema_version,
                   resource_version, created_by_user_id, created_at, updated_at)
                VALUES (?, ?, 'follow-up', ?, ?, 1, ?, ?, ?)
                """,
                (encounter_id, patient_id, data["occurredAt"], SCHEMA_VERSION_V2, actor_id, now, now),
            )
            conn.execute(
                """
                INSERT INTO follow_up_deltas
                  (delta_id, patient_id, prior_encounter_id, encounter_id, prior_final_plan_id,
                   changes_json, created_by_user_id, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    delta_id,
                    patient_id,
                    data["priorEncounterId"],
                    encounter_id,
                    data["priorFinalPlanId"],
                    json.dumps(data["changes"], separators=(",", ":")),
                    actor_id,
                    now,
                ),
            )
            encounter = conn.execute(
                "SELECT * FROM encounters WHERE encounter_id = ?", (encounter_id,)
            ).fetchone()
            delta = conn.execute(
                "SELECT * FROM follow_up_deltas WHERE delta_id = ?", (delta_id,)
            ).fetchone()
            body = {"encounter": encounter_v2_row(encounter), "followUpDelta": follow_up_delta_row(delta)}
            conn.execute(
                """
                INSERT INTO idempotency_records
                  (actor_id, operation, idempotency_key, request_fingerprint,
                   response_status, response_body, created_at)
                VALUES (?, ?, ?, ?, 201, ?, ?)
                """,
                (actor_id, operation, idempotency_key, request_fingerprint, json.dumps(body), now),
            )
            return body, False

    def list_patients_v2(
        self,
        offset: int,
        page_size: int,
        query: str | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        where = ""
        params: list[Any] = []
        if query is not None:
            where = (
                "WHERE a.patient_code = ? COLLATE NOCASE "
                "OR p.first_name LIKE ? COLLATE NOCASE OR p.last_name LIKE ? COLLATE NOCASE"
            )
            params.extend([query, f"%{query}%", f"%{query}%"])
        params.extend([page_size + 1, offset])
        with self.adapter.connect() as conn:
            rows = conn.execute(
                f"""
                SELECT
                  p.*,
                  a.alias_id AS a_alias_id,
                  a.patient_id AS a_patient_id,
                  a.patient_code AS a_patient_code,
                  a.schema_version AS a_schema_version,
                  a.resource_version AS a_resource_version,
                  a.created_by_user_id AS a_created_by_user_id,
                  a.created_at AS a_created_at,
                  a.updated_at AS a_updated_at
                FROM patients p
                JOIN patient_code_aliases a ON a.patient_id = p.id
                {where}
                ORDER BY p.created_at, p.id
                LIMIT ? OFFSET ?
                """,
                params,
            ).fetchall()
        has_more = len(rows) > page_size
        items = []
        for row in rows[:page_size]:
            alias = {
                "aliasId": row["a_alias_id"],
                "patientId": row["a_patient_id"],
                "patientCode": row["a_patient_code"],
                "schemaVersion": row["a_schema_version"],
                "resourceVersion": row["a_resource_version"],
                "provenance": {
                    "sourceModule": "add-new-patient",
                    "createdByUserId": row["a_created_by_user_id"],
                    "createdAt": row["a_created_at"],
                    "updatedAt": row["a_updated_at"],
                },
            }
            items.append({"patient": patient_v2_row(row), "patientCodeAlias": alias})
        return items, has_more

    def create_patient_encounter_v2(
        self,
        data: dict[str, Any],
        actor_id: str,
        idempotency_key: str,
        request_fingerprint: str,
        *,
        operation: str = "create-patient-first-encounter-v2",
    ) -> tuple[dict[str, Any], bool]:
        try:
            with self.adapter.connect() as conn:
                conn.execute("BEGIN IMMEDIATE")
                now = now_iso()
                retention_cutoff = (datetime.now(UTC) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
                conn.execute("DELETE FROM idempotency_records WHERE created_at < ?", (retention_cutoff,))
                previous = conn.execute(
                    """
                    SELECT request_fingerprint, response_body FROM idempotency_records
                    WHERE actor_id = ? AND operation = ? AND idempotency_key = ?
                    """,
                    (actor_id, operation, idempotency_key),
                ).fetchone()
                if previous:
                    if previous["request_fingerprint"] != request_fingerprint:
                        raise IdempotencyConflictError("Idempotency key was reused with a different request")
                    return json.loads(previous["response_body"]), True

                patient_id = str(uuid4())
                alias_id = str(uuid4())
                encounter_id = str(uuid4())
                intake_id = str(uuid4())
                patient = data["patient"]
                encounter = data["encounter"]
                intake = data["intakeSnapshot"]
                conn.execute(
                    """
                    INSERT INTO patients
                      (id, patient_code, first_name, last_name, sex, dob, phone_number,
                       created_by_user_id, created_at, updated_at, schema_version, resource_version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        patient_id,
                        patient["patientCode"],
                        patient["firstName"],
                        patient["lastName"],
                        patient["sex"],
                        patient["dob"],
                        patient.get("phoneNumber"),
                        actor_id,
                        now,
                        now,
                        SCHEMA_VERSION_V2,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO patient_code_aliases
                      (alias_id, patient_id, patient_code, schema_version, resource_version,
                       created_by_user_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, 1, ?, ?, ?)
                    """,
                    (alias_id, patient_id, patient["patientCode"], SCHEMA_VERSION_V2, actor_id, now, now),
                )
                conn.execute(
                    """
                    INSERT INTO encounters
                      (encounter_id, patient_id, encounter_type, occurred_at, schema_version,
                       resource_version, created_by_user_id, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?, ?, ?)
                    """,
                    (
                        encounter_id,
                        patient_id,
                        encounter["encounterType"],
                        encounter["occurredAt"],
                        SCHEMA_VERSION_V2,
                        actor_id,
                        now,
                        now,
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO patient_intake_records
                      (id, patient_id, encounter_date, presenting_complaint, provisional_diagnosis,
                       treatment_history, allergies_snapshot, current_medications_snapshot,
                       suicidality, substance_use, created_by_user_id, created_at, updated_at,
                       encounter_id, schema_version, resource_version)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                    """,
                    (
                        intake_id,
                        patient_id,
                        encounter["occurredAt"],
                        intake["presentingComplaint"],
                        intake["provisionalDiagnosis"],
                        json.dumps(intake.get("treatmentHistory") or []),
                        json.dumps(intake.get("allergies") or []),
                        json.dumps(intake.get("currentMedications") or []),
                        canonical_suicidality((intake.get("riskFlags") or {}).get("suicidality")),
                        1 if (intake.get("riskFlags") or {}).get("substanceUse", False) else 0,
                        actor_id,
                        now,
                        now,
                        encounter_id,
                        SCHEMA_VERSION_V2,
                    ),
                )
                patient_resource = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
                alias_resource = conn.execute("SELECT * FROM patient_code_aliases WHERE alias_id = ?", (alias_id,)).fetchone()
                encounter_resource = conn.execute("SELECT * FROM encounters WHERE encounter_id = ?", (encounter_id,)).fetchone()
                intake_resource = conn.execute(
                    """
                    SELECT i.*, e.legacy_intake_id FROM patient_intake_records i
                    JOIN encounters e ON e.encounter_id = i.encounter_id WHERE i.id = ?
                    """,
                    (intake_id,),
                ).fetchone()
                body = {
                    "patient": patient_v2_row(patient_resource),
                    "patientCodeAlias": alias_v2_row(alias_resource),
                    "encounter": encounter_v2_row(encounter_resource),
                    "intakeSnapshot": intake_v2_row(intake_resource),
                }
                conn.execute(
                    """
                    INSERT INTO idempotency_records
                      (actor_id, operation, idempotency_key, request_fingerprint,
                       response_status, response_body, created_at)
                    VALUES (?, ?, ?, ?, 201, ?, ?)
                    """,
                    (actor_id, operation, idempotency_key, request_fingerprint, json.dumps(body), now),
                )
                return body, False
        except sqlite3.IntegrityError as error:
            if "patient_code" in str(error).lower():
                raise AliasCollisionError("Patient-code alias already exists") from error
            raise

    def update_patient_v2(self, patient_id: str, expected_version: int, changes: dict[str, Any]) -> dict[str, Any] | None:
        columns = {
            "firstName": "first_name",
            "lastName": "last_name",
            "sex": "sex",
            "dob": "dob",
            "phoneNumber": "phone_number",
        }
        assignments = [f"{columns[field]} = ?" for field in changes]
        values = [changes[field] for field in changes]
        now = now_iso()
        with self.adapter.connect() as conn:
            exists = conn.execute("SELECT resource_version FROM patients WHERE id = ?", (patient_id,)).fetchone()
            if not exists:
                return None
            if exists["resource_version"] != expected_version:
                raise StaleResourceError("Patient resource version is stale")
            cursor = conn.execute(
                f"""
                UPDATE patients SET {', '.join(assignments)}, updated_at = ?, resource_version = resource_version + 1
                WHERE id = ? AND resource_version = ?
                """,
                (*values, now, patient_id, expected_version),
            )
            if cursor.rowcount != 1:
                raise StaleResourceError("Patient resource version is stale")
            row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
        return patient_v2_row(row)
