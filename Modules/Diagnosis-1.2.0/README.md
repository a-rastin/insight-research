## `diagnosis` module

DSM-5-TR schizophrenia criteria checklist for the Insight clinical decision
support tool. Clinician-controlled — the psychiatrist confirms or bypasses;
the model never decides.

### Interface (the seam)

This table is a summary. The authoritative spec — request/response
shapes, error codes, auth, CSRF, route discovery, invariants — lives
in [`docs/api-contract.md`](docs/api-contract.md). If the README and
that document disagree, `docs/api-contract.md` wins; the route
catalogue there is locked against the live router by
`test_unittest.TestRestContract.test_api_contract_doc_lists_every_live_route`.

| Method | Path                          | Purpose                                            |
|--------|-------------------------------|----------------------------------------------------|
| GET    | `/internal/dashboard/module-routes/{moduleId}` | Dashboard module-route discovery. Returns the diagnosis launch descriptor (e.g. `launch.href = /modules/diagnosis`) for `moduleId == "diagnosis"`, 404 otherwise. Read-only, no patient state. |
| GET    | `/internal/diagnosis/audit/{code}` | Audit-log seam for the future Insight Logs module (and other internal integrators). Returns the chronologically persisted local audit trail for `code` (`{ "code": ..., "snapshots": [ ... ] }`, oldest first). Reads only — never writes a snapshot on demand. An unknown / never-audited code yields an empty `snapshots` list, not a 404. Read-only (no state mutation), no CSRF gate. Auth: `psychiatrist` or `admin`. Each decision-bearing PUT on `/diagnosis/{code}` now persists a snapshot through `_dump_for_audit` -> `store.audit_snapshot`. |
| GET    | `/diagnosis/_meta`            | Criteria tree (no patient data). UI bootstraps.   |
| GET    | `/diagnosis/_csrf`           | Mint a signed double-submit CSRF token + set the `csrf` cookie. Read-only. |
| GET    | `/diagnosis/{code}`           | Current checked state + evaluation for a patient. |
| PUT    | `/diagnosis/{code}`           | Persist `{checked:[...], decision:"confirmed"|"definite"}`. Returns evaluation. **CSRF-gated.** |
| POST   | `/diagnosis/{code}/init`      | Create an empty session for a patient code. **CSRF-gated.** |
| POST   | `/api/diagnosis/v2/assessments` | Initialize canonical Patient/Encounter UUID-bound assessment. |
| GET/PUT | `/api/diagnosis/v2/assessments/{assessmentId}` | Fetch or conditionally update versioned assessment. |
| GET    | `/api/diagnosis/v2/encounters/{encounterId}/assessment-snapshot` | Fetch Treatment Plan source snapshot. |
| GET    | `/`                           | Standalone shell: serves the embeddable module UI HTML (one `#diagnosis-root` mount point + `window.createDiagnosisModule`) and bootstraps it against `document.body`. Stamps a CSRF token into `<meta name="csrf-token">` + sets the `csrf` cookie. |
| GET    | `/health`                     | Liveness probe.                                   |
| GET    | `/ready`                     | Readiness probe. 200 when ok + `{ok, module, checks:{db, auth, patient}}`, else 503 with the same body. **Never leaks URLs / paths / secrets.** |

### CSRF on write routes

PUT and POST `/init` mutate state, so they require a signed double-submit
CSRF token (OWASP pattern). The HTML page route stamps a fresh signed
token into a `<meta name="csrf-token">` tag and sets the matching `csrf`
cookie; the JS reads that meta value and echoes it back as the
`X-CSRF-Token` header on every write. Non-browser clients should
`GET /diagnosis/_csrf` first, then pass the returned token as both the
`csrf` cookie and the `X-CSRF-Token` header on subsequent writes. See
`diagnosis/csrf.py` for the protocol; the in-process self-check and
headless tests short it via `DIAGNOSIS_AUTH_BYPASS=1` (same gate as
auth).

### Patient identity (canonical id from "Add New Patient")

