# Add New Patient Module

Standalone patient intake module with a FastAPI backend and a small browser UI.
The UI communicates with the module through internal REST APIs only.

## Stack

- Backend: Python 3.13+, FastAPI, uvicorn, Pydantic
- Frontend: vanilla HTML/CSS/JS, no build tooling
- Storage: SQLite

## Run

Install dependencies once:

```powershell
pip install -r requirements.txt
```

Start the server:

```powershell
uvicorn add_new_patient_backend.main:app --port 4173
```

Or via the `server.py` entry point:

```powershell
uvicorn server:app --port 4173
```

Open `http://localhost:4173`.

The port can be overridden with `--port`. The SQLite path can be overridden with
the `ADD_NEW_PATIENT_DB_PATH` environment variable (defaults to
`add_new_patient.sqlite3` in the repo root).

Standalone dev keeps `/` as the browser entry point. Embedded Dashboard launch
uses `/modules/add-new-patient`, which serves the same static shell.

## Tests

```powershell
python -m unittest test_add_new_patient_backend.py
python -m unittest test_encounter_v2_contracts.py
```

## REST API

- `GET /internal/dashboard/module-routes/add-new-patient`
- `GET /api/health`
- `GET /api/patients`
- `POST /api/patients`
- `GET /api/patients/{idOrCode}`
- `GET /api/add-new-patient/v2/contract`
- `GET|POST /api/add-new-patient/v2/patients`
- `POST /api/add-new-patient/v2/patients/search`
- `GET|PATCH /api/add-new-patient/v2/patients/{patientId}`
- `POST /api/add-new-patient/v2/patient-code-aliases/resolve`
- `GET /api/add-new-patient/v2/encounters/{encounterId}`
- `GET /api/add-new-patient/v2/encounters/{encounterId}/intake-snapshot`

V2 uses UUID-only resource paths, body-based patient-code resolution/search,
atomic idempotent patient plus first-encounter creation, strong ETags, paginated
lists, strict UTC timestamps, versioned provenance, ordered transactional
migrations, request tracing, and RFC 9457 problem details. Legacy creation is a
request/response adapter over the same v2 persistence transaction. See
`docs/api-contract.md` and `schema/patient-encounter-v2.openapi.json`.

## Embed Contract

Dashboard route discovery contract:

```json
{
  "moduleId": "add-new-patient",
  "title": "Add New Patient",
  "href": "/modules/add-new-patient"
}
```

Load `app.js` after the module markup and call:

```js
window.AddNewPatientModule.activate();
```

The host can point the frontend at a different internal API base URL before
loading the module:

```js
window.ADD_NEW_PATIENT_API_BASE_URL = "https://internal.example.local";
```

For host-controlled initialization, disable auto-init before loading `app.js`,
then create the module with an explicit root:

```js
window.ADD_NEW_PATIENT_AUTO_INIT = false;

const addNewPatient = window.createAddNewPatientModule({
  root: document.querySelector("[data-module='add-new-patient']"),
  apiBaseUrl: "https://internal.example.local"
});

addNewPatient.activate();
```
