from __future__ import annotations

import json
import os
import socket
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener, urlopen
from uuid import UUID


PSY_HEADER = {"x-demo-auth-user": "psy-1"}
PSY_USER_ID = "11111111-1111-4111-8111-111111111111"
PSY_SESSION_ID = "22222222-2222-4222-8222-222222222222"
ADMIN_USER_ID = "33333333-3333-4333-8333-333333333333"
ADMIN_SESSION_ID = "44444444-4444-4444-8444-444444444444"


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class MockAuthenticationServer:
    def __init__(self) -> None:
        self.payloads: dict[str, tuple[int, dict]] = {}
        self.requests: list[dict[str, str]] = []

    def set_payload(self, session_id: str, payload: dict, status: int = 200) -> None:
        self.payloads[session_id] = (status, payload)

    def __enter__(self) -> "MockAuthenticationServer":
        owner = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                token = self.headers.get("x-auth-session") or self.headers.get("x-auth-session-id") or ""
                owner.requests.append({"path": self.path, "x-auth-session": token})
                status, payload = owner.payloads.get(token, (401, {"authenticated": False}))
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("content-type", "application/json")
                self.send_header("x-schema-version", "2.0.0")
                self.send_header("content-length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def log_message(self, *_: object) -> None:
                return

        self.port = free_port()
        self.server = ThreadingHTTPServer(("127.0.0.1", self.port), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.port}/api/auth/v2/session"
        return self

    def __exit__(self, *_: object) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


class AddNewPatientServer:
    def __init__(self, auth_session_url: str | None = None) -> None:
        self.auth_session_url = auth_session_url

    def __enter__(self) -> str:
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tempdir.name, "add_new_patient.sqlite3")
        os.environ["ADD_NEW_PATIENT_DB_PATH"] = self.db_path
        if self.auth_session_url:
            os.environ["AUTH_SESSION_URL"] = self.auth_session_url
            os.environ["ADD_NEW_PATIENT_MOCK_AUTH"] = "0"
        else:
            os.environ.pop("AUTH_SESSION_URL", None)
            os.environ.pop("ADD_NEW_PATIENT_MOCK_AUTH", None)
        os.environ.pop("AUTH_BASE_URL", None)
        for name in list(sys.modules):
            if name == "add_new_patient_backend" or name.startswith("add_new_patient_backend."):
                del sys.modules[name]

        import uvicorn
        from add_new_patient_backend.main import app

        self.port = free_port()
        self.config = uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="error")
        self.server = uvicorn.Server(self.config)
        self.thread = threading.Thread(target=self.server.run, daemon=True)
        self.thread.start()

        base = f"http://127.0.0.1:{self.port}"
        deadline = time.time() + 5
        while time.time() < deadline:
            try:
                request_json(base, "/api/health")
                return base
            except Exception:
                time.sleep(0.05)
        raise RuntimeError("server did not start")

    def __exit__(self, *_: object) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=5)
        self.tempdir.cleanup()


def request_json(
    base: str,
    path: str,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: dict | None = None,
) -> tuple[int, dict | None]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = Request(
        f"{base}{path}",
        data=data,
        method=method,
        headers={"content-type": "application/json", **(headers or {})},
    )
    try:
        with urlopen(req, timeout=5) as response:
            raw = response.read()
            try:
                return response.status, json.loads(raw) if raw else None
            except json.JSONDecodeError:
                return response.status, {"_raw": raw.decode("utf-8", errors="replace")}
    except HTTPError as error:
        try:
            payload = json.loads(error.read().decode("utf-8"))
        finally:
            if error.fp:
                error.fp.close()
            error.close()
        return error.code, payload


def csrf_headers(base: str, headers: dict[str, str] | None = None) -> dict[str, str]:
    req = Request(f"{base}/api/add-new-patient/csrf", method="GET")
    with urlopen(req, timeout=5) as response:
        payload = json.loads(response.read().decode("utf-8"))
        cookie = response.headers["set-cookie"].split(";", 1)[0]
    return {**(headers or {}), "cookie": cookie, "x-csrf-token": payload["csrfToken"]}


