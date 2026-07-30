# Diagnosis Module — REST API Contract

Canonical contract for the `diagnosis` module's HTTP surface. The
[README](../README.md) is a summary; this document is the authoritative
spec every Insight integrator (Dashboard, Logs, Auth gateway, "Add New
Patient" registry, non-browser clients) codes against. If the code and
this document disagree, **the code wins** — file an issue and update
this document in the same change. Hands-off spec for: route shapes,
request / response bodies, error codes, auth, CSRF, route discovery,
and the invariants a client can rely on.

Source of truth files (HANDOFF §12): `diagnosis/api.py` (composition),
`diagnosis/diagnosis_api.py` (per-patient REST), `diagnosis/dashboard.py`
(discovery + audit seam), `diagnosis/page.py` (browser page),
`diagnosis/app.py` (`/health`, `/ready`), `diagnosis/criteria.py`
(`Evaluation` + `meta_contract`), `diagnosis/auth.py`, `diagnosis/csrf.py`,
`diagnosis/patient.py`, `diagnosis/deps.py`.

- **Module id**: `diagnosis` (derived from `DIAGNOSIS_MODULE_BASE_PATH`;
  the last path segment of the mount prefix — see §10).
- **Default mount**: `app.include_router(router, prefix="/diagnosis")`.
- **Standalone**: `python -m diagnosis` → `http://{DIAGNOSIS_HOST}:{DIAGNOSIS_PORT}`
  (default `0.0.0.0:8000`).
- **Decision support, not a decision**: the model's `evaluation.met` never
  auto-decides a diagnosis. The psychiatrist affirms (`"confirmed"`) or
  bypasses (`"definite"`); both are the clinician's explicit voice. See
  §11 (Clinician Authority) and HANDOFF §6 / §6.1.

---

## 1. Conventions

| Notation            | Meaning                                                       |
|---------------------|---------------------------------------------------------------|
| `{code}`            | Free-text patient code path parameter (local session key).    |
| `{moduleId}`        | Module id path parameter for Dashboard discovery.             |
| `…`                 | Elided nested object; see the cited shape section.           |
| Status → body       | Every error response is `{"detail": <string>}` (FastAPI HTTPException). |
| `checked`           | A JSON array of criterion `id` strings (`A1`–`A6`, `B1`, `C1`, `D1`). |
| Timestamps          | Unix epoch seconds (int), column `created_at` / `updated_at`. |
| `evaluation` object | Shape defined in §7 (the `RESULT_FIELDS` contract).          |

Unless noted, every JSON response is `Content-Type: application/json`.
The browser page (`GET /`) is the only HTML response.

All write routes (POST `/init`, PUT `/{code}`) require both a valid
auth role **and** a signed double-submit CSRF token; read routes
require a valid auth role only. Auth runs before CSRF on writes so an
unauthenticated caller gets a 401 and never learns a CSRF token exists
(HANDOFF §9.8). See §8 (Auth) and §9 (CSRF).

---

## 2. Route catalogue

Prefix all `/diagnosis/...` and `/internal/...` paths with the mount
prefix when the module is mounted (default `/diagnosis`; see §10).
The `/`, `/health`, `/ready` routes ship on the standalone app and on
the parent Insight app's composed router (HANDOFF §3 — `app.py`).

| Method | Path                                          | Seam            | Purpose                                                          | Auth                              | CSRF  |
|--------|-----------------------------------------------|-----------------|------------------------------------------------------------------|-----------------------------------|-------|
| GET    | `/`                                           | `page.py`       | Standalone shell: serve the embeddable module UI HTML + stamp CSRF meta/cookie. | `psychiatrist` \| `admin`         | —     |
| GET    | `/health`                                     | `app.py`        | Liveness probe.                                                  | none                              | —     |
| GET    | `/ready`                                      | `app.py`        | Readiness probe. 200 when ok, 503 otherwise.                     | none                              | —     |
| GET    | `/diagnosis/_meta`                            | `dashboard.py`  | Criteria tree + `rules` contract (UI bootstrap, single source of truth). | `psychiatrist` \| `admin`         | —     |
| GET    | `/diagnosis/_csrf`                            | `dashboard.py`  | Mint a signed CSRF token + set the `csrf` cookie.                  | `psychiatrist` \| `admin`         | —     |
| GET    | `/internal/dashboard/module-routes/{moduleId}` | `dashboard.py` | Dashboard module-route discovery. 404 for unknown `moduleId`.      | `psychiatrist` \| `admin`         | —     |
| GET    | `/internal/diagnosis/audit/{code}`             | `dashboard.py`  | Audit-log seam: persisted chronological audit trail for `code`.   | `psychiatrist` \| `admin`         | —     |
| POST   | `/diagnosis/{code}/init`                      | `diagnosis_api.py` | Create an empty session for a patient code.                   | `psychiatrist`                    | **required** |
| GET    | `/diagnosis/{code}`                           | `diagnosis_api.py` | Current checked state + evaluation for a patient.            | `psychiatrist` \| `admin`         | —     |
| PUT    | `/diagnosis/{code}`                           | `diagnosis_api.py` | Persist `{checked, decision}`; return evaluation + decision.  | `psychiatrist`                    | **required** |
| GET    | `/api/diagnosis/v2/contract`                  | `v2.py`          | Discover interface, schema, rule, profile, and retention versions. | none | — |
| GET    | `/api/diagnosis/v2/openapi.json`              | `v2.py`          | OpenAPI 3.1 contract. | none | — |
| GET    | `/api/diagnosis/v2/diagnosis-assessment-v2.schema.json` | `v2.py` | Draft 2020-12 assessment schema. | none | — |
| POST   | `/api/diagnosis/v2/assessments`               | `v2.py`          | Idempotently initialize one Patient/Encounter-bound assessment. | `psychiatrist` | **required** |
| GET    | `/api/diagnosis/v2/assessments/{assessmentId}` | `v2.py`         | Fetch current versioned assessment. | `psychiatrist` \| `admin` | — |
| PUT    | `/api/diagnosis/v2/assessments/{assessmentId}` | `v2.py`         | Replace checked criteria and explicit clinician decision using `If-Match`. | `psychiatrist` | **required** |
| GET    | `/api/diagnosis/v2/assessments/{assessmentId}/audit` | `v2.py`   | Fetch chronological assessment provenance. | `psychiatrist` \| `admin` | — |
| GET    | `/api/diagnosis/v2/encounters/{encounterId}/assessment-snapshot` | `v2.py` | Fetch Treatment Plan's encounter-bound source snapshot. | `psychiatrist` \| `admin` | — |
| GET    | `/api/diagnosis/v2/encounters/{encounterId}/assessments/latest` | `v2.py` | Fetch the latest version of the encounter-bound assessment. | `psychiatrist` \| `admin` | — |

**Route-order invariant (HANDOFF §9.4)**: literal paths (`/diagnosis/_meta`,
`/diagnosis/_csrf`, and the `/internal/...` discovery + audit routes) MUST
be registered before the parameterized `/{code}` family on the composed
router, or FastAPI captures `_meta` / `_csrf` into `{code}` and 404s. The
`/internal/...` routes carry their own path parameters (`{moduleId}`,
`{code}`) but live under a distinct `/internal/...` prefix so they do
not collide with `/{code}`. Don't reorder the `for _sub in ()` tuple in
`api.py` (HANDOFF §9.10).

---

## 2.1. Diagnosis assessment v2

V2 is the canonical UUID interface. New URLs contain only `assessmentId` or
`encounterId` UUIDs; patient-code aliases are never accepted in v2 paths.
Legacy code routes remain compatibility adapters and use the same server
`evaluate()` function and clinician-authority semantics.

`POST /api/diagnosis/v2/assessments` requires `X-Schema-Version: 2.0.0`,
`Idempotency-Key`, psychiatrist auth, and CSRF. Body:

```json
{"patientId":"<uuid>","encounterId":"<uuid>"}
```

Before persistence, Diagnosis fetches both UUID resources from Add New Patient
v2 and verifies `encounter.patientId == patientId`. Unknown resources return
404, dependency/schema failure returns 503/502, and ownership mismatch returns
409. Repeating the same principal/key/body returns the original assessment and
`Idempotency-Replayed: true`; changed body returns
`COMMON_IDEMPOTENCY_KEY_REUSED`.

Assessment responses validate against
`schema/diagnosis-assessment-v2.schema.json#/$defs/assessment` and contain:
assessment, Patient, and Encounter UUIDs; checked criteria; server evaluation;
nullable explicit clinician decision (`confirmed` or `bypass`) with actor and
time; rule/schema versions; status; resource version; UTC create/update times;
and actor provenance. `evaluation.met` remains evidence only and never creates
or rewrites a clinician decision. A `confirmed` decision is invalid when the
server evaluation is unmet; `bypass` remains the explicit valid path whether
criteria evaluate true or false.

`PUT /api/diagnosis/v2/assessments/{assessmentId}` requires schema header,
psychiatrist auth, CSRF, and the strong ETag from GET/init in `If-Match`.
Missing precondition returns 428; stale precondition returns 412. Each accepted
write increments `resourceVersion` and appends an attributable audit snapshot.
The audit endpoint returns events oldest first. The encounter snapshot endpoint
returns the same schema-versioned resource and ETag for Treatment Plan without
copying or mutating Diagnosis state.

`GET /api/diagnosis/v2/encounters/{encounterId}/assessments/latest` is the
canonical latest-read route. Because Diagnosis permits one assessment per
Encounter in interface 2.0.0, it returns that assessment's current version and
strong ETag without mutation. The older `assessment-snapshot` route delegates
to the same read operation and remains the Treatment Plan compatibility name.

On upgrade, the ordered `diagnosis-assessment-v2` storage migration stages every
previously unseen code-keyed session in a module-owned quarantine table. A
legacy code cannot supply an Encounter UUID, so the migration never guesses one
from patient code, timestamps, or row order. An explicit resolver must provide
canonical Patient and Encounter UUIDs; successful resolution atomically creates
the assessment, a versioned `migrated` audit snapshot, and a legacy compatibility
link. Invalid, missing, conflicting, or unavailable identity remains quarantined
with the original source snapshot and a typed reason. Source `sessions` rows are
retained for rollback and unresolved legacy compatibility; linked legacy routes
read and write only the canonical assessment. Rerunning staging or resolution is
idempotent.

V2 uses RFC 9457 problem bodies without patient identifiers. Full route and
schema definitions are published in
`schema/diagnosis-assessment-v2.openapi.json` and
`schema/diagnosis-assessment-v2.schema.json`.

---

## 3. Browser page — `GET /`

Serves the embeddable module UI HTML (`static/index.html`; no build step).
Stamps a fresh signed CSRF token into both a `<meta name="csrf-token">`
tag in the page head and a matching `csrf` cookie on the response so the
JS can echo it back on the next write without an extra fetch.

### Request
No body and no patient query parameters. The host supplies canonical Patient
and Encounter UUIDs directly to the embedded constructor; the page never reads
patient context from or writes it to browser location/history.

### Response
- **200** — `Content-Type: text/html; charset=utf-8`. Body is the
  single-file SPA. The injected `<meta name="csrf-token" content="...">`
  tag appears before `<meta name="viewport">`.
- **Set-Cookie**: `csrf=<signed-token>; Path=/; SameSite=Lax` (and
  `Secure` when `DIAGNOSIS_CSRF_SECURE=1`).
- Under `DIAGNOSIS_AUTH_BYPASS=1` (self-check / headless tests), the
  meta/cookie injection is skipped so the served page is byte-clean for
  asserts.

### Errors
- **401** — not authenticated (`{"detail": "Not authenticated"}`).
- **403** — authenticated but neither `psychiatrist` nor `admin`.

The page contract is a single mount point `#diagnosis-root` and
`window.createDiagnosisModule({root, apiBaseUrl, patientId, encounterId,
embedded})`. It returns `mount()`, `unmount()`, and
`setAssessmentContext({patientId, encounterId})`. Patient and Encounter values
must be canonical UUIDs supplied by the host. The UI calls only v2 assessment
routes, never places aliases in a URL, never mutates host navigation, renders
only server-returned evaluation, and requires a separate explicit click for a
`confirmed` or `bypass` clinician decision. It retains the last persisted
server state and exposes a focused visible alert when initialization or update
persistence fails. `unmount()` aborts in-flight requests, clears timers,
removes every registered listener, and clears only the supplied root. The
contract is locked by `test_embed.py`; the CSRF meta stamp remains locked by
`test_csrf.test_html_page_carries_meta_token`.

---

## 4. Liveness — `GET /health`

Cheap "is the process up" probe. Does NOT check dependencies — use
`/ready` for that (HANDOFF §9.11).

### Response
- **200** — `{"ok": true, "module": "diagnosis"}`

No auth. No CSRF. Never 503; never raises.

---

## 5. Readiness — `GET /ready`

Module-local readiness probe. Answers "are this module's dependencies
configured so a clinical request won't immediately 401 / 422." A load
balancer gates traffic here, not on `/health`.

### Response
- **200** when `ok == true`; **503** when `ok == false`. The body is
  the same in both cases:

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

`ok` is the AND of every check's `ok`. The probe **never leaks secrets**
and **never calls a live service** (HANDOFF §9.11):

- **`db`** — probes the live `DiagnosisStore` with `SELECT 1` on the
  connection the route handlers reuse. Never echoes the on-disk DB
  path. A SQLite fault collapses to `{"ok": false}` (no traceback in
  the body).
- **`auth`** — verifies `AUTH_BASE_URL` is non-empty AND the
  `DIAGNOSIS_AUTH_BYPASS=1` shim is off. `bypass: true` is the **deploy
  alarm** that fires when the shim is left on in production (a
  production readiness gate MUST fail on it). Never calls the auth
  service — it needs the user's `Cookie`, so a cookieless probe would
  401 / surface the configured URL.
- **`patient`** — opt-in adapter. When `DIAGNOSIS_PATIENT_LOOKUP != "1"`
  (default), reports `{"enabled": false, "configured": true}` as a clean
  "skipped" state. When enabled, verifies `PATIENT_BASE_URL` is
  non-empty.

No auth. No CSRF. Never raises. Locked by `test_readiness.py`.

---

## 6. Dashboard discovery seam

All routes in this seam live in `dashboard.py`. None mutate patient
state; none require CSRF. Auth policy is `psychiatrist` OR `admin`
(read policy — admins audit, never mutate; HANDOFF §9.10).

### 6.1. `GET /diagnosis/_meta`

Criteria tree + the `rules` contract the browser page derives its
optimistic display from. The `rules` object is the SAME primitives
`evaluate()` reads — the UI MUST NOT reimplement the DSM logic in JS
(HANDOFF §9.12). Locked against the engine across every id subset by
`test_unittest.test_meta_rules_match_engine_every_subset`.

#### Response
- **200** —

```json
{
  "criteria": [
    {"id": "A1", "group": "Criterion A - Characteristic symptoms",
     "text": "Delusions (fixed false beliefs resistant to evidence).", "core": true},
    {"id": "A2", "group": "Criterion A - Characteristic symptoms",
     "text": "Hallucinations (...) .", "core": true},
    {"id": "A3", "group": "Criterion A - Characteristic symptoms",
     "text": "Disorganized thinking / speech (...).", "core": true},
    {"id": "A4", "group": "Criterion A - Characteristic symptoms",
     "text": "Grossly disorganized or catatonic behaviour.", "core": false},
    {"id": "A5", "group": "Criterion A - Characteristic symptoms",
     "text": "Negative symptoms: ...", "core": false},
    {"id": "A6", "group": "Criterion A - Characteristic symptoms",
     "text": "Symptoms present for a significant portion of 1 month (...).",
     "core": false, "duration": true},
    {"id": "B1", "group": "Criterion B - Functioning", "text": "...", "core": false, "guard": "B"},
    {"id": "C1", "group": "Criterion C - Schizoaffective exclusion", "text": "...", "core": false, "guard": "C"},
    {"id": "D1", "group": "Criterion D - Substance / medical exclusion", "text": "...", "core": false, "guard": "D"}
  ],
  "rules": {
    "symptom_ids":      ["A1", "A2", "A3", "A4", "A5"],
    "core_ids":         ["A1", "A2", "A3"],
    "duration_id":      "A6",
    "guard_ids":        ["B1", "C1", "D1"],
    "symptom_threshold": 2,
    "core_threshold":   1
  }
}
```

Each criterion object: `id` (stable), `group` (clinician-facing label),
`text` (paraphrase), `core` (boolean), and optionally `duration` (A6) or
`guard` (`"B"`/`"C"`/`"D"` on B1/C1/D1). The `id` strings are part of
the wire contract — renaming is a breaking change (HANDOFF §9.1).

#### Errors
- **401** — not authenticated.
- **403** — authenticated but neither `psychiatrist` nor `admin`.

### 6.2. `GET /diagnosis/_csrf`

Mint a fresh signed double-submit CSRF token. Non-browser clients call
this once, then pass the returned value as both the `csrf` cookie and
the `X-CSRF-Token` header on subsequent writes (see §9). Browser
clients get the same token stamped into `GET /` instead.

#### Response
- **200** — body: `{"token": "<raw32hex>.<hmac_sha256_hex>"}`
- **Set-Cookie**: `csrf=<token>; Path=/; SameSite=Lax` (`Secure` when
  `DIAGNOSIS_CSRF_SECURE=1`; `HttpOnly=false` so JS can read it).

The token does NOT survive a server restart by design. Multi-worker
deployments MUST pin `DIAGNOSIS_CSRF_SECRET` so a token minted by one
worker validates on another (HANDOFF §9.8). Tests pin the secret via
`csrf.reset_secret_for_tests`.

#### Errors
- **401**, **403** — same role gate as `_meta`.

### 6.3. `GET /internal/dashboard/module-routes/{moduleId}`

Dashboard module-route discovery. The larger Insight Dashboard learns
how to launch each mounted module from this single URL pattern. The
diagnosis module answers for `moduleId == <settings.module_id>` (default
`"diagnosis"`); any other id falls through to a clean 404 so a
misrouted call is loud but does not leak a stack trace.

#### Path parameters
- `moduleId` — string. Compared verbatim against the settings-derived
  module id (default `"diagnosis"`, derived from
  `DIAGNOSIS_MODULE_BASE_PATH` — see §10).

#### Response
- **200** for the matching id —

```json
{
  "moduleId":    "diagnosis",
  "title":       "Diagnosis",
  "description": "DSM-5-TR schizophrenia criteria checklist.",
  "launch":      {"href": "/modules/diagnosis"},
  "routes":      {"self":    "/diagnosis/_meta",
                  "csrf":    "/diagnosis/_csrf",
                  "session": "/diagnosis/{code}"}
}
```

`launch.href` derives from `module_base_path` so a non-default mount
prefix flows through to the descriptor (HANDOFF §9.10). The
`routes.session` value is the literal pattern string `/diagnosis/{code}`
— **not** a substituted URL. Dashboard depends on every key.

#### Errors
- **404** — `moduleId` does not match: `{"detail": "Unknown module id"}`.
- **401**, **403** — same role gate.

Locked by `test_discovery.py` (happy + 404 paths).

### 6.4. `GET /internal/diagnosis/audit/{code}`

Audit-log seam — the persisted local audit trail for `code`, exposed
read-only for the future Insight Logs module. Each decision-bearing PUT
on `/diagnosis/{code}` is persisted as an audit event via
`_dump_for_audit` → `store.audit_snapshot` (HANDOFF §9.14), so this
route returns whatever has accumulated rather than snapshotting on
demand.

#### Path parameters
- `code` — free-text local session key (NOT the canonical patient id).
  Lives under `/internal/diagnosis/...` so its `{code}` parameter does
  NOT collide with the per-patient `/{code}` family.

#### Response
- **200** for any code, known or not —

```json
{
  "code": "P-0427-A",
  "snapshots": [
    {"code": "P-0427-A", "patient_id": "...", "checked": ["A1"], "decision": null,
     "created_at": 1718000000, "updated_at": 1718000005},
    {"code": "P-0427-A", "patient_id": "...", "checked": ["A1", "A2", "A6", "B1"],
     "decision": "confirmed", "created_at": 1718000000, "updated_at": 1718000010}
  ]
}
```

`snapshots` is ordered oldest-first (ascending `audit.id`). Each
snapshot is the JSON of the source session row at audit-write time —
`decision` + `checked` ids verbatim, NO `evaluation` key — so an
audit row can never be read as a server-derived auto-diagnosis
(HANDOFF §6.1 extends through the audit trail). An unknown /
never-audited code yields an empty `snapshots` list, NOT a 404 —
`code` is the free-text local session key, and an empty trail is a
legitimate state. Init alone does NOT audit (empty-session creation
is not a clinician decision).

#### Errors
- **401**, **403** — same role gate.

Locked by `test_unittest.TestAuditSeam` + `test_routes.py`.

---

## 7. Per-patient diagnosis REST seam

All routes in this seam live in `diagnosis_api.py`. `{code}` is the
free-text patient code the clinician typed — it is the LOCAL session
key, NOT the canonical INSIGHT patient id (see §11 (Patient Identity)).

### 7.1. `POST /diagnosis/{code}/init`

Create an empty session for a patient code. Idempotent: if a session
already exists, returns `{"created": false}` (NOT 409). The frontend
POSTs `/init` before GET to guarantee a session exists.

#### Path parameters
- `code` — free-text patient code (local session key).

#### Request body
None.

#### Response
- **200** —
```json
{"created": true, "patient_id": "<canonical-id-or-code>"}
```

`patient_id` is the canonical INSIGHT registry id when
`DIAGNOSIS_PATIENT_LOOKUP=1` is set, or the free-text `code` itself
when the adapter is disabled (default). It is NEVER blank.

#### Errors
- **400** — `code` is empty / whitespace: `{"detail": "Patient code required"}`.
- **401** — not authenticated.
- **403** — authenticated but not `psychiatrist` (writes are clinician-only),
  OR CSRF token missing/mismatch/invalid.
- **422** — patient lookup enabled and the registry 404'd, was
  unreachable, or returned a payload with no canonical `id`.
  `{"detail": "Unknown patient code: 'P-XXX'"}` or
  `{"detail": "Patient registry unavailable for code 'P-XXX'"}` or
  `{"detail": "Patient registry returned no canonical id for code 'P-XXX'"}`.

### 7.2. `GET /diagnosis/{code}`

Current checked state + the live `evaluation` for a patient. Read-only;
no CSRF. 404 if the code has never been seen — the frontend POSTs
`/init` first to prevent this. Contract: "caller creates sessions via
PUT/init before GET" (HANDOFF §10).

#### Path parameters
- `code` — free-text patient code (local session key).

#### Response
- **200** —
```json
{
  "code": "P-0427-A",
  "patient_id": "<canonical-id-or-code>",
  "checked": ["A1", "A2", "A6", "B1"],
  "decision": "confirmed",
  "evaluation": {
    "met": true,
    "a_count": 2,
    "core_count": 2,
    "failures": [],
    "reason": "Criterion A met.",
    "checked": ["A1", "A2", "A6", "B1"]
  },
  "updated_at": 1718000010
}
```

The `evaluation` object shape is the `RESULT_FIELDS` contract
(`("met", "a_count", "core_count", "failures", "reason", "checked")`).
Don't drop or rename keys without bumping the Insight integration
(HANDOFF §9.7). `decision` is the clinician's recorded voice
(`"confirmed"` | `"definite"` | `null`).

#### Errors
- **404** — no session for `code`: `{"detail": "Unknown patient code: P-XXX"}`.
- **401** — not authenticated.
- **403** — authenticated but neither `psychiatrist` nor `admin`.

### 7.3. `PUT /diagnosis/{code}`

Persist the clinician's checked criteria + final decision. Returns the
new evaluation. The web page calls this on every checkbox toggle
(debounced 350ms) AND on the explicit decision buttons. `"definite"`
bypasses the criteria-met requirement per clinician authority
(HANDOFF §6 / §6.1); the server MUST NOT consult `met` on the bypass
path.

After `store.put` succeeds, the route calls `_dump_for_audit(code)` so
every decision-bearing PUT persists a local audit event (HANDOFF §9.14).
The audit snapshot is the source row — NO `evaluation` key — so it
cannot be mistaken for a server-derived auto-diagnosis.

#### Path parameters
- `code` — free-text patient code (local session key).

#### Request body
```json
{
  "checked":  ["A1", "A2", "A6", "B1"],
  "decision": "confirmed"
}
```
- `checked` — array of criterion `id` strings. Duplicates are de-duped
  (order preserved) at the API layer.
- `decision` — `"confirmed"` | `"definite"` | `null`.
  - `"confirmed"` — psychiatrist affirms criteria met (requires the
    clinician's affirmative click; the server does NOT auto-set this
    from `met == true`).
  - `"definite"` — psychiatrist bypasses the checklist. Always valid,
    regardless of `met`. Records "psychiatrist overrides the
    checklist" per the institution's protocol.
  - `null`/omitted — checkbox-toggle write with no decision change.

Validation is via the `Submission` pydantic model
(`diagnosis_api.Submission`); a body that fails pydantic validation is
rejected with `422` BEFORE the auth / CSRF deps run by FastAPI.

#### Response
- **200** —
```json
{
  "code": "P-0427-A",
  "patient_id": "<canonical-id-or-code>",
  "evaluation": {
    "met": true,
    "a_count": 2,
    "core_count": 2,
    "failures": [],
    "reason": "Criterion A met.",
    "checked": ["A1", "A2", "A6", "B1"]
  },
  "decision": "confirmed",
  "updated_at": 1718000010
}
```

`evaluation.met` reports the honest DSM result regardless of `decision`
— a `"definite"` bypass on a not-met checklist persists `decision ==
"definite"` AND `evaluation.met == false` (the API does NOT rewrite
`met` to match the bypass). A `"confirmed"` recorded earlier is NOT
retro-downgraded by a later PUT whose checklist no longer meets A.
Locked by `test_unittest.TestClinicianAuthority` (HANDOFF §6.1).

#### Errors
- **400** — `code` is empty / whitespace: `{"detail": "Patient code required"}`.
- **401** — not authenticated.
- **403** — not `psychiatrist`, OR CSRF token missing/mismatch/invalid.
- **422** — pydantic body validation failed (e.g. `decision` not in
  the allowed set), OR patient lookup enabled and the registry failed
  the same way as `/init` (§7.1). Body shape depends on the failing
  path — pydantic returns its own `{"detail": [...]}` shape; the
  patient adapter returns `{"detail": "..."}`.

---

## 8. Auth

The module delegates trust to the central Insight auth service. It
does NOT decode JWTs or read the auth database. Two role dependencies
live in `deps.py` (HANDOFF §3):

| Dependency                       | Allowed roles                | Used by                                                    |
|----------------------------------|------------------------------|------------------------------------------------------------|
| `require_psychiatrist`           | `psychiatrist`               | `POST /init`, `PUT /{code}` (writes — clinician-only).     |
| `require_psychiatrist_or_admin`  | `psychiatrist` \| `admin`    | `GET /`, `GET /_meta`, `GET /_csrf`, discovery, audit, `GET /{code}`. |

Admins audit, never mutate clinical state.

### Trust call
For every protected request the module calls
`GET {AUTH_BASE_URL}/api/auth/v2/session` with the incoming `Cookie`
header and reads the JSON response:

```json
{
  "authenticated": true,
  "authorized": true,
  "interfaceVersion": "2.0.0",
  "session": {"id": "<uuid>", "active": true, "expiresAt": "<UTC date-time>"},
  "user": {"id": "<uuid>", "username": "clinician", "role": "psychiatrist"},
  "gates": {"passwordChangeRequired": false, "disclaimerRequired": false, "disclaimerVersion": "<version>"}
}
```

- Missing, non-authenticated, unauthorized, gated, expired, non-v2, non-UUID,
  or non-canonical-role response → **401** `{"detail": "Not authenticated"}`.
- Authenticated but missing the required role → **403** `{"detail": "Forbidden"}`.
- Auth service unreachable / non-JSON / timed out (`AUTH_TIMEOUT_S`,
  default 2.0s) → **401** fail-closed (does not leak the transport
  error to the caller).

Config (see §10): `AUTH_BASE_URL` (default `http://localhost:9000`),
`AUTH_TIMEOUT_S` (default `2.0`).

### `DIAGNOSIS_AUTH_BYPASS=1` shim
The in-process self-check and headless tests set this env to short BOTH
the role deps (returns a fake `psychiatrist`+`admin` session) AND the
CSRF dep. It MUST be off in production — readiness surfaces
`checks.auth.bypass == true` as the deploy alarm when it is left on
(§5). Wired in `deps.py` at import time, so setting the env AFTER the
first `diagnosis.*` import does NOT re-wire the deps (HANDOFF §10).

---

## 9. CSRF

Signed double-submit CSRF (OWASP pattern) for the two write routes
(`POST /init`, `PUT /{code}`). Read routes are exempt. Implemented in
`csrf.py`.

### Token format
`<raw32hex>.<hmac_sha256_hex>` where `raw` is 32 hex chars
(`secrets.token_hex(16)`) and the HMAC is keyed by the per-process
secret (`settings.csrf_secret` or a fresh random
`secrets.token_bytes(32)`).

### Protocol
1. Client fetches a token via `GET /diagnosis/_csrf` (or scrapes
   `<meta name="csrf-token">` from `GET /` for the browser path). The
   token is returned in the JSON body AND set as the `csrf` cookie.
2. On every write the client sends BOTH:
   - `Cookie: csrf=<token>`
   - `X-CSRF-Token: <token>`
3. `csrf.require_csrf` (FastAPI dep) verifies all three: cookie ===
   header (constant time), cookie HMAC valid, header HMAC valid.
   Fail-closed **403** on any mismatch:
   - `{"detail": "CSRF token missing"}` — cookie or header absent.
   - `{"detail": "CSRF token mismatch"}` — cookie !== header.
   - `{"detail": "CSRF token invalid"}` — bad signature.

### Cookie flags
`Path=/`, `SameSite=Lax`, `HttpOnly=false` (JS may read it). `Secure`
flipped on by `DIAGNOSIS_CSRF_SECURE=1` (set behind TLS). The cookie
name is `csrf`; the header name is `X-CSRF-Token` (constants
`csrf.COOKIE_NAME`, `csrf.HEADER_NAME`).

### Lifecycle & multi-worker
The HMAC secret is per-process random by default — a token minted by
one worker does NOT validate on another, and a server restart
invalidates all outstanding tokens (clients re-fetch on next `GET /`
or `GET /_csrf`). Multi-worker / multi-process deployments MUST set
`DIAGNOSIS_CSRF_SECRET` (env) so all workers share the key (HANDOFF
§9.8). Tests pin the secret via `csrf.reset_secret_for_tests`.

### Auth-before-CSRF ordering
On `init` and `put` the deps are declared
`Depends(require_psychiatrist)` THEN `Depends(require_csrf)`. FastAPI
runs deps in declared order, so an unauthenticated caller gets a 401
and never learns a CSRF token exists. Don't reorder them (HANDOFF
§9.8).