`{code}` in the route path is the local session key only — it is NOT
the canonical patient id. Before a write route persists a row, the
module calls the INSIGHT "Add New Patient" registry at
`GET {PATIENT_BASE_URL}/api/patients/lookup?code=...` (env
`PATIENT_BASE_URL`, default `http://localhost:9000`) to align the row's
`patient_id` column with the registry's canonical `patient.id`. The
diagnosis module never reads the patient DB and never imports from the
primitives app — it forwards the incoming `Cookie` (same trust boundary
as the auth service) and reads the JSON back. The response shape is
`{"id", "patient_code", "display_name"}`.

A registry 404, a transport / parse fault, or a missing canonical `id`
all map to a clean `422` so the clinician sees "unknown patient code"
instead of a stack trace — never a row whose `patient_id` collapses
back to the free-text code. See `diagnosis/patient.py` for the contract;
`test_patient.py` exercises the happy + fault paths (no test framework).

Opt-in: the adapter is **disabled by default** to preserve the prior
diagnosis-local behaviour for the self-check and offline tests. Set
`DIAGNOSIS_PATIENT_LOOKUP=1` at deployment to enforce real lookup.

### Module-local readiness (`/ready`)

`/health` is a liveness probe — "the process is up." `/ready` is a
**module-local** readiness probe — "my dependencies are configured and a
clinical request won't immediately 401 / 422." Response shape (stable):

```json
{
  "ok": true,
  "module": "diagnosis",
  "checks": {
    "db":      {"ok": true},
    "auth":    {"ok": true, "configured": true, "bypass": false},
    "patient": {"ok": true, "enabled": false, "configured": true}
  }
}
```

`ok` is the AND of every check. The HTTP route returns 200 when `ok`
and 503 otherwise so a load balancer can gate traffic on it.

The probe **never leaks secrets** and **never calls a live service**:

- **DB** — probes the live `DiagnosisStore` with `SELECT 1` on the
  same connection the route handlers reuse (never echoes the on-disk
  DB path).
- **Auth** — verifies `AUTH_BASE_URL` is configured AND the
  `DIAGNOSIS_AUTH_BYPASS=1` shim is off. We do NOT call the auth
  service (it needs the user's `Cookie`, so a cookieless probe would
  401 / surface the base URL). `bypass: true` in the response is the
  deploy alarm that fires when the shim is left on in production.
- **Patient** — the adapter is opt-in. When `DIAGNOSIS_PATIENT_LOOKUP`
  is not `"1"` the probe reports `{enabled: false, configured: true}`
  as a clean "skipped" state (the adapter short-circuits and never
  contacts the registry). When enabled, the probe verifies
  `PATIENT_BASE_URL` is configured.

Pure function form: `from diagnosis import check_readiness;
check_readiness()` — when mounted inside the larger Insight app the
parent composes this into its own readiness aggregator. See
`diagnosis/readiness.py` for the contract and `test_readiness.py` for
the function + HTTP 200/503 + no-leak paths (no test framework). The
shape and the no-leak contract are locked by HANDOFF §9.11.

### Dashboard module-route discovery

The larger Insight Dashboard learns how to launch each mounted module by
hitting a single URL pattern across every module:

    GET /internal/dashboard/module-routes/{moduleId}

The diagnosis module answers for `moduleId == "diagnosis"` and returns a
stable launch descriptor; any other id falls through to a clean `404` so a
misrouted call is loud but does not leak a stack trace. The descriptor
shape (Dashboard depends on every key):

```json
{
  "moduleId": "diagnosis",
  "title": "Diagnosis",
  "description": "DSM-5-TR schizophrenia criteria checklist.",
  "launch": {"href": "/modules/diagnosis"},
  "routes": {"self": "/diagnosis/_meta",
             "csrf": "/diagnosis/_csrf",
             "session": "/diagnosis/{code}"}
}
```

Read-only (no patient-state mutation, no CSRF gate). Auth: `psychiatrist`
or `admin` — same read policy as `_meta` / `_csrf`. See `diagnosis/dashboard.py`
for the contract and `test_discovery.py` for the happy + fault paths
(no test framework).