def valid_payload(**overrides: object) -> dict:
    payload = {
        "demographics": {
            "patientCode": "TEST01",
            "firstName": "Jane",
            "lastName": "Doe",
            "sex": "Female",
            "dob": dob_for_age(40),
            "phoneNumber": "5551234567",
        },
        "clinical": {
            "presentingComplaint": "Persistent low mood and insomnia.",
            "provisionalDiagnosis": "F32.1",
            "treatmentHistory": ["CBT in 2024"],
            "allergies": ["penicillin"],
            "currentMedications": ["sertraline 50 mg"],
            "riskFlags": {"suicidality": "ideation", "substanceUse": False},
        },
    }
    for key, value in overrides.items():
        if key in payload["demographics"]:
            payload["demographics"][key] = value
        elif key in payload["clinical"]:
            payload["clinical"][key] = value
        else:
            payload[key] = value
    return payload


def flat_payload(**overrides: object) -> dict:
    payload = {**valid_payload()["demographics"], **valid_payload()["clinical"]}
    payload.update(overrides)
    return payload


def dob_for_age(age: int) -> str:
    today = datetime.now(UTC).date()
    try:
        return today.replace(year=today.year - age).isoformat()
    except ValueError:
        return today.replace(year=today.year - age, day=28).isoformat()


def dob_days_ago(days: int) -> str:
    return (datetime.now(UTC).date() - timedelta(days=days)).isoformat()


def future_dob() -> str:
    return (datetime.now(UTC).date() + timedelta(days=1)).isoformat()