### Bypass shim
`DIAGNOSIS_AUTH_BYPASS=1` (same gate as auth) shorts the CSRF dep so
the in-process self-check drives writes without minting tokens
(HANDOFF §9.8). Never set in production.

Locked by `test_csrf.py` (no-token, header-only, cookie-only, mismatch,
bad signature, valid path, mint-sets-cookie, HTML-carries-meta,
bypass-honored).

---

## 10. Configuration (env knobs → `Settings`)

Single source: `diagnosis/config.py :: Settings` (frozen dataclass) +
`settings` singleton. Read ONCE at import time; production code never
writes. The lone exception to "consumer reads `settings.*`": `deps.py`
re-reads `DIAGNOSIS_AUTH_BYPASS` at import (the pre-import ordering
contract, HANDOFF §10), and `readiness._check_auth` /
`_check_patient` read the module-level `AUTH_BASE_URL` /
`PATIENT_BASE_URL` globals at call time so a test-only swap surfaces
without re-importing. Don't add a fresh `os.environ.get` in another
module — extend `Settings` + `_load` instead.

| Env var                       | `Settings` field     | Default                     | Affects                                                              |
|-------------------------------|----------------------|-----------------------------|----------------------------------------------------------------------|
| `DIAGNOSIS_DB_PATH`           | `db_path`            | `diagnosis_store.db`        | SQLite file path for `DiagnosisStore`.                               |
| `AUTH_BASE_URL`               | `auth_url`           | `http://localhost:9000`     | Insight auth service base URL.                                       |
| `AUTH_TIMEOUT_S`              | `auth_timeout_s`     | `2.0`                       | Auth call timeout (fail fast).                                       |
| `PATIENT_BASE_URL`            | `patient_url`        | `http://localhost:9000`     | "Add New Patient" registry base URL.                                 |
| `PATIENT_TIMEOUT_S`           | `patient_timeout_s`  | `2.0`                       | Patient lookup timeout.                                               |
| `DIAGNOSIS_PATIENT_LOOKUP`    | `patient_lookup`     | `0` (disabled)             | `1` → enforce canonical patient id lookup on writes.                |
| `DIAGNOSIS_CORS_ORIGINS`      | `cors_origins`       | `*`                         | Comma list; standalone `app.py` CORS middleware. Ignored when mounted. |
| `DIAGNOSIS_AUTH_BYPASS`       | `mock_auth`          | `0` (off)                   | `1` → shorts auth + CSRF deps AND surfaces as readiness deploy alarm. Wired in `deps.py` at import. |
| `DIAGNOSIS_CSRF_SECRET`       | `csrf_secret`        | `None` → per-process random| HMAC key for CSRF tokens. MUST be set for multi-worker deploys.        |
| `DIAGNOSIS_CSRF_SECURE`       | `csrf_secure`        | `0` (off)                   | `1` → `Secure` flag on the `csrf` cookie (set behind TLS).           |
| `DIAGNOSIS_MODULE_BASE_PATH`  | `module_base_path`   | `/diagnosis`                | Mount prefix. Last path segment is `module_id`; `launch_href` = `/modules/<id>`. |
| `DIAGNOSIS_HOST`              | `host`               | `0.0.0.0`                   | Standalone uvicorn bind host.                                        |
| `DIAGNOSIS_PORT`              | `port`               | `8000`                       | Standalone uvicorn bind port.                                        |