### Run standalone

```bash
pip install -r requirements.txt
python -m diagnosis                # http://localhost:8000?code=P-0427-A
```

The criteria engine self-check (`criteria._demo`, a thin shim over
`test_unittest.py::TestCriteriaRules`) runs before boot.

### Test suite

No external test framework — only stdlib ``unittest`` plus the existing
ponytail-style harnesses. Run the full surface:

```bash
python -m test_unittest    # rules + REST contract + auth + CSRF + persistence + patient (stdlib unittest)
python -m test_config      # settings adapter + consumer wiring (env snapshot, frozen dataclass)
python -m test_routes       # seam split + route-order invariants
python -m test_auth         # role enforcement via fake auth service
python -m test_csrf         # CSRF gate via fake auth service
python -m test_discovery    # Dashboard module-route discovery
python -m test_patient      # canonical patient identity via fake registry
python -m test_readiness    # readiness probe + no-leak + HTTP 200/503
python -m test_embed        # embeddable module UI contract (createDiagnosisModule)
```

The boot self-checks (`criteria._demo`, `api._http_selfcheck`) are now
thin shims that run the matching ``unittest`` cases in `test_unittest.py`,
so the fail-fast contract (HANDOFF §9.5) holds without duplicating
assertions. `python -m diagnosis` runs all six self-checks
(`criteria._demo`, `store._store_selfcheck`, `patient._patient_selfcheck`,
`readiness._readiness_selfcheck`, `config._config_selfcheck`,
`api._http_selfcheck`) before binding uvicorn.

### Mount inside Insight (the larger app)

```python
from fastapi import FastAPI
from diagnosis import router

app = FastAPI()
app.include_router(router, prefix="/diagnosis")
```

When mounted, the HTML page at `/diagnosis/` calls the same-origin API, so no
CORS or absolute URLs are required.

### Embeddable module UI — `createDiagnosisModule({root, apiBaseUrl})`

The web page is an embeddable module UI matching the "Add New Patient"
pattern. The served HTML does NOT bake a standalone shell — it ships a
single mount point (`#diagnosis-root`) and a constructor:

```js
// window.createDiagnosisModule is exposed by the served page.
// Standalone case (python -m diagnosis -> GET /) bootstraps itself:
const inst = createDiagnosisModule({
  root: document.getElementById("diagnosis-root"),
  apiBaseUrl: "",       // same-origin root for the mounted case
  embedded: false,      // true inside the larger Insight dashboard
  initialCode: "P-0427-A", // optional pre-load patient code
});
inst.mount();           // paint criteria UI inside `root`
// inst.unmount();      // tear down DOM + listeners on host navigation away
// inst.setPatientCode("P-0427-A");  // load a different patient live
```

Contract the host passes / receives:
- `{HTMLElement}  root`        — mount target; the standalone shell passes `document.body`.
- `{string}       apiBaseUrl`  — prefix for every API call (`/diagnosis` if cross-origin; `""` same-origin).
- `{boolean}      embedded`    — when true, the module emits no `Insight / .dm-topbar` header (the host dashboard already shows its own) and never mutates `history`.
- returns `{ mount(): void, unmount(): void, setPatientCode(code): void }` for clean teardown + live panel swaps.

Contract the module preserves (do NOT regress):
- `/diagnosis/_meta` `rules` contract stays the single source of truth
  for the optimistic display — the JS NEVER reimplements the DSM logic
  in JavaScript (HANDOFF §9.12).
- The CSRF token still comes from `<meta name="csrf-token">` (stamped
  by the page seam on serve); every PUT/POST carries `X-CSRF-Token`.
- The "Diagnosis is clear" button is `disabled` unless Criterion A is
  met; the bypass button is **always enabled** — clinician authority over
  the checklist (HANDOFF §6).
- The module NEVER mutates the host URL, NEVER bakes a host topbar,
  NEVER ships a host-navigation placeholder button (the host owns the
  return-to-dashboard link).

