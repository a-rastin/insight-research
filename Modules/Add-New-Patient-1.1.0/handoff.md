# Repository Handoff — Add New Patient Module

Last updated: 2026-07-29

Pointers to the long-form documentation live in `docs/`. This file is the
short entry-point for an agent or maintainer who just opened the repo.

## What this repo is

A standalone patient-intake module. Python FastAPI backend, vanilla HTML/CSS/JS
frontend, SQLite persistence. Designed to run on its own from this repo **or**
to be embedded by a Dashboard host that supplies the same markup and optionally
points the browser module at a different internal API base URL.

Core architectural rule — **preserved across all rework so far**:

> The browser UI communicates with the module only through REST endpoints. It
> does not touch SQLite or any private file. The server does not serve
> `add_new_patient.sqlite3`, source files, or anything outside its explicit
> static allowlist.

## Layout

```text
add_new_patient_backend/
  __init__.py        package docstring
  config.py          Settings (port, db_path, auth URLs, CSRF secret, mock-auth flag)
  db.py              SCHEMA + per-table SQL + DatabaseAdapter Protocol + SQLiteAdapter + legacy migration
  repository.py      PatientRepository (list/get/create + intake history) + helpers
  models.py          Pydantic v2 contract: PatientIntake, PatientDemographics, ClinicalSection, ClinicalFlag, generate_patient_code
  csrf.py            CSRF cookie + token sign/verify + write-method gate
  auth.py            AuthSessionError + session normalizers + fetch_auth_identity
  main.py            FastAPI app, REST handlers, auth dependencies, mock /api/auth/v2/session, CSRF middleware, static allowlist
server.py            from add_new_patient_backend.main import app
requirements.txt     fastapi, uvicorn, pydantic
index.html           standalone page (also served at /modules/add-new-patient)
app.js               browser module — createAddNewPatientModule({root, apiBaseUrl})
styles.css           visual styling — design system documented in DESIGN.md
DESIGN.md            Carbon Health design language (color, type, motion, a11y)
schema/
  add-new-patient.schema.json   integration documentation only — NOT executed at runtime
  patient-encounter-v2.schema.json   Draft 2020-12 v2 resource contract
  patient-encounter-v2.openapi.json  OpenAPI 3.1 v2 API contract
docs/
  add-new-patient-handoff.md    long-form architecture + invariants + verification
  api-contract.md               REST contract in detail
  patient-domain-glossary.md    patient domain rules
data/                reserved (no files)
test_add_new_patient_backend.py   unittest suite (uvicorn in a thread)
test_encounter_v2_contracts.py    v2 contract, migration, concurrency suite
test_frontend.mjs                node:test smoke tests for index.html
```

## How to run

```powershell
pip install -r requirements.txt
uvicorn add_new_patient_backend.main:app --port 4173
# or
uvicorn server:app --port 4173
```

Open `http://localhost:4173`.

Override the SQLite path with `ADD_NEW_PATIENT_DB_PATH`. Override the port with
`PORT` or `--port`. Disable the in-memory mock auth in production deployments
by setting `AUTH_BASE_URL` (or `AUTH_SESSION_URL`) and
`ADD_NEW_PATIENT_MOCK_AUTH=0`.

## Tests

```powershell
python -m unittest test_add_new_patient_backend.py
python -m unittest test_encounter_v2_contracts.py
node --test test_frontend.mjs        # optional, HTML smoke only
```

## REST endpoints

| Method | Path                                                              | Auth                                |
|--------|-------------------------------------------------------------------|-------------------------------------|
| GET    | `/api/health`                                                      | none                                |
| GET    | `/internal/dashboard/module-routes/add-new-patient`              | none (Dashboard discovery)          |
| GET    | `/api/auth/v2/session`                                             | none (mock-auth only when enabled)  |
| GET    | `/api/add-new-patient/csrf`                                        | none                                |
| GET    | `/api/patients`                                                    | `require_authenticated_session`     |
| GET    | `/api/patients/{idOrCode}`                                         | `require_authenticated_session`     |
| GET    | `/api/patients/{idOrCode}/intake`                                  | `require_psychiatrist_or_admin_session` |
| POST   | `/api/patients`                                                    | `require_psychiatrist_session` + CSRF |

CSRF middleware (`main.py`) rejects `POST`/`PATCH` requests missing a valid
`X-CSRF-Token` header that matches the signed `add_new_patient_csrf` cookie.

## Patient identifier contract (F1.1)

Cross-module references pin to **either**:

- `id` — server-generated UUID, immutable, canonical for Follow-up module writes
- `patientCode` — 6 chars from `ABCDEFGHJKLMNPQRSTUVWXYZ23456789`,
  server-generated when absent, case-insensitive, `UNIQUE` in SQLite

`GET /api/patients/{idOrCode}` resolves UUID first, then
`UPPER(patient_code)`. `/intake` adds encounter history (newest first).

V2 removes aliases from integration URLs. Patient and Encounter use independent
UUIDs; exact patient-code resolution is body-based at
`POST /api/add-new-patient/v2/patient-code-aliases/resolve`. Existing v1 intake
rows migrate one-to-one to explicit Encounter UUIDs through `legacyIntakeId`,
without grouping by encounter dates.

## Request payload shape

`POST /api/patients` accepts **both** shapes today (legacy flat and nested):

```json
{
  "demographics": {...},
  "clinical": {...}
}
```

See `models.py:PatientIntake.accept_legacy_flat_payload`. The flat shape still
works because the form was that way before Pydantic was introduced. New code
should use the nested shape.

## Current invariants (do not break)

1. UI talks to the module only through `/api/*` + CSRF.
2. `add_new_patient.sqlite3`, source files, and `/data/` are never served as
   static assets — see the allowlist in `main.py:PUBLIC_FILES` and
   `EMBEDDED_ASSET_PATHS`.
3. Pydantic `PatientIntake` is the runtime contract source. The schema JSON
   file is documentation only.
4. Reads need an authorized v2 `psychiatrist` or `admin` session; writes need
   `psychiatrist`. Intake history permits `psychiatrist` or `admin`.
5. The module never decodes JWT and never reads the auth DB — identity comes
   only from upstream `GET /api/auth/v2/session`.
6. Mock auth is a standalone-dev fallback, gated by env. Production must set
   an auth URL and `ADD_NEW_PATIENT_MOCK_AUTH=0`.
7. CSRF token required on all write methods.
8. Test data must not linger in the SQLite file.

## Known limitations (not bugs)

- No pagination on `GET /api/patients`.
- No `PUT/PATCH/DELETE` endpoints.
- SQLite single-process safe; multi-process needs a stronger adapter.
- No server-side request logging.

## Recent additions visible in current code but not in older docs

- **CSRF** (`csrf.py`, middleware + `GET /api/add-new-patient/csrf`,
  `app.js` calls it via `getCsrfToken`).
- **Intake records** — second table `patient_intake_records` storing each
  encounter separately; patient joins to the latest intake in `repository.py`.
  Handled by `models.ClinicalSection` (encounter date, presenting complaint,
  provisional diagnosis, list fields, risk flags).
- **Legacy data migration** in `db.py:migrate_patients_to_identity_table`
  splits the old denormalized `patients` row into the new identity table plus
  an initial intake row.
- **`require_psychiatrist_or_admin_session`** plus the new
  `GET /api/patients/{idOrCode}/intake` endpoint for the Follow-up module.
- **Pydantic contract** accepts both nested and flat payloads.

## Where to look first

1. `DESIGN.md` — what the UI is meant to feel like.
2. `docs/add-new-patient-handoff.md` — full architecture + invariants + how to
   extend fields.
3. `docs/api-contract.md` — REST contract in detail.
4. `docs/patient-domain-glossary.md` — patient domain semantics.
5. `add_new_patient_backend/main.py` — wiring (routes, auth deps, CSRF, static
   allowlist, exception handlers).
6. `add_new_patient_backend/models.py` — runtime contract.
7. `add_new_patient_backend/repository.py` — SQL shape and row mapping.
8. `app.js` + `index.html` — browser lifecycle, embed contract.

## Verification shortcuts

```text
GET  /api/health                              -> 200
GET  /                                         -> 200 (index.html)
GET  /app.js                                   -> 200
GET  /styles.css                               -> 200
GET  /data/patients.json                       -> 404
GET  /server.py                                -> 404
GET  /add_new_patient.sqlite3                  -> 404
GET  /api/patients (no session)                -> 401 authentication_session_required
POST /api/patients valid body + psy session    -> 201 with X-CSRF-Token round-tripped
POST /api/patients no csrf                     -> 403 csrf_token_invalid
POST /api/patients duplicate code              -> 422
GET  /api/patients/{patientCode} + session     -> 200
GET  /api/patients/{idOrCode}/intake + psy     -> 200 with intakeRecords[]
```

Do not leave test patients in `add_new_patient.sqlite3`.