Derived:
- `module_id` — `module_base_path.rstrip("/").rsplit("/", 1)[-1]` or
  `"diagnosis"` (so `/tools/dx` → `"dx"`).
- `launch_href` — `f"/modules/{module_id}"`.

Locked by `test_config.py` + `_config_selfcheck`.

---

## 11. Invariants — break these and you've changed the contract

Mirrors HANDOFF §9. Cited for the wire contract; consult HANDOFF for
the implementation-level detail.

1. **`CRITERIA` ids are stable.** `A1`–`A6`, `B1`, `C1`, `D1`. Clients
   store them; the JS binds via `data-id`. Renaming = breaking change.
2. **`evaluate(checked_ids)` is pure.** No I/O, no side effects. A
   client consuming `evaluation` from GET/PUT is consuming a pure
   projection of `checked`.
3. **`Submission.decision ∈ {"confirmed", "definite", None}`.** PUT
   MUST accept `"definite"` even when `met` is false (the bypass
   path). See §13 (Clinician Authority).
4. **Route declaration order**: literal paths (`/diagnosis/_meta`,
   `/diagnosis/_csrf`, the two `/internal/...` routes) before the
   parameterized `/{code}` family. Inversion breaks `_meta` / `_csrf`.
5. **Six self-checks pass before boot.** `criteria._demo`,
   `store._store_selfcheck`, `patient._patient_selfcheck`,
   `readiness._readiness_selfcheck`, `config._config_selfcheck`,
   `api._http_selfcheck`. A failing assert means the server won't
   boot. Don't disable them in `__main__.py`.
