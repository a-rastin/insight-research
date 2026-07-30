from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen
from uuid import UUID, uuid4

from jsonschema import Draft202012Validator, FormatChecker

from test_add_new_patient_backend import AddNewPatientServer, PSY_HEADER, csrf_headers


ROOT = Path(__file__).resolve().parent
SCHEMA_PATH = ROOT / "schema" / "patient-encounter-v2.schema.json"
OPENAPI_PATH = ROOT / "schema" / "patient-encounter-v2.openapi.json"
V2 = "/api/add-new-patient/v2"


def valid_v2_payload(code: str | None = "V2TEST") -> dict:
    return {
        "patient": {
            "patientCode": code,
            "firstName": "Jane",
            "lastName": "Doe",
            "sex": "Female",
            "dob": "1986-07-29",
            "phoneNumber": "5551234567",
        },
        "encounter": {"encounterType": "initial", "occurredAt": "2026-07-29T10:00:00Z"},
        "intakeSnapshot": {
            "presentingComplaint": "Clinical intake fixture.",
            "provisionalDiagnosis": "F20.9",
            "treatmentHistory": [],
            "allergies": [],
            "currentMedications": [],
            "riskFlags": {"suicidality": "suicidality_none", "substanceUse": False},
        },
    }


def request_v2(
    base: str,
    path: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: dict | None = None,
) -> tuple[int, dict, dict[str, str]]:
    data = json.dumps(body, separators=(",", ":")).encode("utf-8") if body is not None else None
    request = Request(
        f"{base}{path}",
        data=data,
        method=method,
        headers={"content-type": "application/json", **(headers or {})},
    )
    try:
        with urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read()), {key.lower(): value for key, value in response.headers.items()}
    except HTTPError as error:
        try:
            return error.code, json.loads(error.read()), {key.lower(): value for key, value in error.headers.items()}
        finally:
            error.close()


def create_headers(base: str, key: str = "encounter-v2-key-0001") -> dict[str, str]:
    return {
        **csrf_headers(base, PSY_HEADER),
        "x-schema-version": "2.0.0",
        "idempotency-key": key,
    }