The previous shell baked a full standalone ``Insight`` topbar and a
``Back to dashboard`` placeholder directly into `<body>`; that is gone
(replaced by the host-owned `createDiagnosisModule` contract). `test_embed.py`
locks the embeddable UI contract (pathset unchanged, byte-clean bypass
serve preserved, no host chrome, no host-navigation placeholder).

### Architecture (deep module)

- **Interface** — the FastAPI router composed in `api.py` from three seams:
  - `page.py` — browser page: `GET /`.
  - `dashboard.py` — Dashboard discovery interface: `GET /diagnosis/_meta`
    (criteria tree + the `rules` contract `criteria.meta_contract` that drives
    the UI's optimistic display — server rules stay the single source of
    truth, the browser never reimplements them in JS), `GET /diagnosis/_csrf`,
    `GET /internal/dashboard/module-routes/{moduleId}`
    (Dashboard module-route discovery -> launch href `/modules/diagnosis`),
    `GET /internal/diagnosis/audit/{code}`
    (audit-log seam exposing the persisted local audit trail for the future
    Insight Logs module — read-only, never writes a snapshot on demand),
    the `_dump_for_audit` snapshot hook (now persisting a local audit event
    on every decision-bearing PUT).
  - `diagnosis_api.py` — protected per-patient REST: `POST /diagnosis/{code}/init`,
    `GET /diagnosis/{code}`, `PUT /diagnosis/{code}`.
  - `deps.py` — shared process-wide `DiagnosisStore` + role/CSRF dependencies
    (and the `DIAGNOSIS_AUTH_BYPASS=1` shim) consumed by all three seams.
    Eight routes + the standalone `/health`. Small.
- **Implementation** — the DSM-5-TR evaluation in `criteria.py`. Pure function
  `evaluate(checked_ids) -> Evaluation`. No I/O, no side effects.
  Tested via `test_unittest.py::TestCriteriaRules` (stdlib ``unittest``, no
  new deps); the inline `_demo()` shim in `criteria.py` runs those cases
  before the standalone server boots, so a rule regression fails fast.
- **Web page** — single HTML file, vanilla JS, token CSS from `DESIGN.md`.
  No build step. Talks to the API via `fetch`. Exposes
  `createDiagnosisModule({root, apiBaseUrl})` so the larger Insight
  dashboard can mount the module UI inside its own host panel without
  baking a second standalone topbar or shipping a host-navigation
  placeholder. See "Embeddable module UI" above and `test_embed.py`.
- **CSRF** — write routes (PUT + POST `/init`) are gated by a signed
  double-submit token (HMAC-SHA256, per-process secret). See `diagnosis/csrf.py`
  and `test_csrf.py`. The HTML page stamps the token into a `<meta>` tag
  and cookie on serve; the JS echoes it back via the `X-CSRF-Token` header.
- **Patient identity** — `diagnosis/patient.py` aligns the free-text
  `{code}` path parameter with the canonical INSIGHT patient id from the
  "Add New Patient" registry. Adapter calls the registry over internal
  REST (no DB imports, no primitives-app imports). Disabled by default;
  set `DIAGNOSIS_PATIENT_LOOKUP=1` to enforce. See `test_patient.py` for
  the contract. The seam split itself is locked by `test_routes.py`.
- **Config adapter** — `diagnosis/config.py` owns the integration knobs in
  one frozen `Settings` dataclass + a `settings` singleton read from the env
  at import. Every consumer (`store`, `auth`, `patient`, `csrf`, `app`,
  `__main__`, `dashboard`) reads `settings.*` instead of scattering
  `os.environ.get` — this is the only place to add a new integration
  knob. Locked by `test_config.py` + `_config_selfcheck` (run by the boot
  chain).

### Configuration (env knobs → `Settings`)

The `diagnosis/config.py` adapter is the single source for every
previously hard-coded knob the module needs to integrate with the larger
Insight app. All values default to the prior hard-coded constants, so a
bare import behaves identically to the pre-adapter module.