6. **The web page never decides without the clinician.** The model's
   `met` only *enables* the confirm button; it never auto-sends a
   decision. `met == true` does NOT coerce `decision` to
   `"confirmed"`.
7. **`RESULT_FIELDS` is the acceptance contract** for GET/PUT
   `evaluation` objects. Don't drop / rename keys without bumping the
   Insight integration.
8. **CSRF on writes.** `POST /init` and `PUT /{code}` require the
   signed double-submit token. Don't add a state-mutating route
   without wiring `Depends(require_csrf)`.
9. **Canonical patient id is authoritative.** `sessions.patient_id`
   is set by `patient.resolve_patient` only — never assigned the
   free-text `{code}` from a route handler. The `{code}` stays the
   local session key; the cross-module identity is the registry id.
   A row whose `patient_id == code` is fine when lookup is disabled
   (default) — a route handler bypassing the adapter is a contract
   break.
10. **Seam split is a contract.** `page.py` owns the browser page;
    `dashboard.py` owns discovery + audit-log + the audit-snapshot
    hook; `diagnosis_api.py` owns per-patient mutation; `deps.py`
    owns the shared store + role/CSRF deps. Don't re-instantiate
    `DiagnosisStore` in a seam or re-write the role/CSRF deps in a
    route module.
11. **Readiness is module-local and never leaks secrets.** Never
    raises, never calls a live service, never echoes a URL/path. The
    HTTP route returns 200 when `ok` else 503. `bypass: true` on the
    auth check is the deploy alarm.
