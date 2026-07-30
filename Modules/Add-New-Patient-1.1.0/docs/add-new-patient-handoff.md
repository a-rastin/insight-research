# Add New Patient Module Handoff

Last updated: 2026-07-07

This document is for future LLMs or maintainers who need to understand, extend,
test, or embed the Add New Patient module. It describes the current
architecture after the A0.1 module-level rebuild (Node `server.js` -> Python
FastAPI).

## Purpose

The Add New Patient module is a standalone patient intake slice. It renders a
small browser UI for entering patient details and persists records through an
internal REST interface backed by SQLite. It can run by itself from this
repository, or be embedded by a host app that provides the expected markup and
optionally points the browser module at a different internal API base URL.

The key architectural rule is:

The browser UI must communicate through REST endpoints only. It must not read
or write the SQLite database directly, and the server must not expose the
database file or any source file as a static asset.

## Stack

- Python 3.13+ backend on FastAPI + uvicorn + Pydantic.
- Pydantic models in `models.py` are the single runtime contract source.
- SQLite storage via a small inlined adapter in `repository.py`.
- No Node runtime dependency remains. Frontend is plain HTML/CSS/JS.

## Package Layout

Mirrors the Dashboard backend layout so both modules share Docker base images,
contract patterns, and unittest suite shape.

```
add_new_patient_backend/
  __init__.py        package docstring
  config.py          Settings (port, db_path, auth URLs + mock)
  db.py              SCHEMA + DatabaseAdapter Protocol
  repository.py      SQLiteAdapter + PatientRepository + now_iso + patient_row
  models.py          PatientCreate Pydantic model + generate_patient_code
  auth.py            AuthSessionError + session normalizers + fetch_auth_identity
  main.py            FastAPI app + REST handlers + auth dependencies + static allowlist
server.py            from add_new_patient_backend.main import app
requirements.txt     fastapi, uvicorn, pydantic
test_add_new_patient_backend.py   unittest suite (uvicorn server-in-thread)
```

## Auth seam (B1.1)

The module does not decode JWT and does not read the auth DB. Patient REST
endpoints verify inline on every request by forwarding caller auth headers
(`Authorization`, `Cookie`, `X-Auth-Session`, `X-Auth-Session-Id`) to
`GET /api/auth/session`. There is no local session table because Add New
Patient has no Dashboard shell workspace state.

Read endpoints (`GET /api/patients`, `GET /api/patients/{idOrCode}`) use
`require_authenticated_session`. Mutating endpoints (`POST /api/patients`) use
`require_psychiatrist_session`.

Rejected session shapes (return `None` → HTTP 401
`authentication_session_required`):

- `authenticated: false`
- session `active: false`
- status in `BLOCKED_AUTH_STATUSES` (expired / force_password_change /
  disclaimer_blocked / disclaimer_required / ...)
- truthy `expired` / `isExpired` flag
- `expiresAt` in the past
- truthy `forcePasswordChange*` / `mustChangePassword` / `passwordResetRequired`
- truthy `disclaimerBlocked*` / `disclaimerRequired*` / `requiresDisclaimer*`
- missing user id

`require_psychiatrist_session` also rejects sessions whose user role is not
`PSYCHIATRIST`. `require_authenticated_session` does not apply role gating.

`AuthSessionError` (network failure, non-401/403 upstream status) is mapped to
HTTP 502 `authentication_session_unavailable`. Upstream 401/403 is mapped to
HTTP 401 `authentication_session_required` (return `None` from
`fetch_auth_identity`).

Outbound auth request timeout: `AUTH_SESSION_TIMEOUT_MS` env var, default
`2000` ms.

Config env (read once at process start in `config.py`):

- `AUTH_SESSION_URL` — full URL to `GET /api/auth/session` (highest priority)
- `AUTH_BASE_URL` — base; `<AUTH_BASE_URL>/api/auth/session` is used
- `ADD_NEW_PATIENT_MOCK_AUTH` — `1` forces mock auth on, `0` forces it off.
  When neither `AUTH_SESSION_URL` nor `AUTH_BASE_URL` is set, mock auth is on
  unless `ADD_NEW_PATIENT_MOCK_AUTH=0`. In mock mode, `GET /api/auth/session`
  is served in-process by `main.py`, keyed off `X-Demo-Auth-User` (`psy-1`
  psychiatrist "Mina Rahimi"). Mock state is in-memory
  (`MOCK_AUTH_SESSIONS` dict) — never persisted.