def future_iso() -> str:
    return (datetime.now(UTC) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")


def auth_payload(**overrides: dict) -> dict:
    payload = {
        "authenticated": True,
        "authorized": True,
        "interfaceVersion": "2.0.0",
        "session": {"id": PSY_SESSION_ID, "active": True, "expiresAt": future_iso()},
        "user": {"id": PSY_USER_ID, "username": "verified-clinician", "role": "psychiatrist"},
        "gates": {"passwordChangeRequired": False, "disclaimerRequired": False, "disclaimerVersion": "2026-07-06"},
        "compatibility": {"legacyUserId": 1, "legacyRole": "user"},
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(payload.get(key), dict):
            payload[key] = {**payload[key], **value}
        else:
            payload[key] = value
    return payload


class AuthIdentityNormalizationTest(unittest.TestCase):
    def test_normalize_accepts_psychiatrist_with_valid_session(self) -> None:
        from add_new_patient_backend.auth import normalize_auth_identity

        identity = normalize_auth_identity(auth_payload())
        assert identity is not None
        self.assertEqual(identity["authSessionId"], PSY_SESSION_ID)
        self.assertEqual(identity["user"]["id"], PSY_USER_ID)
        self.assertEqual(identity["user"]["role"], "psychiatrist")
        self.assertEqual(identity["user"]["username"], "verified-clinician")

    def test_normalize_authenticated_accepts_admin_but_psychiatrist_rejects_it(self) -> None:
        from add_new_patient_backend.auth import normalize_authenticated_session, normalize_psychiatrist_session

        payload = auth_payload(
            session={"id": ADMIN_SESSION_ID},
            user={"id": ADMIN_USER_ID, "username": "admin", "role": "admin"},
            compatibility={"legacyUserId": 2, "legacyRole": None},
        )
        self.assertIsNotNone(normalize_authenticated_session(payload))
        self.assertIsNone(normalize_psychiatrist_session(payload))

    def test_normalize_rejects_blocked_sessions(self) -> None:
        from add_new_patient_backend.auth import normalize_auth_identity

        blocked_payloads = [
            auth_payload(session=None),
            auth_payload(authenticated=False),
            auth_payload(authorized=False),
            auth_payload(interfaceVersion="1.0.0"),
            auth_payload(session={"active": False}),
            auth_payload(session={"expiresAt": "2000-01-01T00:00:00Z"}),
            auth_payload(session={"id": "not-a-uuid"}),
            auth_payload(user={"id": "not-a-uuid"}),
            auth_payload(user={"username": ""}),
            auth_payload(user={"role": "PSYCHIATRIST"}),
            auth_payload(gates={"passwordChangeRequired": True}),
            auth_payload(gates={"disclaimerRequired": True}),
            auth_payload(compatibility=None),
            auth_payload(compatibility={"legacyUserId": 0}),
        ]
        for payload in blocked_payloads:
            with self.subTest(payload=payload):
                self.assertIsNone(normalize_auth_identity(payload))

    def test_normalize_rejects_non_v2_schema_header(self) -> None:
        from add_new_patient_backend.auth import normalize_authenticated_session

        self.assertIsNone(normalize_authenticated_session(auth_payload(), "1.9.0"))
        self.assertIsNotNone(normalize_authenticated_session(auth_payload(), "2.4.0"))


class AddNewPatientBackendTest(unittest.TestCase):
    def test_health_endpoint(self) -> None:
        with AddNewPatientServer() as base:
            status, data = request_json(base, "/api/health")
            self.assertEqual(status, 200)
            self.assertEqual(data, {"module": "Add New Patient", "status": "ok"})
            self.assertEqual(request_json(base, "/healthz")[0], 200)
            self.assertEqual(request_json(base, "/readyz")[0], 503)

    def test_dashboard_module_route_contract(self) -> None:
        with AddNewPatientServer() as base:
            status, data = request_json(base, "/internal/dashboard/module-routes/add-new-patient")
            self.assertEqual(status, 200)
            self.assertEqual(
                data,
                {
                    "moduleId": "add-new-patient",
                    "title": "Add New Patient",
                    "href": "/modules/add-new-patient/",
                },
            )

    def test_create_patient_returns_201_with_full_record(self) -> None:
        with AddNewPatientServer() as base:
            status, data = request_json(base, "/api/patients", method="POST", headers=csrf_headers(base, PSY_HEADER), body=valid_payload())
            self.assertEqual(status, 201)
            patient = data["patient"]
            self.assertEqual(patient["patientCode"], "TEST01")
            self.assertEqual(patient["firstName"], "Jane")
            self.assertEqual(patient["lastName"], "Doe")
            self.assertEqual(patient["sex"], "Female")
            self.assertEqual(patient["dob"], valid_payload()["demographics"]["dob"])
            self.assertEqual(patient["age"], 40)
            self.assertEqual(patient["phoneNumber"], "5551234567")
            self.assertTrue(UUID(patient["createdByUserId"]))
            self.assertIn("intakeId", patient)
            self.assertIn("encounterDate", patient)
            self.assertEqual(patient["presentingComplaint"], "Persistent low mood and insomnia.")
            self.assertEqual(patient["provisionalDiagnosis"], "F32.1")
            self.assertEqual(patient["treatmentHistory"], ["CBT in 2024"])
            self.assertEqual(patient["allergies"], ["penicillin"])
            self.assertEqual(patient["currentMedications"], ["sertraline 50 mg"])
            self.assertEqual(patient["riskFlags"], {"suicidality": "ideation", "substanceUse": False})
            self.assertIn("id", patient)
            self.assertIn("createdAt", patient)
            self.assertIn("updatedAt", patient)

    def test_optional_intake_fields_default_safely(self) -> None:
        with AddNewPatientServer() as base:
            payload = valid_payload()
            for field in ["treatmentHistory", "allergies", "currentMedications", "riskFlags"]:
                payload["clinical"][field] = None
            status, data = request_json(base, "/api/patients", method="POST", headers=csrf_headers(base, PSY_HEADER), body=payload)
            self.assertEqual(status, 201)
            patient = data["patient"]
            self.assertEqual(patient["treatmentHistory"], [])
            self.assertEqual(patient["allergies"], [])
            self.assertEqual(patient["currentMedications"], [])
            self.assertEqual(patient["riskFlags"], {"suicidality": "suicidality_none", "substanceUse": False})

    def test_patient_identity_and_intake_record_persist_separately(self) -> None:
        server = AddNewPatientServer()
        with server as base:
            status, data = request_json(base, "/api/patients", method="POST", headers=csrf_headers(base, PSY_HEADER), body=valid_payload())
            self.assertEqual(status, 201)
            patient_id = data["patient"]["id"]

            conn = sqlite3.connect(server.db_path)
            conn.row_factory = sqlite3.Row
            try:
                patient_columns = {row["name"] for row in conn.execute("PRAGMA table_info(patients)").fetchall()}
                self.assertTrue({"id", "patient_code", "first_name", "last_name", "sex", "dob", "phone_number", "created_by_user_id", "created_at", "updated_at"}.issubset(patient_columns))
                self.assertNotIn("age", patient_columns)
                self.assertNotIn("presenting_complaint", patient_columns)
                self.assertNotIn("current_medications", patient_columns)

                patient = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
                self.assertTrue(UUID(patient["created_by_user_id"]))
                self.assertEqual(patient["dob"], valid_payload()["demographics"]["dob"])

                intakes = conn.execute("SELECT * FROM patient_intake_records WHERE patient_id = ?", (patient_id,)).fetchall()
                self.assertEqual(len(intakes), 1)
                self.assertEqual(intakes[0]["presenting_complaint"], "Persistent low mood and insomnia.")
                self.assertEqual(json.loads(intakes[0]["current_medications_snapshot"]), ["sertraline 50 mg"])
                self.assertTrue(UUID(intakes[0]["created_by_user_id"]))
            finally:
                conn.close()

    def test_list_patients_returns_all_persisted(self) -> None:
        with AddNewPatientServer() as base:
            request_json(base, "/api/patients", method="POST", headers=csrf_headers(base, PSY_HEADER), body=valid_payload(patientCode="LIST01"))
            request_json(base, "/api/patients", method="POST", headers=csrf_headers(base, PSY_HEADER), body=valid_payload(patientCode="LIST02"))
            status, data = request_json(base, "/api/patients", headers=PSY_HEADER)
            self.assertEqual(status, 200)
            codes = [patient["patientCode"] for patient in data["patients"]]
            self.assertEqual(sorted(codes), ["LIST01", "LIST02"])

    def test_get_patient_by_code_and_id(self) -> None:
        with AddNewPatientServer() as base:
            request_json(base, "/api/patients", method="POST", headers=csrf_headers(base, PSY_HEADER), body=valid_payload())
            _, created = request_json(base, "/api/patients", method="POST", headers=csrf_headers(base, PSY_HEADER), body=valid_payload(patientCode="GETIT1"))
            patient_id = created["patient"]["id"]
            status, by_code = request_json(base, "/api/patients/GETIT1", headers=PSY_HEADER)
            status_id, by_id = request_json(base, f"/api/patients/{patient_id}", headers=PSY_HEADER)
            self.assertEqual(status, 200)
            self.assertEqual(status_id, 200)
            self.assertEqual(by_code["patient"]["id"], patient_id)
            self.assertEqual(by_id["patient"]["patientCode"], "GETIT1")

    def test_get_patient_intake_returns_patient_and_records_newest_first(self) -> None:
        server = AddNewPatientServer()
        with server as base:
            create_headers = csrf_headers(base, PSY_HEADER)
            create_status, created = request_json(
                base,
                "/api/patients",
                method="POST",
                headers=create_headers,
                body=valid_payload(patientCode="INTK01"),
            )
            if create_status != 201:
                raise AssertionError(f"create failed: {create_status} {created}")
            patient_id = created["patient"]["id"]
            today_dt = datetime.fromisoformat(created["patient"]["encounterDate"].replace("Z", "+00:00"))
            yesterday_iso = (today_dt - timedelta(days=1)).isoformat().replace("+00:00", "Z")
            last_year_iso = (today_dt - timedelta(days=365)).isoformat().replace("+00:00", "Z")

            conn = sqlite3.connect(server.db_path)
            conn.row_factory = sqlite3.Row
            try:
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
                        "intake-older",
                        patient_id,
                        last_year_iso,
                        "Earlier episode.",
                        "F33.1",
                        "[]",
                        "[]",
                        "[]",
                        "ideation",
                        1,
                        PSY_USER_ID,
                        last_year_iso,
                        last_year_iso,
                    ),
                )
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
                        "intake-mid",
                        patient_id,
                        yesterday_iso,
                        "Mid episode.",
                        "F33.1",
                        "[]",
                        "[]",
                        "[]",
                        "suicidality_none",
                        0,
                        PSY_USER_ID,
                        yesterday_iso,
                        yesterday_iso,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            status, data = request_json(base, f"/api/patients/{patient_id}/intake", headers=PSY_HEADER)
            self.assertEqual(status, 200)
            self.assertEqual(data["patient"]["id"], patient_id)
            self.assertEqual(data["patient"]["patientCode"], "INTK01")
            self.assertEqual(len(data["intakeRecords"]), 3)
            self.assertEqual(
                [record["id"] for record in data["intakeRecords"]],
                [created["patient"]["intakeId"], "intake-mid", "intake-older"],
            )
            self.assertEqual(data["intakeRecords"][0]["encounterDate"], created["patient"]["encounterDate"])
            self.assertEqual(data["intakeRecords"][1]["encounterDate"], yesterday_iso)
            self.assertEqual(data["intakeRecords"][2]["encounterDate"], last_year_iso)
            for record in data["intakeRecords"]:
                self.assertIn("id", record)
                self.assertIn("patientId", record)
                self.assertIn("encounterDate", record)
                self.assertIn("presentingComplaint", record)
                self.assertIn("provisionalDiagnosis", record)
                self.assertIn("treatmentHistory", record)
                self.assertIn("allergies", record)
                self.assertIn("currentMedications", record)
                self.assertIn("riskFlags", record)
                self.assertIn("createdByUserId", record)
                self.assertIn("createdAt", record)
                self.assertIn("updatedAt", record)

            status_code, by_code = request_json(base, "/api/patients/INTK01/intake", headers=PSY_HEADER)
            self.assertEqual(status_code, 200)
            self.assertEqual(by_code["patient"]["id"], patient_id)
            self.assertEqual(len(by_code["intakeRecords"]), 3)

            _ = server.db_path

            missing_status, missing_data = request_json(base, "/api/patients/MISSING/intake", headers=PSY_HEADER)
            self.assertEqual(missing_status, 404)
            self.assertEqual(missing_data, {"message": "Patient was not found."})

    def test_get_patient_intake_accepts_admin_role(self) -> None:
        with MockAuthenticationServer() as mock_auth:
            mock_auth.set_payload("psy-sess", auth_payload())
            mock_auth.set_payload(
                "admin-sess",
                auth_payload(session={"id": ADMIN_SESSION_ID}, user={"id": ADMIN_USER_ID, "username": "admin", "role": "admin"}),
            )
            with AddNewPatientServer(auth_session_url=mock_auth.url) as base:
                create_status, _ = request_json(
                    base,
                    "/api/patients",
                    method="POST",
                    headers=csrf_headers(base, {"x-auth-session": "psy-sess"}),
                    body=valid_payload(),
                )
                if create_status != 201:
                    raise AssertionError(f"seed create failed: {create_status}")
                status, data = request_json(
                    base,
                    "/api/patients/TEST01/intake",
                    headers={"x-auth-session": "admin-sess"},
                )
                self.assertEqual(status, 200)
                self.assertEqual(data["patient"]["patientCode"], "TEST01")
                self.assertEqual(len(data["intakeRecords"]), 1)

    def test_get_patient_intake_rejects_unknown_role(self) -> None:
        with MockAuthenticationServer() as mock_auth:
            mock_auth.set_payload("psy-sess", auth_payload())
            mock_auth.set_payload(
                "nurse-sess",
                auth_payload(user={"id": str(UUID("55555555-5555-4555-8555-555555555555")), "username": "nurse", "role": "nurse"}),
            )
            with AddNewPatientServer(auth_session_url=mock_auth.url) as base:
                create_status, _ = request_json(
                    base,
                    "/api/patients",
                    method="POST",
                    headers=csrf_headers(base, {"x-auth-session": "psy-sess"}),
                    body=valid_payload(),
                )
                if create_status != 201:
                    raise AssertionError(f"seed create failed: {create_status}")
                status, data = request_json(
                    base,
                    "/api/patients/TEST01/intake",
                    headers={"x-auth-session": "nurse-sess"},
                )
                self.assertEqual(status, 401)
                self.assertEqual(data, {"error": "authentication_session_required"})

    def test_get_patient_intake_rejects_unauthenticated(self) -> None:
        with AddNewPatientServer() as base:
            status, data = request_json(base, "/api/patients/ANY/intake")
            self.assertEqual(status, 401)
            self.assertEqual(data, {"error": "authentication_session_required"})

    def test_missing_patient_returns_404(self) -> None:
        with AddNewPatientServer() as base:
            status, data = request_json(base, "/api/patients/MISSING", headers=PSY_HEADER)
            self.assertEqual(status, 404)
            self.assertEqual(data, {"message": "Patient was not found."})

    def test_duplicate_patient_code_rejected_422(self) -> None:
        with AddNewPatientServer() as base:
            request_json(base, "/api/patients", method="POST", headers=csrf_headers(base, PSY_HEADER), body=valid_payload())
            status, data = request_json(base, "/api/patients", method="POST", headers=csrf_headers(base, PSY_HEADER), body=valid_payload())
            self.assertEqual(status, 422)
            self.assertEqual(data["message"], "Patient data failed validation.")
            self.assertIn("Patient code already exists", data["errors"]["demographics.patientCode"])

    def test_missing_patient_code_generates_server_side(self) -> None:
        with AddNewPatientServer() as base:
            status, data = request_json(
                base,
                "/api/patients",
                method="POST",
                headers=csrf_headers(base, PSY_HEADER),
                body=valid_payload(patientCode=None),
            )
            self.assertEqual(status, 201)
            self.assertRegex(data["patient"]["patientCode"], r"^[A-Z0-9]{6}$")

    def test_dob_rejects_future_date(self) -> None:
        with AddNewPatientServer() as base:
            status, data = request_json(base, "/api/patients", method="POST", headers=csrf_headers(base, PSY_HEADER), body=valid_payload(dob=future_dob()))
            self.assertEqual(status, 422)
            self.assertIn("demographics.dob", data["errors"])

    def test_dob_rejects_patient_younger_than_one_year(self) -> None:
        with AddNewPatientServer() as base:
            status, data = request_json(base, "/api/patients", method="POST", headers=csrf_headers(base, PSY_HEADER), body=valid_payload(dob=dob_days_ago(364)))
            self.assertEqual(status, 422)
            self.assertIn("demographics.dob", data["errors"])

    def test_old_dob_is_accepted_and_age_is_computed(self) -> None:
        with AddNewPatientServer() as base:
            status, data = request_json(base, "/api/patients", method="POST", headers=csrf_headers(base, PSY_HEADER), body=valid_payload(dob=dob_for_age(111)))
            self.assertEqual(status, 201)
            self.assertEqual(data["patient"]["dob"], dob_for_age(111))
            self.assertEqual(data["patient"]["age"], 111)

    def test_invalid_sex_rejected(self) -> None:
        with AddNewPatientServer() as base:
            status, data = request_json(base, "/api/patients", method="POST", headers=csrf_headers(base, PSY_HEADER), body=valid_payload(sex="Other"))
            self.assertEqual(status, 422)
            self.assertIn("demographics.sex", data["errors"])

    def test_long_name_rejected(self) -> None:
        with AddNewPatientServer() as base:
            status, data = request_json(
                base,
                "/api/patients",
                method="POST",
                headers=csrf_headers(base, PSY_HEADER),
                body=valid_payload(firstName="x" * 81),
            )
            self.assertEqual(status, 422)
            self.assertIn("demographics.firstName", data["errors"])

    def test_phone_normalization_strips_non_digits(self) -> None:
        with AddNewPatientServer() as base:
            status, data = request_json(
                base,
                "/api/patients",
                method="POST",
                headers=csrf_headers(base, PSY_HEADER),
                body=valid_payload(patientCode="PHN001", phoneNumber="(555) 123-4567"),
            )
            self.assertEqual(status, 201)
            self.assertEqual(data["patient"]["phoneNumber"], "5551234567")

    def test_missing_required_clinical_intake_rejected(self) -> None:
        with AddNewPatientServer() as base:
            status, data = request_json(
                base,
                "/api/patients",
                method="POST",
                headers=csrf_headers(base, PSY_HEADER),
                body=valid_payload(presentingComplaint="", provisionalDiagnosis=""),
            )
            self.assertEqual(status, 422)
            self.assertIn("clinical.presentingComplaint", data["errors"])
            self.assertIn("clinical.provisionalDiagnosis", data["errors"])

    def test_flat_payload_is_validated_with_section_error_keys(self) -> None:
        with AddNewPatientServer() as base:
            status, data = request_json(
                base,
                "/api/patients",
                method="POST",
                headers=csrf_headers(base, PSY_HEADER),
                body=flat_payload(dob=future_dob(), provisionalDiagnosis=""),
            )
            self.assertEqual(status, 422)
            self.assertIn("demographics.dob", data["errors"])
            self.assertIn("clinical.provisionalDiagnosis", data["errors"])

    def test_static_assets_served_only_from_allowlist(self) -> None:
        with AddNewPatientServer() as base:
            self.assertEqual(request_json(base, "/")[0], 200)
            self.assertEqual(request_json(base, "/app.js")[0], 200)
            self.assertEqual(request_json(base, "/styles.css")[0], 200)

    def test_dashboard_embedded_module_path_serves_shell_and_assets(self) -> None:
        with AddNewPatientServer() as base:
            class NoRedirect(HTTPRedirectHandler):
                def redirect_request(self, *_: object, **__: object) -> None:
                    return None

            with self.assertRaises(HTTPError) as redirect:
                build_opener(NoRedirect).open(f"{base}/modules/add-new-patient", timeout=5)
            self.assertEqual(redirect.exception.code, 308)
            self.assertEqual(redirect.exception.headers["Location"], "/modules/add-new-patient/")

            status, data = request_json(base, "/modules/add-new-patient")
            self.assertEqual(status, 200)
            self.assertIn('data-module="add-new-patient"', data["_raw"])

            self.assertEqual(request_json(base, "/modules/app.js")[0], 200)
            self.assertEqual(request_json(base, "/modules/styles.css")[0], 200)
            self.assertEqual(request_json(base, "/modules/add-new-patient/app.js")[0], 200)
            self.assertEqual(request_json(base, "/modules/add-new-patient/styles.css")[0], 200)

    def test_private_paths_not_served(self) -> None:
        with AddNewPatientServer() as base:
            for path in [
                "/data/patients.json",
                "/server.py",
                "/schema/add-new-patient.schema.json",
                "/add_new_patient_backend/main.py",
                "/requirements.txt",
                "/modules/server.py",
                "/modules/add-new-patient/server.py",
            ]:
                with self.subTest(path=path):
                    status, _ = request_json(base, path)
                    self.assertEqual(status, 404)