12. **Server evaluation is the single source of truth for the UI's
    optimistic display.** `GET /_meta` returns a `rules` object
    exposing the same primitives `evaluate()` reads. The browser
    MUST NOT reimplement the DSM logic in JS — it projects from
    `rules` + the checked ids. Locked by
    `test_meta_rules_match_engine_every_subset`.
13. **The web page is an embeddable module UI, not a standalone
    shell.** `window.createDiagnosisModule({root, apiBaseUrl})` is
    the one entry point. No baked standalone topbar, no host-nav
    placeholder. The standalone `GET /` bootstraps that fn against
    `document.body` with `embedded: false`.
14. **Audit event seam**: every decision-bearing PUT persists a local
    audit event via `_dump_for_audit` → `store.audit_snapshot`. The
    dashboard `GET /internal/diagnosis/audit/{code}` exposes the
    trail read-only (oldest first). The snapshot is the source row
    — NO `evaluation` key. An unknown / never-audited code yields an
    empty `snapshots` list, NOT a 404. Init alone does NOT audit.

---

## 12. Patient identity (canonical id from "Add New Patient")

``{code}`` in the route path is the local session key only — it is NOT
the canonical patient id. Before a write route (`POST /init`,
`PUT /{code}`) persists a row, the module calls the INSIGHT "Add New
Patient" registry at `GET {PATIENT_BASE_URL}/api/patients/lookup?code=...`
(env `PATIENT_BASE_URL`, default `http://localhost:9000`) to align the
row's `patient_id` with the registry's canonical `patient.id`.