| Env var                       | `Settings` field        | Default                | Purpose |
|-------------------------------|-------------------------|------------------------|---------|
| `DIAGNOSIS_DB_PATH`           | `db_path`               | `diagnosis_store.db`   | SQLite location. |
| `AUTH_BASE_URL`               | `auth_url`              | `http://localhost:9000`| Insight auth service base URL. |
| `AUTH_TIMEOUT_S`             | `auth_timeout_s`        | `2.0`                  | Auth HTTP timeout. |
| `PATIENT_BASE_URL`            | `patient_url`           | `http://localhost:9000`| Patient registry base URL. |
| `PATIENT_TIMEOUT_S`           | `patient_timeout_s`     | `2.0`                  | Registry HTTP timeout. |
| `DIAGNOSIS_PATIENT_LOOKUP`    | `patient_lookup`        | `False` (set `1` to opt in) | Enforce canonical patient id lookup. |
| `DIAGNOSIS_CORS_ORIGINS`      | `cors_origins`           | `*` (comma list)       | CORS allow-origins for standalone mode. |
| `DIAGNOSIS_AUTH_BYPASS`       | `mock_auth`             | `False` (set `1` for self-check) | Self-check / offline-test auth + CSRF bypass shim. NEVER in production. |
| `DIAGNOSIS_CSRF_SECRET`       | `csrf_secret`           | unset -> per-process random | Pinned HMAC secret for multi-worker. |
| `DIAGNOSIS_CSRF_SECURE`       | `csrf_secure`           | `False` (set `1` behind TLS) | Cookie `Secure` flag. |
| `DIAGNOSIS_MODULE_BASE_PATH`  | `module_base_path`      | `/diagnosis`           | Mount prefix derived into `module_id` + `launch_href` for Dashboard discovery. |
| `DIAGNOSIS_HOST`              | `host`                  | `0.0.0.0`              | Standalone uvicorn bind host. |
| `DIAGNOSIS_PORT`              | `port`                  | `8000`                 | Standalone uvicorn bind port. |

Tests that need a different snapshot rebind the consumer module globals
(`auth.AUTH_BASE_URL`, `patient.PATIENT_BASE_URL`, `csrf._SECRET`) via the
existing `reset_*_for_tests` hooks — the singleton itself is frozen.

### Notes

- Store is a SQLite-backed repository adapter (`DiagnosisStore` in
  `diagnosis/store.py`). Single-process, WAL journal. Override the DB
  location with the `DIAGNOSIS_DB_PATH` env var. Sessions persist across
  restarts and the `audit` table records every decision-bearing PUT:
  `diagnosis_api.put_session` calls `_dump_for_audit` ->
  `store.audit_snapshot` after each persist, so each clinician checkbox
  session PUT (the UI's debounced write on every toggle AND the explicit
  confirm / bypass buttons) leaves a chronological local audit event.
  The dashboard seam's `GET /internal/diagnosis/audit/{code}` exposes
  that trail to the future Insight Logs module (read-only). A row's
  snapshot is the source row (`decision` + `checked` ids), with no
  derived `evaluation` key — clinician-authority extends into the
  audit trail (HANDOFF §6.1).
- "Diagnosis is clear" sends `decision: "confirmed"` (criteria met).
- "Diagnosis is clear (bypass)" sends `decision: "definite"` — clinician
  authority over the checklist per DESIGN.md §6 (clinician-confirmed bypass).
- The clinician-authority invariant (the model never auto-decides; bypass is
  always valid on an unmet checklist; `met == True` does not coerce `decision`
  to `"confirmed"`) is a tested contract, not just prose: see
  `test_unittest.TestClinicianAuthority` and HANDOFF §6.1. The boot self-check
  loads it via `diagnosis/api.py::_http_selfcheck` and fails fast on any
  regression.
- All text follows the Insight visual system (Inter body, JetBrains Mono for
  the patient code/score quantities, teal as the single locked accent).