Integrated deployments set `AUTH_BASE_URL` or `AUTH_SESSION_URL` and
`ADD_NEW_PATIENT_MOCK_AUTH=0`.

## Runtime Model

Run the server:

```powershell
uvicorn add_new_patient_backend.main:app --port 4173
```

Default port: `4173`. Override with `--port` or the `PORT` env var. The SQLite
path defaults to `add_new_patient.sqlite3` in the repo root and can be
overridden with the `ADD_NEW_PATIENT_DB_PATH` environment variable.

There is no Node runtime and no `npm`. Dependencies live in `requirements.txt`.

## File Map

### `index.html`

Owns the standalone page markup. It includes:

- Dashboard view: `#dashboardView`
- Patient form view: `#patientView`
- Activation button: `#activateModuleButton`
- Back button: `#backButton`
- Form: `#patientForm`
- Generated code output: `#patientCode`
- Regenerate button: `#regenerateCodeButton`
- Status message: `#statusMessage`
- Field error slots using `data-error-for`

The browser module in `app.js` expects these IDs to exist under its configured
root. If any required element is missing, module initialization throws an
explicit error.

### `styles.css`

Owns standalone visual styling. It does not participate in application logic.

### `app.js`

Owns browser-side lifecycle and interaction flow. It no longer imports a
shared contract module — the FastAPI backend and Pydantic are the contract
source.

Important exported/browser-visible interfaces:

```js
window.createAddNewPatientModule(options)
window.AddNewPatientModule
```

`createAddNewPatientModule` accepts:

```js
{
  root: document,      // or a container element
  apiBaseUrl: ""       // optional REST base URL, without or with trailing slash
}
```

It returns:

```js
{
  activate(),
  back(),
  generateCode(),
  destroy()
}
```

Client-side validation is intentionally minimal. It duplicates only the
obvious rules (required names, sex value, DOB not future and at least 1 year ago,
10-digit phone) to give
immediate UX feedback. Server-side Pydantic validation is the source of truth;
any divergence is a bug to fix in `models.py` first. If a field rule changes,
update `models.py` and `app.js` together — but `models.py` is canonical.

The browser submit flow:

1. Prevents the native form submit.
2. Clears previous field errors.
3. Builds a normalized payload from `FormData`.
4. Validates with the minimal inline `validatePatientPayload`.
5. If invalid, renders field errors and sets the status message to
   `Review the highlighted fields.`
6. If valid, posts JSON to `${apiBaseUrl}/api/patients`.
7. Parses JSON defensively; invalid JSON becomes `{}`.
8. Handles non-2xx responses as normal validation or save failures.
9. Catches network failures and shows
   `Patient could not be saved. Check your connection and try again.`
10. On success, resets the form, generates a fresh patient code, and focuses
    the first name field.

### `add_new_patient_backend/config.py`

Owns runtime settings. Reads env vars at instantiation time:

- `PORT` (default `4173`)
- `ADD_NEW_PATIENT_DB_PATH` (default `<repo>/add_new_patient.sqlite3`)
- `AUTH_SESSION_URL` (default empty — full auth session URL)
- `AUTH_BASE_URL` (default empty — auth base URL, `/api/auth/session` appended)
- `AUTH_SESSION_TIMEOUT_MS` (default `2000`, ms → seconds)
- `ADD_NEW_PATIENT_MOCK_AUTH` (`1` on, `0` off; on by default if no auth URL)

### `add_new_patient_backend/db.py`

Owns the SQLite schema and the `DatabaseAdapter` Protocol. Only the
`patients` table is created. Columns mirror the persisted patient shape:

- `id` TEXT PK
- `patient_code` TEXT NOT NULL UNIQUE
- `first_name` TEXT NOT NULL
- `last_name` TEXT NOT NULL
- `sex` TEXT NOT NULL CHECK (`Male` or `Female`)
- `dob` TEXT NOT NULL (`YYYY-MM-DD`; not future-dated and at least 1 year ago)
- `phone_number` TEXT (nullable)
- `created_by_user_id` TEXT NOT NULL
- `created_at` TEXT NOT NULL ISO-8601
- `updated_at` TEXT NOT NULL ISO-8601

The DB CHECK constraints are a defense-in-depth backstop. Pydantic is expected
to reject invalid records before they reach SQLite. If SQLite raises a CHECK
or UNIQUE error, it means Pydantic let something through — investigate that
as the root cause.

### `add_new_patient_backend/repository.py`

Owns data access. Inline `SQLiteAdapter` reuses the Dashboard adapter shape
(commit/rollback/close, foreign keys on, row factory) but trimmed to the
single table this module needs.

Public functions:

```python
now_iso() -> str
patient_row(row) -> dict
repo.list_patients() -> list[dict]
repo.get_patient(id_or_code) -> dict | None
repo.create_patient(patient) -> dict
repo.existing_codes() -> set[str]
```

`create_patient` writes a new row. UNIQUE on `patient_code` is caught by
`main.py` and mapped to the `422` duplicate-code error shape.

### `add_new_patient_backend/models.py`

Owns the runtime patient contract. `PatientCreate` is a Pydantic v2
`BaseModel`. Field validators perform normalization AND validation:

- `patientCode` — trim, uppercase, reject non-matching `^[A-Z0-9]{6}$`,
  coerce empty string to `None` (server generates code).
- `firstName` / `lastName` — trim, reject empty, reject > 80 chars.
- `sex` — trim, must be `Male` or `Female`.
- `dob` — date of birth; rejects future dates and dates less than 1 year ago.
- `phoneNumber` — strip non-digits, empty to `None`.

`generate_patient_code()` uses `secrets.choice` over `CODE_ALPHABET`
(excludes ambiguous characters like `0`/`O`/`1`/`I`).

### `add_new_patient_backend/auth.py`

Owns the auth seam. Mirrors the Dashboard verified-session feed-in pattern:
caller auth headers are forwarded to the Authentication module, then this
module verifies the returned session inline per request.

Public surface:

```python
class AuthSessionError(Exception)
def normalize_authenticated_session(data: dict) -> dict | None
def normalize_psychiatrist_session(data: dict) -> dict | None
async def fetch_auth_identity(request: Request, session=None, *, require_psychiatrist=False) -> dict | None
def auth_session_url(request: Request) -> str
def forwarded_auth_headers(request: Request, session=None) -> dict[str, str]
```

Session normalization rejects expired / force_password_change /
disclaimer_blocked sessions. Psychiatrist normalization additionally rejects
non-psychiatrist roles. It does not decode JWT and never reaches into the auth
DB — only the upstream REST call.

### `add_new_patient_backend/main.py`

Owns the FastAPI app, REST handlers, auth dependencies, mock auth session
endpoint, static allowlist, exception handlers, and server-side fallback
patient code generation.

Auth dependency:

```python
async def require_authenticated_session(request: Request) -> dict
async def require_psychiatrist_session(request: Request) -> dict
```

`AuthSessionError` → HTTP 502 `authentication_session_required`.
Missing identity → HTTP 401 `authentication_session_required`.
`GET /api/patients` and `GET /api/patients/{id_or_code}` use
`require_authenticated_session`. `POST /api/patients` uses
`require_psychiatrist_session`.

`GET /api/auth/session` serves mock auth when `settings.use_mock_auth` is on.

Owns the FastAPI app, REST handlers, static allowlist, exception handlers,
and server-side fallback patient code generation.

#### Static Asset Rules

Only these paths are served as static files:

```text
/
/index.html
/styles.css
/app.js
/modules/add-new-patient
/modules/add-new-patient/
/modules/app.js
/modules/styles.css
/modules/add-new-patient/app.js
/modules/add-new-patient/styles.css
```