### Registry response shape
```json
{
  "id":           "<canonical-patient.id>",
  "patient_code": "<canonical-patientCode>",
  "display_name": "Ada Lovelace"            // or null
}
```

The diagnosis module forwards the incoming `Cookie` (same trust
boundary as `auth.py`) and reads only this JSON. It NEVER reads the
patient DB directly and NEVER imports from the primitives app.

### Fault mapping (all → 422, never a stack trace)
- Registry **404** → `{"detail": "Unknown patient code: 'P-XXX'"}`.
- Registry **unreachable / non-JSON / timeout** (`PATIENT_TIMEOUT_S`,
  default 2.0s) → `{"detail": "Patient registry unavailable for code 'P-XXX'"}`.
- Registry **200 but missing canonical `id`** →
  `{"detail": "Patient registry returned no canonical id for code 'P-XXX'"}`.

A row whose `patient_id` is blank is NEVER written — that would
re-introduce the diagnosis-local free-text bug under a different name.

### Opt-in
`DIAGNOSIS_PATIENT_LOOKUP` (default unset / not `"1"`):
- **disabled** — adapter short-circuits; returns
  `Patient(id=code, patient_code=code, display_name=code)`. The
  row's `patient_id` equals the free-text `code`. This preserves
  the prior diagnosis-local behaviour for the self-check and
  offline tests.