class PatientEncounterV2ContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
        cls.openapi = json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))

    def validate_definition(self, name: str, value: dict) -> None:
        schema = {**self.schema, "$ref": f"#/$defs/{name}"}
        Draft202012Validator(schema, format_checker=FormatChecker()).validate(value)

    def test_json_schema_openapi_and_atomic_resource_contract(self) -> None:
        Draft202012Validator.check_schema(self.schema)
        self.assertEqual(self.openapi["openapi"], "3.1.0")
        self.assertEqual(self.openapi["info"]["version"], "2.0.0")
        refs = []

        def collect(value: object) -> None:
            if isinstance(value, dict):
                refs.extend(item for key, item in value.items() if key == "$ref")
                for item in value.values():
                    collect(item)
            elif isinstance(value, list):
                for item in value:
                    collect(item)

        collect(self.openapi)
        for ref in refs:
            if ref.startswith("#/",):
                target = self.openapi
                for part in ref[2:].split("/"):
                    target = target[part]
                self.assertIsInstance(target, dict)
            else:
                filename, fragment = ref.split("#", 1)
                self.assertEqual(filename, SCHEMA_PATH.name)
                target = self.schema
                for part in fragment.removeprefix("/").split("/"):
                    target = target[part]
                self.assertIsInstance(target, dict)

        with AddNewPatientServer() as base:
            discovery = request_v2(base, f"{V2}/contract")
            self.assertEqual(discovery[0], 200)
            self.assertEqual(
                set(discovery[1]),
                {
                    "moduleId",
                    "moduleVersion",
                    "interfaceVersion",
                    "schemaVersions",
                    "profileVersion",
                    "openapiPath",
                    "idempotencyKeyRetentionSeconds",
                    "time",
                },
            )
            self.assertEqual(request_v2(base, discovery[1]["openapiPath"])[1], self.openapi)
            self.assertEqual(request_v2(base, f"{V2}/patient-encounter-v2.schema.json")[1], self.schema)

        server = AddNewPatientServer()
        with server as base:
            status, body, headers = request_v2(
                base,
                f"{V2}/patients",
                "POST",
                create_headers(base),
                valid_v2_payload(),
            )
            self.assertEqual(status, 201)
            self.assertEqual(headers["x-schema-version"], "2.0.0")
            self.validate_definition("createPatientEncounterResponse", body)
            patient_id = body["patient"]["patientId"]
            encounter_id = body["encounter"]["encounterId"]
            self.assertNotEqual(patient_id, encounter_id)
            self.assertEqual(body["patientCodeAlias"]["patientId"], patient_id)
            self.assertEqual(body["encounter"]["patientId"], patient_id)
            self.assertEqual(body["intakeSnapshot"]["encounterId"], encounter_id)
            with sqlite3.connect(server.db_path) as conn:
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM encounters").fetchone()[0], 1)
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM patient_intake_records").fetchone()[0], 1)

    def test_idempotent_replay_changed_payload_and_alias_collision_fail_closed(self) -> None:
        server = AddNewPatientServer()
        with server as base:
            headers = create_headers(base)
            first = request_v2(base, f"{V2}/patients", "POST", headers, valid_v2_payload())
            replay = request_v2(base, f"{V2}/patients", "POST", headers, valid_v2_payload())
            self.assertEqual(first[0], 201)
            self.assertEqual(replay[0], 201)
            self.assertEqual(first[1], replay[1])
            self.assertEqual(replay[2]["idempotency-replayed"], "true")

            changed = valid_v2_payload()
            changed["patient"]["firstName"] = "Changed"
            conflict = request_v2(base, f"{V2}/patients", "POST", headers, changed)
            self.assertEqual(conflict[0], 409)
            self.assertEqual(conflict[1]["code"], "COMMON_IDEMPOTENCY_KEY_REUSED")

            collision = request_v2(
                base,
                f"{V2}/patients",
                "POST",
                create_headers(base, "encounter-v2-key-0002"),
                valid_v2_payload("v2test"),
            )
            self.assertEqual(collision[0], 409)
            self.assertEqual(collision[1]["code"], "PATIENT_ALIAS_COLLISION")

            expiring_headers = create_headers(base, "encounter-v2-expiry-001")
            expiring_payload = valid_v2_payload(None)
            expiring = request_v2(base, f"{V2}/patients", "POST", expiring_headers, expiring_payload)
            with sqlite3.connect(server.db_path) as conn:
                conn.execute(
                    "UPDATE idempotency_records SET created_at = '2000-01-01T00:00:00Z' WHERE idempotency_key = ?",
                    ("encounter-v2-expiry-001",),
                )
            after_expiry = request_v2(base, f"{V2}/patients", "POST", expiring_headers, expiring_payload)
            self.assertEqual(after_expiry[0], 201)
            self.assertNotEqual(expiring[1]["patient"]["patientId"], after_expiry[1]["patient"]["patientId"])

    def test_uuid_lookup_alias_resolution_and_utc_validation(self) -> None:
        with AddNewPatientServer() as base:
            created = request_v2(
                base,
                f"{V2}/patients",
                "POST",
                create_headers(base),
                valid_v2_payload(),
            )[1]
            invalid = request_v2(base, f"{V2}/patients/V2TEST", headers=PSY_HEADER)
            self.assertEqual(invalid[0], 400)
            self.assertEqual(invalid[1]["code"], "PATIENT_ID_INVALID")

            alias = request_v2(
                base,
                f"{V2}/patient-code-aliases/resolve",
                "POST",
                {**PSY_HEADER, "x-schema-version": "2.0.0"},
                {"patientCode": "v2test"},
            )
            self.assertEqual(alias[0], 200)
            self.assertEqual(alias[1]["patientId"], created["patient"]["patientId"])

            invalid_time = valid_v2_payload("UTCBAD")
            invalid_time["encounter"]["occurredAt"] = "2026-07-29T12:00:00+02:00"
            rejected = request_v2(
                base,
                f"{V2}/patients",
                "POST",
                create_headers(base, "encounter-v2-key-0003"),
                invalid_time,
            )
            self.assertEqual(rejected[0], 422)
            self.assertEqual(rejected[1]["code"], "PATIENT_CONTRACT_VALIDATION_FAILED")

            invalid_phone = valid_v2_payload("PHNBAD")
            invalid_phone["patient"]["phoneNumber"] = "555123456"
            rejected_phone = request_v2(
                base,
                f"{V2}/patients",
                "POST",
                create_headers(base, "encounter-v2-key-0004"),
                invalid_phone,
            )
            self.assertEqual(rejected_phone[0], 422)

    def test_strong_etag_rejects_stale_patch(self) -> None:
        with AddNewPatientServer() as base:
            created = request_v2(
                base,
                f"{V2}/patients",
                "POST",
                create_headers(base),
                valid_v2_payload(),
            )[1]
            patient_id = created["patient"]["patientId"]
            fetched = request_v2(base, f"{V2}/patients/{patient_id}", headers=PSY_HEADER)
            etag = fetched[2]["etag"]
            patch_headers = {
                **csrf_headers(base, PSY_HEADER),
                "x-schema-version": "2.0.0",
                "if-match": etag,
            }
            updated = request_v2(base, f"{V2}/patients/{patient_id}", "PATCH", patch_headers, {"firstName": "Janet"})
            self.assertEqual(updated[0], 200)
            self.assertEqual(updated[1]["resourceVersion"], 2)
            stale = request_v2(base, f"{V2}/patients/{patient_id}", "PATCH", patch_headers, {"lastName": "Smith"})
            self.assertEqual(stale[0], 412)
            self.assertEqual(stale[1]["code"], "COMMON_PRECONDITION_FAILED")

    def test_list_and_search_pagination(self) -> None:
        with AddNewPatientServer() as base:
            for index in range(3):
                status, _, _ = request_v2(
                    base,
                    f"{V2}/patients",
                    "POST",
                    create_headers(base, f"encounter-v2-page-{index:04d}"),
                    valid_v2_payload(f"PAGE{index + 1:02d}"),
                )
                self.assertEqual(status, 201)
            page_one = request_v2(base, f"{V2}/patients?pageSize=2", headers=PSY_HEADER)
            self.assertEqual(page_one[0], 200)
            self.assertEqual(len(page_one[1]["items"]), 2)
            token = page_one[1]["nextPageToken"]
            page_two = request_v2(base, f"{V2}/patients?pageSize=2&pageToken={token}", headers=PSY_HEADER)
            self.assertEqual(len(page_two[1]["items"]), 1)
            self.assertIsNone(page_two[1]["nextPageToken"])

            search = request_v2(
                base,
                f"{V2}/patients/search",
                "POST",
                {**PSY_HEADER, "x-schema-version": "2.0.0"},
                {"query": "PAGE02", "pageSize": 1},
            )
            self.assertEqual(search[0], 200)
            self.assertEqual([item["patientCodeAlias"]["patientCode"] for item in search[1]["items"]], ["PAGE02"])

    def test_request_ids_problem_details_auth_and_csrf(self) -> None:
        supplied_request_id = str(uuid4())
        with AddNewPatientServer() as base:
            contract = request_v2(
                base,
                f"{V2}/contract",
                headers={"x-request-id": supplied_request_id},
            )
            self.assertEqual(contract[2]["x-request-id"], supplied_request_id)
            self.assertEqual(contract[2]["x-correlation-id"], supplied_request_id)

            unauthenticated = request_v2(base, f"{V2}/patients")
            self.assertEqual(unauthenticated[0], 401)
            self.assertEqual(unauthenticated[2]["content-type"].split(";", 1)[0], "application/problem+json")
            self.assertEqual(unauthenticated[1]["code"], "AUTHENTICATION_SESSION_REQUIRED")
            self.assertEqual(unauthenticated[1]["requestId"], unauthenticated[2]["x-request-id"])
            self.assertEqual(
                set(unauthenticated[1]),
                {"type", "title", "status", "code", "requestId"},
            )

            csrf_rejected = request_v2(
                base,
                f"{V2}/patients",
                "POST",
                {**PSY_HEADER, "x-schema-version": "2.0.0", "idempotency-key": "encounter-v2-csrf-0001"},
                valid_v2_payload("CSRF01"),
            )
            self.assertEqual(csrf_rejected[0], 403)
            self.assertEqual(csrf_rejected[1]["code"], "CSRF_TOKEN_INVALID")
            self.assertEqual(csrf_rejected[2]["x-schema-version"], "2.0.0")

            unauthenticated_write = request_v2(
                base,
                f"{V2}/patients",
                "POST",
                {"x-schema-version": "2.0.0", "idempotency-key": "encounter-v2-auth-0001"},
                valid_v2_payload("AUTH01"),
            )
            self.assertEqual(unauthenticated_write[0], 401)
            self.assertEqual(unauthenticated_write[1]["code"], "AUTHENTICATION_SESSION_REQUIRED")

    def test_v2_write_rejects_authenticated_admin(self) -> None:
        from test_add_new_patient_backend import (
            ADMIN_SESSION_ID,
            ADMIN_USER_ID,
            MockAuthenticationServer,
            auth_payload,
        )

        with MockAuthenticationServer() as mock_auth:
            mock_auth.set_payload(
                "admin-session",
                auth_payload(
                    session={"id": ADMIN_SESSION_ID},
                    user={"id": ADMIN_USER_ID, "username": "admin", "role": "admin"},
                    compatibility={"legacyUserId": 2, "legacyRole": None},
                ),
            )
            with AddNewPatientServer(auth_session_url=mock_auth.url) as base:
                headers = {
                    **csrf_headers(base, {"x-auth-session": "admin-session"}),
                    "x-schema-version": "2.0.0",
                    "idempotency-key": "encounter-v2-admin-0001",
                }
                rejected = request_v2(
                    base,
                    f"{V2}/patients",
                    "POST",
                    headers,
                    valid_v2_payload("ADMIN1"),
                )
                self.assertEqual(rejected[0], 403)
                self.assertEqual(rejected[1]["code"], "AUTHORIZATION_ROLE_REQUIRED")

    def test_legacy_create_is_equivalent_v2_adapter(self) -> None:
        from test_add_new_patient_backend import request_json

        server = AddNewPatientServer()
        with server as base:
            legacy_payload = {
                "demographics": {
                    "patientCode": "LEGACY",
                    "firstName": "Jane",
                    "lastName": "Doe",
                    "sex": "Female",
                    "dob": "1986-07-29",
                    "phoneNumber": "5551234567",
                },
                "clinical": {
                    "encounterDate": "2026-07-29T10:00:00Z",
                    "presentingComplaint": "Clinical intake fixture.",
                    "provisionalDiagnosis": "F20.9",
                    "treatmentHistory": [],
                    "allergies": [],
                    "currentMedications": [],
                    "riskFlags": {"suicidality": "suicidality_none", "substanceUse": False},
                },
            }
            legacy_status, legacy_body = request_json(
                base,
                "/api/patients",
                "POST",
                csrf_headers(base, PSY_HEADER),
                legacy_payload,
            )
            self.assertEqual(legacy_status, 201)
            legacy_patient_id = legacy_body["patient"]["id"]
            with sqlite3.connect(server.db_path) as conn:
                conn.row_factory = sqlite3.Row
                encounter = conn.execute(
                    "SELECT encounter_id FROM encounters WHERE patient_id = ?",
                    (legacy_patient_id,),
                ).fetchone()
            self.assertIsNotNone(encounter)
            patient = request_v2(base, f"{V2}/patients/{legacy_patient_id}", headers=PSY_HEADER)[1]
            encounter_body = request_v2(
                base,
                f"{V2}/encounters/{encounter['encounter_id']}",
                headers=PSY_HEADER,
            )[1]
            snapshot = request_v2(
                base,
                f"{V2}/encounters/{encounter['encounter_id']}/intake-snapshot",
                headers=PSY_HEADER,
            )[1]
            self.assertEqual(patient["firstName"], legacy_payload["demographics"]["firstName"])
            self.assertEqual(encounter_body["occurredAt"], legacy_payload["clinical"]["encounterDate"])
            self.assertEqual(snapshot["presentingComplaint"], legacy_payload["clinical"]["presentingComplaint"])

    def test_atomic_create_rolls_back_all_resources_on_failure(self) -> None:
        from add_new_patient_backend.db import SQLiteAdapter
        from add_new_patient_backend.repository import PatientRepository

        with tempfile.TemporaryDirectory() as tempdir:
            db_path = str(Path(tempdir) / "rollback.sqlite3")
            adapter = SQLiteAdapter(db_path)
            repository = PatientRepository(adapter)
            repository.initialize()
            with adapter.connect() as conn:
                conn.execute(
                    """
                    CREATE TRIGGER reject_intake BEFORE INSERT ON patient_intake_records
                    BEGIN SELECT RAISE(ABORT, 'injected intake failure'); END
                    """
                )
            with self.assertRaises(sqlite3.IntegrityError):
                repository.create_patient_encounter_v2(
                    valid_v2_payload("ROLLBK"),
                    str(uuid4()),
                    "encounter-v2-rollback-0001",
                    "rollback-fingerprint",
                )
            with sqlite3.connect(db_path) as conn:
                for table in ("patients", "patient_code_aliases", "encounters", "patient_intake_records", "idempotency_records"):
                    self.assertEqual(conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0], 0)