class AuthBoundaryTest(unittest.TestCase):
    def test_patients_endpoints_reject_unauthenticated(self) -> None:
        with AddNewPatientServer() as base:
            for path in ["/api/patients", "/api/patients/ANY"]:
                with self.subTest(path=path):
                    status, data = request_json(base, path)
                    self.assertEqual(status, 401)
                    self.assertEqual(data, {"error": "authentication_session_required"})
            status, data = request_json(
                base,
                "/api/patients",
                method="POST",
                headers=csrf_headers(base),
                body=valid_payload(),
            )
            self.assertEqual(status, 401)
            self.assertEqual(data, {"error": "authentication_session_required"})

    def test_csrf_endpoint_issues_cookie_and_token(self) -> None:
        with AddNewPatientServer() as base:
            headers = csrf_headers(base, PSY_HEADER)
            self.assertIn("add_new_patient_csrf=", headers["cookie"])
            self.assertTrue(headers["x-csrf-token"])

    def test_write_rejects_missing_csrf(self) -> None:
        with AddNewPatientServer() as base:
            status, data = request_json(base, "/api/patients", method="POST", headers=PSY_HEADER, body=valid_payload())
            self.assertEqual(status, 403)
            self.assertEqual(data, {"error": "csrf_token_invalid"})

    def test_write_rejects_mismatched_csrf(self) -> None:
        with AddNewPatientServer() as base:
            headers = csrf_headers(base, PSY_HEADER)
            headers["x-csrf-token"] = "wrong-token"
            status, data = request_json(base, "/api/patients", method="POST", headers=headers, body=valid_payload())
            self.assertEqual(status, 403)
            self.assertEqual(data, {"error": "csrf_token_invalid"})

    def test_write_rejects_tampered_csrf_cookie(self) -> None:
        with AddNewPatientServer() as base:
            headers = csrf_headers(base, PSY_HEADER)
            headers["cookie"] = f"add_new_patient_csrf={headers['x-csrf-token']}.bad-signature"
            status, data = request_json(base, "/api/patients", method="POST", headers=headers, body=valid_payload())
            self.assertEqual(status, 403)
            self.assertEqual(data, {"error": "csrf_token_invalid"})

    def test_mock_auth_session_resolves_demo_user(self) -> None:
        with AddNewPatientServer() as base:
            status, data = request_json(base, "/api/auth/v2/session", headers=PSY_HEADER)
            self.assertEqual(status, 200)
            self.assertTrue(data["authenticated"])
            self.assertTrue(UUID(data["user"]["id"]))
            self.assertTrue(UUID(data["session"]["id"]))
            self.assertEqual(data["user"]["role"], "psychiatrist")
            self.assertTrue(data["authorized"])

    def test_mock_auth_session_404_when_mock_disabled(self) -> None:
        with MockAuthenticationServer() as mock_auth:
            with AddNewPatientServer(auth_session_url=mock_auth.url) as base:
                status, data = request_json(base, "/api/auth/v2/session")
                self.assertEqual(status, 404)
                self.assertEqual(data, {"error": "not_found"})

    def test_real_auth_session_returns_401_when_unknown_session(self) -> None:
        with MockAuthenticationServer() as mock_auth:
            with AddNewPatientServer(auth_session_url=mock_auth.url) as base:
                status, data = request_json(base, "/api/patients", headers={"x-auth-session": "unknown"})
                self.assertEqual(status, 401)
                self.assertEqual(data, {"error": "authentication_session_required"})

    def test_real_auth_session_accepts_verified_psychiatrist(self) -> None:
        with MockAuthenticationServer() as mock_auth:
            mock_auth.set_payload("auth-1", auth_payload())
            with AddNewPatientServer(auth_session_url=mock_auth.url) as base:
                status, data = request_json(
                    base,
                    "/api/patients",
                    method="POST",
                    headers=csrf_headers(base, {"x-auth-session": "auth-1"}),
                    body=valid_payload(),
                )
                self.assertEqual(status, 201)
                self.assertEqual(data["patient"]["patientCode"], "TEST01")
                self.assertEqual(mock_auth.requests[0]["path"], "/api/auth/v2/session")
                self.assertEqual(mock_auth.requests[0]["x-auth-session"], "auth-1")

    def test_real_auth_session_rejects_admin_role(self) -> None:
        with MockAuthenticationServer() as mock_auth:
            mock_auth.set_payload(
                "admin-sess",
                auth_payload(session={"id": ADMIN_SESSION_ID}, user={"id": ADMIN_USER_ID, "username": "admin", "role": "admin"}),
            )
            with AddNewPatientServer(auth_session_url=mock_auth.url) as base:
                status, data = request_json(
                    base,
                    "/api/patients",
                    method="POST",
                    headers=csrf_headers(base, {"x-auth-session": "admin-sess"}),
                    body=valid_payload(),
                )
                self.assertEqual(status, 401)
                self.assertEqual(data, {"error": "authentication_session_required"})

    def test_real_auth_session_accepts_admin_on_read_endpoints(self) -> None:
        with MockAuthenticationServer() as mock_auth:
            mock_auth.set_payload(
                "admin-sess",
                auth_payload(session={"id": ADMIN_SESSION_ID}, user={"id": ADMIN_USER_ID, "username": "admin", "role": "admin"}),
            )
            with AddNewPatientServer(auth_session_url=mock_auth.url) as base:
                status, data = request_json(base, "/api/patients", headers={"x-auth-session": "admin-sess"})
                self.assertEqual(status, 200)
                self.assertEqual(data, {"patients": []})

                status, data = request_json(base, "/api/patients/MISSING", headers={"x-auth-session": "admin-sess"})
                self.assertEqual(status, 404)
                self.assertEqual(data, {"message": "Patient was not found."})

    def test_blocked_disclaimer_status_rejected(self) -> None:
        with MockAuthenticationServer() as mock_auth:
            mock_auth.set_payload("auth-blocked", auth_payload(authorized=False, gates={"disclaimerRequired": True}))
            with AddNewPatientServer(auth_session_url=mock_auth.url) as base:
                status, data = request_json(
                    base,
                    "/api/patients",
                    headers={"x-auth-session": "auth-blocked"},
                )
                self.assertEqual(status, 401)
                self.assertEqual(data, {"error": "authentication_session_required"})

    def test_auth_session_unavailable_returns_502(self) -> None:
        # ponytail: point at a port nobody owns -> connection refused -> AuthSessionError -> 502
        with AddNewPatientServer(auth_session_url="http://127.0.0.1:1/api/auth/v2/session") as base:
            status, data = request_json(base, "/api/patients", headers={"x-auth-session": "auth-1"})
            self.assertEqual(status, 502)
            self.assertEqual(data["error"], "authentication_session_unavailable")


class ConcurrencyTest(unittest.TestCase):
    def test_concurrent_patient_creation_preserves_all(self) -> None:
        import concurrent.futures

        with AddNewPatientServer() as base:
            codes = [f"C{i:05d}" for i in range(10)]
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
                futures = [
                    pool.submit(
                        request_json,
                        base,
                        "/api/patients",
                        "POST",
                        csrf_headers(base, PSY_HEADER),
                        valid_payload(patientCode=code),
                    )
                    for code in codes
                ]
                results = [future.result() for future in futures]
            self.assertEqual([status for status, _ in results], [201] * 10)
            _, data = request_json(base, "/api/patients", headers=PSY_HEADER)
            stored = sorted(patient["patientCode"] for patient in data["patients"])
            self.assertEqual(stored, sorted(codes))


if __name__ == "__main__":
    unittest.main()