- **`1`** — real lookup enforced. The 422 paths above surface.

`{code}` is STILL the local session key when lookup is enabled — the
REST contract does NOT change. Only `sessions.patient_id` does. Don't
add a `?patient_id=...` query param or re-route on canonical id.

Contract spec: `diagnosis/patient.py`. Tests: `test_patient.py` (happy
+ fault paths via a fake in-process registry). The adapter is a
mirror of `auth.py` (pure stdlib `urllib`, frozen `Patient`
dataclass, fail-closed HTTPException, no DB imports).

---

## 13. Clinician Authority (the safety contract)

From DESIGN.md §6 and §10 (referenced in code comments); locked by
`test_unittest.TestClinicianAuthority`, which the boot self-check
loads (HANDOFF §6.1).

- **The model never makes the final diagnosis.** `evaluate()` returns
  a boolean `met` field — that is decision **support**, not a
  decision.
- **`"confirmed"`** (`decision: "confirmed"`) — psychiatrist affirms
  "yes, criteria met, this is my diagnosis." Requires an explicit
  clinician click; the server MUST NOT auto-set this from `met ==
  true`. The client-side `disabled` guard on the confirm button is a
  UX cue, NOT a server-side check.
- **`"definite"`** (`decision: "definite"`) — psychiatrist bypasses
  the checklist. Always valid, regardless of `met`. Records
  "psychiatrist overrides the checklist" per the institution's
  protocol. The server MUST NOT consult `met` on the bypass path.