The `/modules/add-new-patient` path is the Dashboard launch target and serves
the same `index.html` shell as standalone `/`. The `/modules/...` asset aliases
exist because relative asset URLs from `/modules/add-new-patient` resolve under
`/modules`.

Every other non-`/api/` path returns `404` except the explicit Dashboard route
metadata endpoint below. This is intentional. Do not replace it with
`StaticFiles(directory=...)` unless you also preserve the invariant that private
data and source files are not public. In particular, these paths must not
resolve:

```text
/data/patients.json
/add_new_patient.sqlite3
/server.py
/server.js
/add_new_patient_backend/main.py
/schema/add-new-patient.schema.json
/requirements.txt
/test_add_new_patient_backend.py
/modules/server.py
/modules/add-new-patient/server.py
```

The catch-all `/{path:path}` route enforces this allowlist — delete it only
if you also preserve the privacy invariant.

#### Exception Handlers

`HTTPException` is converted to JSON. If `exc.detail` is already a dict it is
returned as-is; otherwise it is wrapped as `{"message": str(detail)}`.

`RequestValidationError` (raised by Pydantic when a request fails validation)
is mapped to:

```json
{
  "message": "Patient data failed validation.",
  "errors": {
    "fieldName": "Human-readable error"
  }
}
```

The `"Value error, "` prefix that Pydantic v2 attaches to custom
`ValueError` messages is stripped before returning to the client.

### `schema/add-new-patient.schema.json`

Documents the intended dataset layout, form contract, strings, and REST
contract. It is **not** executed at runtime. The runtime-enforced contract now
lives in `add_new_patient_backend/models.py`. The schema file is kept as
integration documentation only.

When changing patient fields, update in this order:

1. `add_new_patient_backend/models.py` for runtime behavior.
2. `app.js` inline validation for fast UX feedback (optional).
3. `index.html` for any new form controls.
4. `schema/add-new-patient.schema.json` for documentation alignment.

## REST Contract

All REST responses are JSON.

### `GET /api/health`

Returns:

```json
{
  "module": "Add New Patient",
  "status": "ok"
}
```

### `GET /internal/dashboard/module-routes/add-new-patient`

Returns the route shape Dashboard launch buttons expect:

```json
{
  "moduleId": "add-new-patient",
  "title": "Add New Patient",
  "href": "/modules/add-new-patient"
}
```

### `GET /api/patients`

Returns all persisted patients:

```json
{
  "patients": []
}
```

Requires a verified authenticated session. Missing or rejected sessions receive
HTTP 401 `authentication_session_required`; upstream auth session failures
receive HTTP 502 `authentication_session_unavailable`.

### `POST /api/patients`

Accepts:

```json
{
  "patientCode": "ABC123",
  "firstName": "Jane",
  "lastName": "Doe",
  "sex": "Female",
  "dob": "1986-07-07",
  "phoneNumber": "5551234567"
}
```

Behavior:

- `patientCode` is optional and is server-generated if absent or blank.
- All normalization and validation happens in the Pydantic model.
- Duplicate `patientCode` is rejected with `422`.
- Server-generated `id`, `createdAt`, and `updatedAt` are attached.
- SQLite UNIQUE constraint is a defense-in-depth backstop.

Success response (`201`):

```json
{
  "patient": {
    "id": "uuid",
    "patientCode": "ABC123",
    "firstName": "Jane",
    "lastName": "Doe",
    "sex": "Female",
    "dob": "1986-07-07",
    "age": 40,
    "phoneNumber": "5551234567",
    "createdAt": "ISO-8601",
    "updatedAt": "ISO-8601"
  }
}
```

Validation failure response (`422`):

```json
{
  "message": "Patient data failed validation.",
  "errors": {
    "fieldName": "Human-readable error"
  }
}
```

### `GET /api/patients/{idOrCode}`

Looks up a patient by:

- `id`, exact match
- `patientCode`, case-insensitive (via `UPPER()` on the make)

Returns:

```json
{
  "patient": {}
}
```

If missing:

```json
{
  "message": "Patient was not found."
}
```

## Browser Lifecycle Details

