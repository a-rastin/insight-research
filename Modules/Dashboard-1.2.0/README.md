# Dashboard Module

Dashboard is a standalone web app and embeddable module. Boundary rule: internal REST only. Dashboard never imports Authentication code, decodes JWTs, reads an auth DB, or implements patient/admin module workflows.

Backend is Python FastAPI with SQLite persistence behind a repository/DB adapter layer. Dashboard persists only local session/event rows; Authentication remains source of truth for users, roles, and profile display data. `DASHBOARD_DB_PATH` controls SQLite file location and defaults to `dashboard.sqlite3` in this directory.

## Run

```powershell
npm start
```

Equivalent direct command:

```powershell
python -m uvicorn dashboard_backend.main:app --host 127.0.0.1 --port 4173
```

Open `http://localhost:4173/dashboard/`.

Without `AUTH_BASE_URL` or `AUTH_SESSION_URL`, Dashboard serves a mock `GET /api/auth/v2/session` endpoint for standalone development. Set `DASHBOARD_MOCK_AUTH=0` in integrated environments if a real auth endpoint is required.

## Test

```powershell
npm test
```

## Health

```http
GET /healthz
GET /readyz
```

`/readyz` checks DB connectivity.

## Workspace Rules

- Both roles enter `Workspace`.
- Workspace responses include `currentDateTime` and `displayName`.
- Psychiatrist display names use `Dr. {fullName}`.
- Psychiatrist buttons: `Add New Patient`, `Patient Follow-up`, `List of Patients`, `Setting`.
- Admin buttons: `Add New User`, `Logs`, `Backup`, `List of Users`, `DDI Knowledge`, `BN Models`.
- Destinations render `available`, `unavailable`, or `unauthorized` explicitly.
- Only available destinations expose a real gateway-relative module route.
- Add New User and List of Users navigate to Authentication's gateway-relative
  account-administration surface. Dashboard stores and proxies no account data.
- DDI Knowledge and BN Models navigate to provider-owned administration surfaces.
  Dashboard displays only live readiness and aggregate clinical-use status; it
  does not store, edit, activate, or return provider artifacts.
- Dashboard does not implement patient, treatment, admin log, backup, or user-management module logic.

## Module Interface

Authentication identity is verified through REST:

```http
GET /api/auth/v2/session
```

Dashboard activation uses only Dashboard's internal REST endpoint:

```http
POST /internal/dashboard/session
```

The caller supplies the opaque Authentication cookie (development fixtures may
use `X-Auth-Session`). Request body identity fields are ignored. Dashboard
requires interface `2.0.0`, UUID user and session identities, a lowercase
`admin` or `psychiatrist` role, an active future UTC `Z` expiry,
`authorized: true`, and cleared password/disclaimer gates. Unsupported or
legacy response shapes fail closed.

The UI then reads:

```http
GET /internal/dashboard/workspace
```

Available buttons may revalidate their destination through:

```http
GET /internal/dashboard/module-routes/{moduleId}
```

Every protected Dashboard endpoint verifies the local dashboard session and re-checks Authentication through `GET /api/auth/v2/session`, so revocation, disablement, expiry, and role changes take effect immediately.

Admin provider status uses `DDI_READINESS_URL`, `BN_MANAGER_READINESS_URL`, and
`BN_MANAGER_STATUS_URL`. `DASHBOARD_PROVIDER_TIMEOUT_MS` defaults to `2000`.
Missing or failed provider responses remain visibly unavailable.

## Files

| File | Purpose |
| --- | --- |
| `dashboard_backend/main.py` | FastAPI routes, static host, dev mock auth, workspace model |
| `dashboard_backend/repository.py` | Dashboard session/event repository |
| `dashboard_backend/db.py` | DB adapter protocol plus SQLite adapter/schema |
| `dashboard_backend/auth.py` | Authentication session REST client |
| `test_dashboard_backend.py` | Integration tests for auth boundary, workspace buttons, route placeholders, health |
| `index.html` | Standalone entry page |
| `dashboard.js` | Workspace UI adapter |
| `styles.css` | Layout and visual design |
| `api-contract.md` | Internal REST interface |
| `dataset-schema.md` | Dashboard-local persistence and workspace strings |
| `HANDOFF.md` | Module handoff |

## Postgres Upgrade Path

Route handlers depend on `DashboardRepository`, not SQLite directly. SQL access is isolated behind `DatabaseAdapter`; replacing `SQLiteAdapter` with a Postgres adapter should preserve REST behavior and repository method contracts.