- **`evaluation.met` reports the honest DSM result regardless of
  `decision`.** A `"definite"` on a not-met checklist persists
  `decision == "definite"` AND `evaluation.met == false`. A
  `"confirmed"` recorded earlier is NOT retro-downgraded by a later
  PUT whose checklist no longer meets A. No server-side "reconcile
  decision against `met`" logic may exist.

If you add logic that turns the model's `met` into an automatic
diagnosis, you have broken the core safety contract of this module —
and the boot self-check will refuse to start the server.

---

## 14. Source-of-truth tests

Per HANDOFF §8. Don't introduce a `pytest` dep without checking
whether the Insight pytest already exists.

| Concern                              | Test file                                | Suite / function                                                     |
|--------------------------------------|------------------------------------------|----------------------------------------------------------------------|
| DSM rules                            | `test_unittest.py`                       | `TestCriteriaRules`                                                  |
| REST contract + persistence          | `test_unittest.py`                       | `TestRestContract`                                                   |
| Audit event seam                     | `test_unittest.py`                       | `TestAuditSeam`                                                      |
| Clinician authority (model-never-decides) | `test_unittest.py`                  | `TestClinicianAuthority`                                             |
| Auth rejection / CSRF / persistence / patient identity (dep-level) | `test_unittest.py` | `TestAuthRejection` / `TestCSRF` / `TestPersistence` / `TestPatientIdentity` |
| Auth enforcement (HTTP)              | `test_auth.py`                            | whole harness (fake auth service)                                    |
| CSRF gate (HTTP)                     | `test_csrf.py`                            | whole harness (fake auth + pinned secret)                            |
| Settings adapter                     | `test_config.py`                          | whole harness (env snapshot + consumer wiring)                       |
| Route seam split + order             | `test_routes.py`                          | whole harness                                                         |
| Dashboard discovery                  | `test_discovery.py`                       | whole harness (happy + 404)                                          |
| Canonical patient identity           | `test_patient.py`                         | whole harness (fake registry)                                        |
| Readiness probe                       | `test_readiness.py`                       | whole harness (function + HTTP 200/503 + no-leak)                     |
| Embeddable module UI                 | `test_embed.py`                           | whole harness (`createDiagnosisModule` contract)                      |

Run the full surface:

```bash
python -m test_unittest    # rules + REST + auth + CSRF + persistence + patient (stdlib unittest)
python -m test_config     # settings adapter
python -m test_routes      # seam split
python -m test_auth        # role enforcement
python -m test_csrf       # CSRF gate
python -m test_discovery  # Dashboard discovery
python -m test_patient     # canonical patient identity
python -m test_readiness  # readiness probe
python -m test_embed      # embeddable UI
```