### Standalone Page

`index.html` loads:

```html
<script src="./app.js" type="module"></script>
```

Because `ADD_NEW_PATIENT_AUTO_INIT` is not set to `false`, `app.js` immediately
initializes against `document` and sets `window.AddNewPatientModule`.

The dashboard button calls `activate()`, which:

- Resets the form.
- Generates and displays a fresh patient code.
- Clears field errors and status.
- Hides the dashboard view.
- Shows the patient view.
- Focuses the first-name input.

### Embedded Host

The host must provide compatible markup or reuse `index.html` markup. It can
initialize manually:

```js
window.ADD_NEW_PATIENT_AUTO_INIT = false;
```

Then after `app.js` loads:

```js
const module = window.createAddNewPatientModule({
  root: hostElement,
  apiBaseUrl: "/internal-patient-module"
});
```

The host should call `destroy()` before removing the root from the DOM to
detach event listeners.

## Important Invariants

Preserve these unless the product requirements explicitly change:

1. The UI communicates through REST only.
2. `add_new_patient.sqlite3` is not served as a static asset.
3. Static file serving is allowlisted, not directory-wide.
4. Pydantic models are the runtime contract source of truth.
5. `schema/add-new-patient.schema.json` is documentation only.
6. Browser submit failures always resolve to a visible status message.
7. Embedded hosts can opt out of auto-init.
8. `destroy()` removes every event listener added during module initialization.
9. Test or verification data must not be left in the SQLite database.
10. Every patient REST endpoint requires a verified upstream auth session.
    Reads use `require_authenticated_session`; writes use
    `require_psychiatrist_session`. Auth is never bypassed in production — mock
    auth is a standalone-dev fallback gated on
    `ADD_NEW_PATIENT_MOCK_AUTH` and the absence of `AUTH_BASE_URL` /
    `AUTH_SESSION_URL`.
11. The module never decodes JWT and never reads the auth DB. Identity is
    obtained exclusively from `GET /api/auth/session` upstream.

## Known Limitations

This module is intentionally simple. These are current limitations, not
necessarily bugs:

- No pagination on `GET /api/patients`.
- No update or delete endpoint.
- No server-side request logging.
- SQLite file storage is single-process safe. Multiple processes sharing one
  database file would still need a stronger storage adapter.
- `schema/add-new-patient.schema.json` is documentation only; it is not loaded
  at runtime.

## Verification

Run the unittest suite:

```powershell
python -m unittest test_add_new_patient_backend.py
```

The suite boots uvicorn in a thread on a free port, exercises every REST
endpoint, asserts static allowlist + privacy invariants, and runs a
concurrent-create test (10 parallel POSTs with unique codes must all land).

Manual smoke:

```text
GET  /api/health                    -> 200
GET  /                              -> 200
GET  /app.js                        -> 200
GET  /styles.css                    -> 200
GET  /data/patients.json            -> 404
GET  /server.py                     -> 404
GET  /add_new_patient_backend/main  -> 404
GET  /api/patients (no session)     -> 401 authentication_session_required
POST /api/patients with valid data + psychiatrist session -> 201
POST /api/patients with long name   -> 422
POST /api/patients duplicate code    -> 422
GET  /api/patients/{patientCode} + session -> 200 after create
```

Do not leave test patients in the dataset.

## Safe Extension Guidance

### Adding a Patient Field

Update in this order:

1. `add_new_patient_backend/models.py`: add the field with a Pydantic
   validator (run exactly the rules you want enforced).
2. `add_new_patient_backend/db.py`: add the column to `SCHEMA` for fresh
   installs.
3. `add_new_patient_backend/repository.py`: extend the INSERT and
   `patient_row` shape.
4. `index.html`: add the form control and `data-error-for` slot.
5. `app.js`: include the field in `getPatientPayload` and update the inline
   validation if you want immediate UX feedback.
6. `schema/add-new-patient.schema.json`: align the integration documentation.
7. Update this handoff if the field changes the contract materially.

### Replacing SQLite Storage

Treat the storage implementation as an adapter behind these behaviors:

- `list_patients()` returns all patients.
- `get_patient(id_or_code)` returns one or `None`.
- `create_patient(patient)` persists and returns the row.
- `existing_codes()` returns the set of `patient_code` values.

Do not let browser code talk directly to the storage adapter.

### Adding Auth

Auth lives in `add_new_patient_backend/auth.py` and the session dependencies in
`main.py`. Read access requires any verified session. Write access requires
`PSYCHIATRIST`; changing that role check changes the CDSS boundary. Do not
implement auth in static-file serving. Do not decode JWT or read the auth DB.

### Adding Tests

Highest-value tests already covered: contract tests for create + validation,
duplicate-code handling, server-side code generation, static allowlist,
privacy invariants, and concurrent patient creation. New features should add
focused tests in the same unittest shape.

## Recent Architectural Changes

The A0.1 module-level rebuild replaced the Node `http` server with Python
FastAPI so this module shares Docker base images, contract patterns, and
unittest suite shape with the Dashboard and Authentication modules.

- Removed: `server.js`, `patient-contract.js`, `package.json`, Node runtime.
- Added: `add_new_patient_backend/` Python package, `server.py`, `requirements.txt`.
- Pydantic replaces the hand-rolled JS contract as the runtime contract source.
- SQLite replaces `data/patients.json` for persistence.
- REST contract shape is preserved so the existing `app.js` continues to work
  with no changes to fetch logic.
- Static allowlist + privacy invariant is preserved.

### B1.1 — Auth REST client + identity verification seam

Added `add_new_patient_backend/auth.py` mirroring the Dashboard
verified-session feed-in pattern without adding a local session table. Wired
`require_authenticated_session` on patient reads and
`require_psychiatrist_session` on patient writes. Added mock
`GET /api/auth/session` endpoint for standalone dev. `AuthSessionError` → HTTP 502
`authentication_session_unavailable`; missing/upstream-401 identity → HTTP
401 `authentication_session_required`. The module never decodes JWT and never
reads the auth DB.

If future changes undo any of the invariants above, treat that as a regression
unless a new architecture deliberately replaces them.

## F1.1 — Stable Patient Identifier Contract

Cross-module patient resolution (Follow-up module, Treatment Plan,
reviewers) is pinned by `id` (UUID) or `patientCode`
(case-insensitive `^[A-Z0-9]{6}$`). Endpoint shape
`/api/patients/{identifier}` accepts either form; resolution order in
`repository._find_patient_id_row` is UUID exact-match first, then
uppercased `patient_code` match. No substring or partial match.

Invariants (preserve unless requirements change them):

- `id` is generated server-side at `POST /api/patients`, immutable for
  the patient's lifetime, and is the canonical cross-module reference.
  Future Follow-up module "modified treatment plan" intake write MUST
  reference this `id` directly.
- `patientCode` is generated server-side when not supplied and is
  stable per patient. Collisions are forbidden at the storage layer:
  SQLite `UNIQUE` on `patients.patient_code` (see `db.py` `SCHEMA`).
  Duplicate-code POST returns HTTP 422.
- v1 does NOT derive `patientCode` from `id`. Random selection over
  `CODE_ALPHABET` plus DB `UNIQUE` backstop is the contract for v1.
  A future module that demands deterministic, guest-proof codes MUST
  replace this, not amend it silently.
- `GET /api/patients/{identifier}/intake` returns the patient plus full
  encounter history for Follow-up module loading. Pin to the same
  identifier contract; auth is `require_psychiatrist_or_admin_session`.

Test coverage (`test_add_new_patient_backend.py`):

- `test_get_patient_by_id_returns_patient`: UUID lookup.
- `test_duplicate_patient_code_rejected_422`: DB UNIQUE backstop.
- `test_get_patient_intake_returns_patient_and_records_newest_first`:
  encounter history endpoint.
- Concurrent `test_concurrent_creation_uses_unique_codes` exercises the
  UNIQUE collision path under load.

If a new lookup endpoint is added, route through
`PatientRepository._find_patient_id_row` (or its successor) and add a
matching test that resolves the same patient by `id` AND by `patientCode`.