class PatientEncounterV2MigrationTest(unittest.TestCase):
    def create_v1_fixture(self, db_path: str, codes: list[str] | None = None) -> tuple[str, str]:
        from add_new_patient_backend.db import INTAKE_TABLE_SQL, PATIENT_TABLE_SQL

        patient_id = str(uuid4())
        intake_id = str(uuid4())
        codes = codes or ["LEG001"]
        with sqlite3.connect(db_path) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute(PATIENT_TABLE_SQL)
            conn.execute(INTAKE_TABLE_SQL)
            for index, code in enumerate(codes):
                current_patient_id = patient_id if index == 0 else str(uuid4())
                conn.execute(
                    "INSERT INTO patients VALUES (?, ?, 'Legacy', 'Patient', 'Female', '1980-01-01', NULL, 'psy-1', ?, ?)",
                    (current_patient_id, code, "2026-07-01T09:00:00Z", "2026-07-01T09:00:00Z"),
                )
                if index == 0:
                    conn.execute(
                        """
                        INSERT INTO patient_intake_records VALUES
                          (?, ?, '2026-07-01T10:00:00Z', 'Legacy intake', 'F20.9', '[]', '[]', '[]',
                           'suicidality_none', 0, 'psy-1', '2026-07-01T10:00:00Z', '2026-07-01T10:00:00Z')
                        """,
                        (intake_id, patient_id),
                    )
        return patient_id, intake_id

    def test_migration_maps_intake_row_without_date_inference(self) -> None:
        from add_new_patient_backend.db import SQLiteAdapter

        with tempfile.TemporaryDirectory() as tempdir:
            db_path = str(Path(tempdir) / "v1.sqlite3")
            patient_id, intake_id = self.create_v1_fixture(db_path)
            SQLiteAdapter(db_path).initialize()
            with sqlite3.connect(db_path) as conn:
                conn.row_factory = sqlite3.Row
                encounter = conn.execute("SELECT * FROM encounters WHERE legacy_intake_id = ?", (intake_id,)).fetchone()
                snapshot = conn.execute("SELECT * FROM patient_intake_records WHERE id = ?", (intake_id,)).fetchone()
                alias = conn.execute("SELECT * FROM patient_code_aliases WHERE patient_id = ?", (patient_id,)).fetchone()
            self.assertIsNotNone(encounter)
            self.assertIsNotNone(alias)
            UUID(encounter["encounter_id"])
            self.assertNotEqual(encounter["encounter_id"], intake_id)
            self.assertEqual(snapshot["encounter_id"], encounter["encounter_id"])
            self.assertEqual(encounter["occurred_at"], "2026-07-01T10:00:00Z")
            with sqlite3.connect(db_path) as conn:
                migrations = conn.execute("SELECT version, name FROM schema_migrations ORDER BY version").fetchall()
            self.assertEqual(migrations, [(1, "patient-intake-v1"), (2, "patient-encounter-v2")])

    def test_fresh_database_applies_ordered_migrations(self) -> None:
        from add_new_patient_backend.db import LATEST_SCHEMA_VERSION, SQLiteAdapter

        with tempfile.TemporaryDirectory() as tempdir:
            db_path = str(Path(tempdir) / "fresh.sqlite3")
            adapter = SQLiteAdapter(db_path)
            adapter.initialize()
            adapter.initialize()
            with sqlite3.connect(db_path) as conn:
                versions = [row[0] for row in conn.execute("SELECT version FROM schema_migrations ORDER BY version")]
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
            self.assertEqual(versions, list(range(1, LATEST_SCHEMA_VERSION + 1)))
            self.assertTrue({"patients", "patient_code_aliases", "encounters", "patient_intake_records"}.issubset(tables))

    def test_migration_stops_on_case_insensitive_alias_collision(self) -> None:
        from add_new_patient_backend.db import SQLiteAdapter

        with tempfile.TemporaryDirectory() as tempdir:
            db_path = str(Path(tempdir) / "collision.sqlite3")
            self.create_v1_fixture(db_path, ["ABC123", "abc123"])
            with self.assertRaisesRegex(RuntimeError, "patient-code collision"):
                SQLiteAdapter(db_path).initialize()
            with sqlite3.connect(db_path) as conn:
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
                patient_count = conn.execute("SELECT COUNT(*) FROM patients").fetchone()[0]
            self.assertNotIn("patient_code_aliases", tables)
            self.assertNotIn("schema_migrations", tables)
            self.assertEqual(patient_count, 2)


if __name__ == "__main__":
    unittest.main()
