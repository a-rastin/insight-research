# HANDOFF — `diagnosis` module

A guide for any future LLM (or human) that needs to read, extend, or integrate
this module. Read this first; it maps the codebase faster than the code itself.

---

## 1. What this module is

A **DSM-5-TR schizophrenia criteria checklist** for the *Insight* clinical
decision support tool. The clinician checks off criteria; the module reports
whether the DSM-5-TR rules are satisfied. **The model never decides.** The
psychiatrist confirms ("Diagnosis is clear") or bypasses ("Diagnosis is clear
(bypass)"). This is a hard design rule — see §6 below.

It is a **deep module** in John Ousterhout's sense: a tiny REST interface
hiding the entire DSM-5-TR evaluation. Two deployment modes:

1. **Standalone** — `python -m diagnosis` boots a uvicorn server with the
   web page at `/`.
2. **Mounted** — `from diagnosis import router; app.include_router(router, prefix="/diagnosis")`
   inside the larger Insight FastAPI app. The HTML page calls same-origin API,
   so no CORS / absolute URLs needed.
Scope: **research prototype**. Sessions persist to SQLite via
``store.DiagnosisStore`` (env ``DIAGNOSIS_DB_PATH``); keyed by patient
code. The row's ``patient_id`` column binds to the canonical INSIGHT
``patient.id`` from the "Add New Patient" registry when
``DIAGNOSIS_PATIENT_LOOKUP=1`` is set (see ``patient.py``); default
disabled preserves the prior diagnosis-local identity so the self-check
and offline tests don't need a live registry.

---

## 2. Repo layout

```
diagnosis/                      <- repo root (git: one commit "Innit")
├── README.md                   <- user-facing interface contract (read it)
├── docs/api-contract.md         <- canonical REST contract: route shapes,
│                                  request/response bodies, errors, auth,
│                                  CSRF, route discovery, invariants.
│                                  Locked against the live router by
│                                  ``test_unittest.TestRestContract
│                                  .test_api_contract_doc_lists_every_live_route``.
├── requirements.txt            <- fastapi, uvicorn, pydantic. That's all.
├── HANDOFF.md                   <- this file
├── t.py                        <- dev scratch (gitignored by convention — safe to delete)
├── test_auth.py                <- role-enforcement tests (no framework, ponytail style)
├── test_csrf.py                <- CSRF tests for write routes (same harness as test_auth)
├── test_config.py              <- settings-adapter tests (env snapshot + consumer wiring; ponytail style)
├── test_discovery.py           <- Dashboard module-route discovery tests (descriptor shape + auth / 404 paths)
├── test_patient.py             <- patient-identity adapter tests (fake Add New Patient registry)
├── test_readiness.py           <- module-local readiness probe tests (DB / auth / patient checks + no-leak + HTTP 200/503)
├── test_routes.py              <- route-seam split tests — each seam owns its routes, route order, re-exports
├── test_embed.py              <- embeddable module UI contract — createDiagnosisModule({root, apiBaseUrl}), no host chrome / nav placeholder, route layer untouched
├── test_unittest.py            <- stdlib ``unittest`` suite: rules + REST contract + auth rejection + CSRF + persistence + patient identity + audit seam + clinician authority. The boot smoke checks (``criteria._demo`` / ``api._http_selfcheck``) are now thin shims that run the matching ``TestCase`` sets here.
├── test_output.txt             <- scratch capture from a test run
└── diagnosis/                   <- the importable Python package
    ├── __init__.py             <- exports: router, evaluate, get_criteria, get_app, check_readiness
    ├── __main__.py             <- `python -m diagnosis` entry. Runs self-checks then uvicorn.
    ├── app.py                  <- standalone FastAPI app + /health + /ready + CORS middleware
    ├── readiness.py            <- module-local readiness probe (DB / auth / patient config checks; never leaks URLs) + _readiness_selfcheck
    ├── api.py                  <- THE composed router. Pulls the three seams below into one `router` in invariant order; owns `_http_selfcheck` + back-compat re-exports (`store`, `Submission`, `RESULT_FIELDS`, `_dump_for_audit`, `_read_page`).
    ├── deps.py                 <- shared wiring: the process-wide `DiagnosisStore` instance + the role/CSRF dependencies and the `DIAGNOSIS_AUTH_BYPASS=1` shim consumed by all three seams.
    ├── page.py                 <- BROWSER PAGE seam: `GET /` (serves the SPA, stamps CSRF meta+cookie).
    ├── dashboard.py            <- DASHBOARD DISCOVERY seam: `GET /diagnosis/_meta` (criteria tree + ``rules`` contract for the UI's optimistic display), `GET /diagnosis/_csrf`, `GET /internal/dashboard/module-routes/{moduleId}` (Dashboard module-route discovery -> launch href `/modules/diagnosis`), `GET /internal/diagnosis/audit/{code}` (audit-log seam exposing the persisted local audit trail for the future Logs module — read-only, never writes a snapshot on demand), the `_dump_for_audit` audit-snapshot hook (also invoked from `diagnosis_api.put_session` on every decision-bearing PUT to persist a local audit event). Read-only, no patient-state mutation.
    ├── diagnosis_api.py        <- PROTECTED DIAGNOSIS REST seam: `POST /diagnosis/{code}/init`, `GET /diagnosis/{code}`, `PUT /diagnosis/{code}`. Owns `Submission` + `RESULT_FIELDS`.
    ├── assessment_service.py   <- one criteria-evaluation/presentation path shared by v2 and legacy adapters
    ├── auth.py                 <- role enforcement via the Insight auth service (delegated; no JWT decode)
    ├── csrf.py                 <- signed double-submit CSRF for PUT + POST /init. HMAC-SHA256, per-process secret.
    ├── config.py               <- settings adapter: one ``Settings`` frozen dataclass + ``settings`` singleton sourced from the env (DB path, auth URL, patient URL, CORS origins, mock-auth flag, CSRF secret/secure, module base path, host/port). The only place to add a new integration knob; every other module reads ``settings.*`` rather than scattering ``os.environ.get``. ``_config_selfcheck`` is run by the boot chain.
    ├── patient.py              <- patient identity adapter: free-text code -> canonical INSIGHT patient.id via internal REST
    ├── store.py                <- SQLite repository adapter, v2 migration/quarantine/resolver, versioned audit + _store_selfcheck
    ├── criteria.py             <- DSM-5-TR rules. Pure function evaluate() + _demo() self-check
    └── static/
        └── index.html          <- single-file vanilla-JS web page (no build step)
```

Ten Python files, one HTML file. Nothing else. There are no tests outside the
inline `_demo()` / `_store_selfcheck()` / `_patient_selfcheck()` /
`_http_selfcheck()` / `_readiness_selfcheck()` / `_config_selfcheck()` plus the eight `test_*.py`
harnesses (`test_auth`, `test_csrf`, `test_config`, `test_discovery`, `test_embed`,
`test_patient`, `test_readiness`, `test_routes`, `test_unittest`) — those are
the test surface. `test_config.py` locks the settings adapter (env snapshot +
consumer wiring); `test_unittest.py` now also carries `TestClinicianAuthority`
(lock for the HANDOFF §6.1 clinician-authority invariant), loaded by
`api._http_selfcheck` alongside `TestRestContract` and `TestAuditSeam`.
`test_unittest.py` replaces the inline asserts in `criteria._demo()` and
`api._http_selfcheck()` with stdlib ``unittest`` cases; the shims now run
the matching ``TestCase`` sets so the boot fail-fast contract still holds
without duplicating assertions.

---

## 3. The two layers and how to find things

### Layer A — the seams (api.py + 3 sub-seams, app.py, __init__.py, __main__.py)

The public router used to be one Module mixing the browser page, the
protected per-patient diagnosis REST, and the Dashboard discovery
interface. It is now split into three focused seams composed by
`api.py`. The REST contract is **unchanged** — same paths, request /
response shapes, and `app.include_router(router, prefix="/diagnosis")`
mount. The split is purely about seams so each concern lives in its
own module:

  - `page.py`         — BROWSER PAGE seam: `GET /`.
  - `dashboard.py`    — DASHBOARD DISCOVERY seam: `GET /diagnosis/_meta`
                        (criteria tree + the ``rules`` contract that
                        drives the UI's optimistic display —
                        HANDOFF §9.12), `GET /diagnosis/_csrf`,
                        `GET /internal/dashboard/module-routes/{moduleId}`
                        (returns the launch descriptor for our own module id,
                        404 for an unknown one),
                        `GET /internal/diagnosis/audit/{code}`
                        (audit-log seam — exposes the persisted local audit
                        trail for the future Insight Logs module; read-only,
                        never writes a snapshot on demand),
                        `_dump_for_audit` (audit-snapshot hook, also invoked
                        from `diagnosis_api.put_session` on every
                        decision-bearing PUT so local audit events persist).
                        Read-only, no patient-state mutation.
  - `diagnosis_api.py`— PROTECTED DIAGNOSIS REST seam: per-patient
                        `POST /init`, `GET`, `PUT`. Owns `Submission` + `RESULT_FIELDS`.
  - `deps.py`         — shared wiring: the process-wide
                        `DiagnosisStore` instance + the role / CSRF
                        dependencies + the `DIAGNOSIS_AUTH_BYPASS=1` shim.
                        The three seams import from here so policy / store
                        identity never drifts. Tests still import
                        ``from diagnosis.api import store`` (re-exported).
  - `config.py`       — SETTINGS adapter: one frozen ``Settings`` dataclass
                        + a ``settings`` singleton sourced from the env
                        (DB path, auth URL + timeout, patient URL + timeout
                        + lookup flag, CORS origins, mock-auth flag, CSRF
                        secret + secure flag, module base path, host/port).
                        Every other module reads ``settings.*`` instead of
                        scattering ``os.environ.get``; this is the only
                        place to add a new integration knob. ``module_id``
                        + ``launch_href`` derive from ``module_base_path``
                        so a non-default mount prefix flows through to the
                        Dashboard descriptor. The ``reset_*_for_tests``
                        hooks on ``auth`` / ``patient`` / ``csrf`` mutate
                        *their* module globals, not the singleton, so the
                        test surface stays the same. ``_config_selfcheck``
                        is run by the boot chain (HANDOFF §9.5).
                        ``test_config.py`` locks the snapshot + the consumer
                        wiring.

`api.py` composes the three sub-routers into ONE `router` in the route-order
invariant order (see §9.4) by registering the sub-routers' routes on
`router` — it does NOT call `router.include_router(sub)` at this level,
because FastAPI only unwraps one level of `include_router` when the parent
app later mounts us, and the extra nesting would silently drop the
`/diagnosis/_csrf` route from OpenAPI. Appending the `APIRoute` objects
directly preserves the declared order, their deps, and the
literal-before-`/{code}` matching. See `test_routes.py`.

### Layer C — the repository (store.py)

Pure-ish persistence adapter used by `api.py`. Single connection per process,
WAL journal, two tables (`sessions`, `audit`). Same `init`/`get`/`put`/`audit_snapshot`
contract the route handlers used against the prior in-memory dict. Override DB
location with `DIAGNOSIS_DB_PATH`. `_store_selfcheck()` covers patient id/code
round-trip, checked-criteria persistence, decision round-trip, monotonic
timestamps, audit snapshots, and durability across a fresh `DiagnosisStore`.

**`diagnosis/__init__.py`** — package entrypoint. Exports `router`, `evaluate`,
`get_criteria`, `get_app`. `get_app()` is lazy because importing `app.py`
pulls in FastAPI; the criteria engine alone must import without it.

**`diagnosis/api.py`** — the composed router. Read this to understand
the contract surface and how the three seams are wired together.
- `store: DiagnosisStore` (re-exported from `deps.py`; the
  SQLite-backed repository adapter; see `store.py`). Single-process,
  WAL journal. The route handlers use the same `init`/`get`/`put`
  surface they used to call against the old in-memory dict — REST
  contract is unchanged. Override the DB location with `DIAGNOSIS_DB_PATH`.
- `Submission` pydantic model (owned by `diagnosis_api.py`) —
  `{checked: [ids], decision: "confirmed"|"definite"|null}`.
- Seven routes on the public router (README table is authoritative), split
  across the three seams: `page.py` (`GET /`), `dashboard.py`
  (`GET /diagnosis/_meta`, `GET /diagnosis/_csrf`,
  `GET /internal/dashboard/module-routes/{moduleId}`,
  `GET /internal/diagnosis/audit/{code}`), `diagnosis_api.py`
  (`POST /diagnosis/{code}/init`, `GET /diagnosis/{code}`,
  `PUT /diagnosis/{code}`). Plus the standalone `app.py` `/health` and
  `/ready`.
  Critical gotcha documented in code: **literal routes
  (`/diagnosis/_meta`, `/diagnosis/_csrf`) MUST be matched before the
  parameterized `/{code}` route**, or FastAPI captures `_meta`/`_csrf`
  into `{code}` and 404s. The dashboard module-route discovery path
  `/internal/dashboard/module-routes/{moduleId}` has a `{moduleId}` path
  parameter but lives under a distinct `/internal/...` prefix, so it does
  NOT collide with `/{code}`; it still ships with the dashboard seam
  (before the diagnosis seam) for the literal-before-`/{code}` ordering.
  The audit-log route `/internal/diagnosis/audit/{code}` also has a
  `{code}` parameter but lives under the same `/internal/...` prefix —
  it does NOT collide with `/{code}` for the same reason, and it ships in
  the dashboard seam (before the diagnosis seam) for the ordering
  invariant too.
  `api.py` registers the page seam, then the dashboard seam (literals +
  the discovery route + the audit-log route), then the diagnosis seam
  (`{code}`) — do not reorder the `for _sub in (...)` tuple.
- `RESULT_FIELDS` tuple (owned by `diagnosis_api.py`) — the acceptance
  contract shared by GET/PUT response evaluation objects.
- **CSRF gate**: PUT and POST `/diagnosis/{code}/init` declare
  `Depends(require_csrf)` alongside the role dependency. CSRF is checked
  second (FastAPI evaluates deps in declared order) — a 401 from the role
  dependency fires first, so unauthenticated callers never burn a CSRF
  token. The bypass shim (`DIAGNOSIS_AUTH_BYPASS=1`) shorts both auth and
  CSRF so the in-process self-check can drive PUT/init without minting
  tokens. See `csrf.py` for the protocol; both deps live in `deps.py`.
- **Patient identity adapter**: `init_session` and `put_session` (in
  `diagnosis_api.py`) call
  `patient.resolve_patient(code, request.headers["cookie"])` BEFORE
  persisting, and write the returned `Patient.id` (the canonical INSIGHT
  registry id) into `sessions.patient_id`. The free-text `{code}` path
  parameter stays the local session key — the REST contract is unchanged.
  The adapter calls `GET {PATIENT_BASE_URL}/api/patients/lookup?code=...`
  via internal REST only; the diagnosis module never reads the patient DB
  and never imports from the primitives app. Adapter is **opt-in** via
  `DIAGNOSIS_PATIENT_LOOKUP=1`; default disabled returns a
  self-consistent `Patient(id=code, patient_code=code, display_name=code)`
  so the row's `patient_id` is never blank. A registry 404 / transport
  fault / missing canonical id maps to a clean 422 — never a stack trace
  and never a row whose `patient_id` collapses back to the free-text code.
  See `patient.py` for the contract and `test_patient.py` for the
  happy + fault paths.
- `_dump_for_audit(code)` (owned by `dashboard.py`, re-exported by
  `api.py`) — JSON snapshot for audit logging, persisted to the `audit`
  table by `store.audit_snapshot`. As of the audit-event-seam issue this
  hook is ALSO invoked from `diagnosis_api.put_session` after every
  decision-bearing PUT (so each checkbox toggle PUT + each explicit
  confirm / bypass button hit leaves a local audit row), and the
  dashboard seam exposes the persisted trail through
  `GET /internal/diagnosis/audit/{code}` for the future Insight Logs
  module. Snapshot is the source row (decision + checked ids) — NO
  `evaluation` key — so an audit row can never be read as a
  server-derived auto-diagnosis (HANDOFF §6.1 extends through the
  audit trail).
- `_http_selfcheck()` — thin shim that runs
  ``test_unittest.py::TestRestContract`` plus ``TestClinicianAuthority``
  plus ``TestAuditSeam``
  (stdlib ``unittest``, no new dependency) under the
  ``DIAGNOSIS_AUTH_BYPASS=1`` shim the same way the route handlers do, so
  the readiness probe inside it asserts `auth.bypass == True` -> not
  deploy-ready (the same alarm a production gate would fire if the shim
  were left on). The added `TestClinicianAuthority` blocks (HANDOFF §6.1)
  fail the boot self-check if the model's `met` ever becomes an automatic
  diagnosis or a valid bypass is rejected on an unmet checklist. The
  added `TestAuditSeam` blocks (audit-event-seam issue) fail the boot
  self-check if a decision-bearing PUT stops persisting a local audit
  event or the dashboard audit-log route stops returning the
  chronological trail. The
  inline assert-based contract smoke check used to live here; the cases
  moved to ``test_unittest.py`` so the rules + REST contract + auth
  rejection + CSRF + persistence + audit seam + clinician authority +
  patient identity
  all share one ``unittest`` surface. Runs before `python -m diagnosis`
  serves traffic (HANDOFF §9.5).

**`diagnosis/app.py`** — the standalone FastAPI app. Mounts the router, adds
permissive CORS (`ponytail:` tighten via env when deployed), exposes
`/health` -> `{"ok": True, "module": "diagnosis"}` (liveness) and
`/ready` -> `diagnosis.readiness.check_readiness()` (readiness; 200 when ok,
503 when any check fails). When embedded in the larger Insight app, this file
is **not** used — the larger app includes the `router` directly and composes
`check_readiness()` into its own readiness aggregator.

**`diagnosis/readiness.py`** — module-local readiness probe. Returns
`{"ok": bool, "module": "diagnosis", "checks": {db, auth, patient}}`
without raising. **Never leaks secrets**: the DB check probes the live
`DiagnosisStore` with `SELECT 1` on the connection the route handlers reuse
(never echoes the on-disk DB path); the auth check verifies
`AUTH_BASE_URL` is configured AND the shim is off (never echoes the URL,
never calls the auth service — the auth service needs the user's Cookie, so a
cookieless probe would 401 and falsely report not-ready on a clean deploy);
the patient check verifies the adapter is configured when
`DIAGNOSIS_PATIENT_LOOKUP=1` (never echoes `PATIENT_BASE_URL`) and reports
`{enabled: False, configured: True}` as a clean "skipped" state when the
adapter is opted out. ``bypass: True`` on the auth check is the deploy alarm
that surfaces when the `DIAGNOSIS_AUTH_BYPASS=1` shim is left on in
production. `_readiness_selfcheck()` is the ponytail-style no-framework
self-verify; `test_readiness.py` covers the function + the HTTP route
(200/503 + no-leak).

**`diagnosis/__main__.py`** — CLI entry. `argparse` for `--host/--port/--reload`.
Runs **both** self-checks (`criteria._demo()` and `api._http_selfcheck()`)
before booting uvicorn. **Fail-fast contract**: if either self-check asserts,
the server never starts. Don't bypass this.

**`diagnosis/csrf.py`** — signed double-submit CSRF for write routes.
- `mint()` returns `{raw_32_hex}.{hmac_sha256(secret, raw)}`. The secret is
  per-process random; multi-worker deployments MUST set `DIAGNOSIS_CSRF_SECRET`
  (env) so a token minted by one worker validates on another. Token does NOT
  survive a server restart — clients must re-fetch after each boot.
- `set_cookie(resp, token)` stamps the `csrf` cookie (SameSite=Lax,
  HttpOnly=False so JS may read it; not Secure in dev — flip with
  `DIAGNOSIS_CSRF_SECURE=1` behind TLS).
- `require_csrf(request)` — the FastAPI dependency. Fail-closed 403 unless
  cookie value === header value AND both signatures verify (constant time).
- `reset_secret_for_tests(secret)` — pin a known secret so test code can
  mint tokens the validator accepts.
- The bypass shim in `api.py` (controlled by `DIAGNOSIS_AUTH_BYPASS=1`)
  shorts CSRF so the in-process self-check drives writes without minting.
- `test_csrf.py` mirrors `test_auth.py` — fake auth service always returns
  psychiatrist, secret pinned via `reset_secret_for_tests`. Covers: no
  token, header-only, cookie-only, mismatch, bad signature, valid path,
  mint route sets cookie, HTML page carries meta, bypass-honored.

**`diagnosis/patient.py`** — patient identity adapter. Mirrors `auth.py`:
pure-stdlib `urllib`, frozen `Patient` dataclass, fail-closed HTTPException,
no DB imports, no primitives-app imports. Read this before touching any
route that writes a row.
- `resolve_patient(code, cookie_header) -> Patient` — the only public
  entry. Honours `DIAGNOSIS_PATIENT_LOOKUP`:
    - unset / not "1" (default) — adapter disabled; returns
      `Patient(id=code, patient_code=code, display_name=code)`. The
      self-check + offline tests rely on this short. Production opts IN.
    - "1" — real lookup enforced; 404 / transport fault / missing
      `id` → clean 422.
- `_fetch_patient(code, cookie_header)` — calls
  `GET {PATIENT_BASE_URL}/api/patients/lookup?code=...`, forwards the
  incoming `Cookie` (same trust boundary as `auth.py`).
- `_build_patient(payload, code)` — normalizes the registry JSON; fails
  closed on a missing canonical `id`; falls back `patient_code` to the
  supplied free-text `code` when the payload omits it.
- `reset_patient_for_tests(base_url)` — rebind `PATIENT_BASE_URL` for
  tests; mirrors `auth.reset_auth_for_tests`.
- `_patient_selfcheck()` — no-registry self-verify. Run: `python -m
  diagnosis.patient`. Covers empty code (400), bypass short
  (free-text), missing-id 422, `_build_patient` fallbacks, and
  `display_name` None / non-str tolerance.
- `test_patient.py` — full happy + fault contract against a fake
  in-process "Add New Patient" registry + fake auth (psychiatrist).
  Covers: canonical id bound on init + put, unknown code → 422 on both
  routes, empty code → 400, registry 200-but-no-id → 422, bad JSON →
  422, registry 500 → 422, registry down → 422, lookup-disabled env
  falls back to free-text without contacting the registry.

### Layer B — the engine (criteria.py)

Pure logic, no I/O. Read this to understand the DSM-5-TR rules.
- `CRITERIA: list[dict]` — the source of truth. 9 items, each with stable
  `id` (A1–A6, B1, C1, D1), `group`, `text`, plus optional flags:
  - `core: True` on A1, A2, A3 (the "core triad")
  - `duration: True` on A6 (required but does not count toward the ≥2 symptom count)
  - `guard: "B"|"C"|"D"` on B1/C1/D1 (exclusion items — must be checked **True** to exclude)
- `GUARD_LABEL` — human-readable labels for guard failures.
- `Evaluation` dataclass — the return type. Has `.to_dict()` for the API.
- `get_criteria()` — returns copies (caller must not mutate `CRITERIA`).
- `evaluate(checked_ids: list[str]) -> Evaluation` — **the pure function**.
  This is the test surface. Rules (paraphrased from the docstring):
  1. Count A-group symptoms excluding the duration item A6. Need ≥2.
  2. At least 1 must be from the core triad (A1–A3).
  3. A6 (duration, 1-month) must also be checked.
  4. Each guard B/C/D has one item; it must be checked to satisfy the exclusion.
  - `met = not failures` — the only definition of "criteria met".
  - `reason` — one-line clinician-facing summary, used verbatim in the UI.
- `_demo()` — thin shim that runs ``test_unittest.py::TestCriteriaRules``
  (stdlib ``unittest``). Run: `python -m diagnosis.criteria`. The inline
  six-case assert smoke check used to live here; the cases moved to
  ``test_unittest.py`` so the rule assertions share one surface with the
  REST contract + auth + CSRF + persistence + patient identity tests.
  If a rule changes, the tests in ``test_unittest.py::TestCriteriaRules``
  are the authoritative safety net — and the boot shim still fail-fast
  on a failed assert.

---

## 4. The web page (`static/index.html`)

Single HTML file, **no build step**. INS-024 connects the embedded UI only to
the canonical v2 assessment interface:

- `createDiagnosisModule({root, apiBaseUrl, embedded, patientId,
  encounterId})` accepts canonical UUID context from the host and returns
  `{mount, unmount, setAssessmentContext}`.
- The UI never accepts a patient code, reads a query string, writes history,
  or places a patient alias in a URL. The host owns navigation and context.
- Startup loads criteria metadata, obtains CSRF from the stamped meta element
  or `/diagnosis/_csrf`, reads the latest Encounter assessment, and initializes
  it through `POST /api/diagnosis/v2/assessments` only when latest returns 404.
- Every write uses schema `2.0.0`; create uses an idempotency key; update uses
  the current strong ETag in `If-Match`; cookies and CSRF remain enforced.
- The browser does not evaluate criteria. It renders the v2 server evaluation,
  and `evaluation.met` only gates availability of the separately clicked
  confirm action. Bypass is a separate confirmed action and is attributed by
  the server-authenticated psychiatrist identity.
- Checkbox changes persist `clinicianDecision: null`; explicit confirm and
  bypass actions persist their own decision object. A rejected write restores
  the last server state and shows a focused `role="alert"` failure instead of
  appearing saved.
- Native checkboxes and buttons preserve keyboard behavior, focus is moved to
  the workspace after successful context load and to errors on failure, and
  visible focus/reduced-motion/mobile-target rules are present.
- `unmount()` aborts in-flight requests, clears pending timers, removes every
  module listener, and clears only the supplied root. Context switches abort
  the preceding request before loading the new Encounter.
- Embedded mode omits `.dm-topbar`; neither mode mutates browser navigation.

`test_embed.py` locks these UI contracts and verifies JavaScript syntax with
Node. `test_diagnosis_v2_contracts.py` covers the v2 HTTP, UUID-only URL,
clinician-authority, failure/precondition, and legacy/server evaluation-
equivalence behavior. `test_csrf.test_html_page_carries_meta_token` continues
to lock the page-seam CSRF stamp. The `/` route serves this file through
`_read_page()`.

---

## 5. Run it

```bash
# Standalone
pip install -r requirements.txt
python -m diagnosis                               # http://localhost:8000?code=P-0427-A
python -m diagnosis --port 8010 --reload          # dev with hot reload

# Self-checks only (no server)
python -m diagnosis.criteria                      # engine unittests (rules)
python -m diagnosis.store                         # persistent store test
python -m diagnosis.patient                       # patient identity adapter test
python -m diagnosis.readiness                      # readiness probe test
python -m diagnosis.config                        # settings adapter test
python -c "from diagnosis.api import _http_selfcheck; _http_selfcheck()"  # REST contract unittests

# Full unittest suite (rules + REST contract + auth + CSRF + persistence + patient)
python -m test_unittest
python -m test_config                            # settings adapter (env snapshot + consumer wiring)

# Embedded
from fastapi import FastAPI
from diagnosis import router
app = FastAPI()
app.include_router(router, prefix="/diagnosis")
```

Note: `python -m diagnosis` always runs all six self-checks before serving.
A failing assert means the server won't boot. This is intentional.
`criteria._demo` and `api._http_selfcheck` delegate to the `unittest`
cases in `test_unittest.py`; the remaining four smoke checks
(`store._store_selfcheck`, `patient._patient_selfcheck`,
`readiness._readiness_selfcheck`, `config._config_selfcheck`) are the
conventional inline-assert self-verifies.

---

## 6. The clinician-authority rule (do not violate)

From DESIGN.md §6 and §10 (referenced in code comments):
- **The model never makes the final diagnosis.** `evaluate()` returns a
  boolean `met` field — that is decision **support**, not a decision.
- The "Diagnosis is clear" button (`decision: "confirmed"`) requires
  Criterion A met (client-side `disabled` guard). The psychiatrist is
  affirming "yes, criteria met, this is my diagnosis."
- The "bypass" button (`decision: "definite"`) is **always enabled** and
  records "psychiatrist overrides the checklist." Per the institution's
  protocol this exists because clinician authority supersedes the
  checklist in edge cases. The model's `met` is *not* consulted for bypass.
- The `Submission.decision` field is `Literal["confirmed", "definite"] | None`.
  `"definite"` from a still-unmet criteria state is **valid and must be
  accepted by PUT** — that's the bypass path. Do not add a server-side
  "must be met to confirm `definite`" check.

If you add any logic that turns the model's `met` into an automatic
diagnosis, you have broken the core safety contract of this module.

### 6.1. Tested contract — `test_unittest.TestClinicianAuthority`

This invariant is **not** prose-only. It locked in `test_unittest.py`'s
`TestClinicianAuthority` suite (stdlib `unittest`, no new deps), which the
boot self-check runs (`diagnosis/api.py::_http_selfcheck` loads it via
`TestLoader` alongside `TestRestContract`). Cases:

1. **`test_met_false_never_implies_a_decision` / `test_met_true_is_not_a_confirmed_diagnosis`**
   — `Evaluation` exposes NO decision-shaped attribute (`decision` /
   `diagnosis` / `verdict` / `confirmed` / `definite` / `bypass`). The
   dataclass stays a pure checklist projection; nothing on its surface
   invites auto-diagnosis logic.
2. **`test_bypass_accepted_when_criteria_unmet`** — `decision: "definite"`
   PUT on a not-met checklist is accepted (200), persisted as `definite`,
   and round-trips through GET. The server does NOT consult `met` on the
   bypass path.
3. **`test_bypass_accepted_when_criteria_met`** — symmetric: a bypass on
   a checklist that *would* mark `met == True` stays `definite`; the API
   does NOT rewrite `met` to match the bypass either (`evaluation.met`
   still reports the honest DSM result).
4. **`test_no_auto_confirmation_from_met_true`** — a PUT with `met == True`
   but `decision: null` MUST stay `decision == None`. `met` must not
   coerce the decision to `"confirmed"`. The psychiatrist must explicitly
   affirm; the model is not allowed to commit a diagnosis on their behalf.
5. **`test_confirmed_requires_explicit_clinician_decision`** — `"confirmed"`
   PUT records verbatim; the audit snapshot (`_dump_for_audit`) preserves
   the clinician's voice (`decision`) plus the checked ids, and carries NO
   `evaluation` key — so the audit row can never be mistaken for a
   server-derived auto-diagnosis.
6. **`test_decision_not_rewritten_on_later_met_toggle`** — a bypass captured
   earlier is NOT retro-converted when a later PUT happens to satisfy A.
   No server-side "reconcile decision against `met`" logic may exist.
7. **`test_confirmed_unchanged_when_checklist_later_unmet`** — symmetric:
   a `confirmed` recorded earlier is NOT retro-downgraded by a later PUT
   whose checklist no longer meets A. The decision is the clinician's
   record; the model's refreshed projection is independent of it.

Break any of these and you've broken the core safety contract — and the
boot self-check will refuse to start the server.

---

## 7. DESIGN.md tokens (referenced, file not in this repo)

`DESIGN.md` lives in the larger Insight app, not here. The HTML hard-codes
its tokens verbatim. The locked ones:
- `--primary: #0A9E8F` (teal) — the single accent. Inter for body text,
  JetBrains Mono for monospace quantities (patient code, score numbers).
- Status colors: `--normal` (green), `--urgent` (red), `--warning` (amber),
  `--info` (blue), `--follow-up` (purple). Each has matching `*-bg`.
- Radii: `--radius-sm 4px / -md 8px / -lg 12px / -xl 16px / -pill 9999px`.
- Easing: `cubic-bezier(0.4, 0, 0.2, 1)` with durations 100/180/300ms.
- `prefers-reduced-motion` resets all transitions/animations.

If you change a token here, also change it in the larger Insight app or they
drift. Prefer keeping the local copy identical to DESIGN.md.

---

## 8. Common changes and where to make them

| You want to… | Edit… | Watch out for… |
|---|---|---|
| Add/edit a DSM criterion | `criteria.py :: CRITERIA` | Update the matching case in `test_unittest.py::TestCriteriaRules` in the same change. The `id` strings are part of the API contract and the JS data-id bindings. `criteria._demo` is now a thin shim that runs those `unittest` cases — edit the cases, not the shim. |
| Change a rule (e.g. duration threshold) | `criteria.py :: evaluate()` | Update docstring AND the matching `test_unittest.py::TestCriteriaRules` cases. If the rule edit adds a new *dimension* the UI's optimistic display surfaces, expose its primitive in `criteria.meta_contract()` AND extend `test_meta_rules_match_engine_every_subset` in the same change (see §9.12). The HTML `renderLocalEvaluation` consumes `meta_contract` via `/diagnosis/_meta` — never reimplement the rule in JS. |
| Add a discovery / audit-read endpoint | `dashboard.py` (e.g. a new `GET /diagnosis/_...` route, or another `/internal/dashboard/module-routes/{...}` discovery variant, or a new `/internal/diagnosis/audit/...` audit trail surface). | **Literal routes before `/{code}`** — must be included *before* the diagnosis seam sub-router in the `for _sub in (...)` tuple in `api.py`, or FastAPI captures them. The `/internal/dashboard/module-routes/{moduleId}` path's `{moduleId}` param and the `/internal/diagnosis/audit/{code}` path's `{code}` param do NOT collide with `/{code}` because they sit under distinct `/internal/...` prefixes, but both still ship in the dashboard seam before the diagnosis seam for the ordering invariant. The audit-log route (`GET /internal/diagnosis/audit/{code}`) READS — never writes a snapshot on demand; keep it that way. |
| Swap the persistence layer | `store.py :: DiagnosisStore` — add methods, keep the `init`/`get`/`put`/`audit_snapshot`/`reset` surface intact. | The router contract (path, request/response shape) must not change — Insight callers depend on it. Keep `RESULT_FIELDS`. Point at a new DB location with the `DIAGNOSIS_DB_PATH` env var. |
| Change the web page | `static/index.html` directly; there is no build step | Keep `apiBaseUrl` prefixing every fetch (the new contract — no baked same-origin `API = ""` constant). Keep the bypass button always-enabled per §6. **Keep `csrfHeaders(...)` on every fetch that uses method `"PUT"` or `"POST"`** — the server 403s otherwise. **Keep `createDiagnosisModule({root, apiBaseUrl})` the one embeddable entry point** — never bake a standalone topbar or a host-navigation placeholder (e.g. the old `Back to dashboard` button — removed). Mirror any DOM/contract edit into `test_embed.py` so the embeddable contract stays locked. |
| Add persistence to bypass/confirmed | Already persists in `DiagnosisStore` as `decision`, with timestamps (`created_at`/`updated_at`) and audit snapshots. As of the audit-event-seam issue `diagnosis_api.put_session` ALSO calls `_dump_for_audit(code)` after each `store.put` so the local `audit` table accumulates a chronological trail per code; the dashboard seam's `GET /internal/diagnosis/audit/{code}` exposes that trail to the future Insight Logs module (read-only). Update `_store_selfcheck()` in the same change so the contract is locked in; mirror any audit-shape change into `TestAuditSeam`. | The `_dump_for_audit` hook returns the JSON snapshot AND inserts it into the `audit` table via `store.audit_snapshot` — wire additional audit sinks (e.g. an emission endpoint) when integrating with Insight. |
| Add / change an integration knob | `config.py :: Settings` + ``_load`` — the frozen dataclass + env read is the single source for DB path, auth URL, patient URL, CORS origins, mock-auth flag, CSRF secret/secure, module base path, host/port. | Every other module reads ``settings.*`` instead of scattering ``os.environ.get``. DO NOT add a fresh ``os.environ.get`` in another module — extend ``Settings`` + ``_load`` and re-point the consumer at it. The ``reset_*_for_tests`` hooks on ``auth`` / ``patient`` / ``csrf`` mutate *their* module globals (not the singleton) so the test surface keeps working. Update `_config_selfcheck` + `test_config.py` in the same change so the snapshot + consumer wiring stay locked. |
| Add a Python tests beyond the self-checks | The repository already has `test_unittest.py` (stdlib ``unittest``, no new deps): `TestCriteriaRules` (rules), `TestRestContract` (REST contract + persistence + patient-identity-disabled short under the bypass shim), `TestAuditSeam` (audit event seam — every decision-bearing PUT persists a local audit event + the dashboard `GET /internal/diagnosis/audit/{code}` route exposes the chronological trail, oldest first; init alone does NOT audit), `TestClinicianAuthority` (model-never-decides invariant, HANDOFF §6.1 — loaded by boot self-check; covers bypass-on-met AND on-unmet plus the no-auto-confirmation-from-met cases), `TestAuthRejection` / `TestCSRF` / `TestPersistence` / `TestPatientIdentity` (dep-level unit cases). The ponytail harnesses `test_auth` / `test_csrf` / `test_config` / `test_discovery` / `test_embed` / `test_patient` / `test_readiness` / `test_routes` remain for end-to-end integration paths via fake in-process HTTP servers. Don't introduce a pytest dep without checking Insight pytest already exists. `test_config.py` is the template for a settings-adapter change; `test_csrf.py` for a CSRF-affecting HTTP change; `test_routes.py` for a seam-routing change; `test_readiness.py` for a readiness-affecting change; `test_embed.py` for an embeddable-UI / served-page change; `test_unittest.py::TestRestContract` for a REST-contract change (NOTE: `TestRestContract.test_api_contract_doc_lists_every_live_route` locks the `docs/api-contract.md` §2 route catalogue against the live router — add the new `(method, path)` row to that doc in the same change or the test fails); `test_unittest.py::TestAuditSeam` for an audit-seam change; `test_unittest.py::TestClinicianAuthority` for a clinician-authority / decision-handling change; `test_unittest.py::TestCriteriaRules` for a rules change. |
| Add / change a readiness check | `readiness.py :: _check_<name>` returns `{ok: bool, ...}` — add the key to the `checks` dict in `check_readiness()` and `__all__` is fine to extend. The HTTP route in `app.py` wraps whatever `check_readiness()` returns. | NEVER call a live service from readiness (it would block + leak). NEVER echo a URL / path / token / host name in the response. NEVER raise from the probe — a fault must collapse to `{ok: False}`. Update `_readiness_selfcheck` + `test_readiness.py` in the same change so the no-leak + no-raise contracts stay locked. Update `__init__` re-export + HANDOFF §9.11. |
| Rotate/share the CSRF secret | `config.py :: Settings.csrf_secret` (env `DIAGNOSIS_CSRF_SECRET`) is the source; `csrf.py :: _SECRET` is initialised from it at import and falls back to per-process random when unset. Multi-worker deployments MUST set it so a token minted on one worker validates on another. | Tokens do not survive a restart by design — clients re-fetch on next `GET /` or `GET /diagnosis/_csrf`. For production behind TLS set `DIAGNOSIS_CSRF_SECURE=1` (-> `Settings.csrf_secure` -> `csrf._SECURE_COOKIE`) so the cookie is `Secure`. |
| Add a browser-page route | `page.py` — currently only `GET /`. | The page seam is gated by the read policy (`require_psychiatrist_or_admin`) and owns the CSRF meta/cookie injection on serve. Keep the bypass short-circuit byte-clean under `DIAGNOSIS_AUTH_BYPASS=1`. |
| Deploy / tighten CORS | `config.py :: Settings.cors_origins` (env `DIAGNOSIS_CORS_ORIGINS`, comma list, default `*`) is the source; `app.py` reads `settings.cors_origins`. | Only affects standalone mode. When mounted in Insight, the parent app owns CORS. `test_config.py::test_app_cors_reads_settings` locks the wiring. |
| Add a new write route | `diagnosis_api.py` — declare `_ = Depends(require_psychiatrist)` AND `__ = Depends(require_csrf)` together (both from `deps.py`). Order matters: FastAPI runs deps in declared order — list auth first so unauthenticated callers get 401, never the CSRF token leak. After `store.put` succeeds, call `_dump_for_audit(code)` (from `dashboard.py`) so each decision-bearing write persists a local audit event — `TestAuditSeam` will fail the boot self-check otherwise (HANDOFF §9.14). | Update `test_csrf.py` to cover the new route's missing-token path, and `test_auth.py` to arm writes via `_arm_with_csrf`. Update `test_routes.py` to declare the new path on the diagnosis REST seam. |
| Enforce canonical patient identity (link to Add New Patient registry) | `patient.py :: resolve_patient` — already wired into `init_session` + `put_session`. Flip the env `DIAGNOSIS_PATIENT_LOOKUP=1` at deploy; point at the registry with `PATIENT_BASE_URL`. (`Settings.patient_url` + `Settings.patient_lookup` surface the same values; `patient.py` keeps the mutable module globals for the test reset hook.) | REST contract is unchanged: `{code}` stays the local session key; only the row's `patient_id` column becomes canonical. Don't write to `sessions.patient_id` from outside `resolve_patient` — that re-introduces the diagnosis-local free-text bug. Update `_patient_selfcheck` + `test_patient.py` if the registry contract changes. |

---

## 9. Invariants — break these and you've changed the contract

1. `CRITERIA` ids (`A1`–`A6`, `B1`, `C1`, `D1`) are stable. Clients store
   them, the JS binds to them via `data-id`. Renaming is a breaking change.
2. `evaluate(checked_ids)` is **pure**. No I/O, no side effects, no globals.
   Anything you add that touches the store breaks the test surface.
3. `Submission.decision ∈ {"confirmed", "definite", None}`. PUT must accept
   `"definite"` even when `met` is false (the bypass path). See §6.
4. Route declaration order in `api.py`: literal paths first, `/{code}` last.
   Concretely the `for _sub in (_page_router, _dashboard_router, _diagnosis_router)`
   tuple sets the registration order — page (`/`) -> dashboard (`_meta`, `_csrf`
   literals + the `/internal/dashboard/module-routes/{moduleId}` discovery route
   + the `/internal/diagnosis/audit/{code}` audit-log route) -> diagnosis REST
   (`/{code}` family). The audit-log route's `{code}` parameter, like the
   discovery route's `{moduleId}` parameter, lives under the distinct
   `/internal/...` prefix and does NOT collide with `/{code}` — but still
   precedes it for the literal-before-parameterized invariant. Do NOT pre-nest with
   `router.include_router(sub)` at this level: FastAPI only unwraps one level
   of `include_router` when the parent app later mounts us, and the extra
   nesting silently drops `/diagnosis/_csrf` from OpenAPI (regression
   caught by `test_routes.py`). Appending the sub-routers' `APIRoute`
   objects instead.
5. The six self-checks (`criteria._demo`, `store._store_selfcheck`,
   `patient._patient_selfcheck`, `readiness._readiness_selfcheck`,
   `config._config_selfcheck`, `api._http_selfcheck`) must pass before
   the server boots. Don't disable them in `__main__.py`. `criteria._demo`
   and `api._http_selfcheck` are thin shims that run the matching
   `unittest` cases in `test_unittest.py` — the assertions live there so
   the rule + REST contract + auth rejection + CSRF + persistence +
   audit seam + clinician-authority + patient identity surface shares
   one `unittest` home. `api._http_selfcheck` now loads `TestRestContract`,
   `TestClinicianAuthority` (HANDOFF §6.1), AND `TestAuditSeam` (audit-
   event-seam issue): the boot self-check fails fast if the model-never-
   decides invariant is broken OR a decision-bearing PUT stops persisting
   a local audit event OR the dashboard audit-log route stops returning
   the chronological trail. The other four smoke checks
   `_store_selfcheck` / `_patient_selfcheck` / `_readiness_selfcheck` /
   `_config_selfcheck` remain conventional inline-assert self-verifies
   (no env pivot needed).
6. The web page never decides without the clinician. The model's `met` only
   **enables** the confirm button; it never auto-sends a decision. The
   server honours the same shape on PUT and the boot self-check locks it
   via `TestClinicianAuthority` (HANDOFF §6.1): `met == True` does not
   coerce `decision` to `"confirmed"`, and `"definite"` is accepted
   regardless of `met`.
7. `RESULT_FIELDS` defines the evaluation object shape GET/PUT return.
   Don't drop or rename keys without bumping the Insight integration.
8. **CSRF on writes**: PUT `/diagnosis/{code}` and POST `/diagnosis/{code}/init`
   require the signed double-submit token (cookie `csrf` === header
   `X-CSRF-Token` AND HMAC signed by `_csrf._SECRET`). Read routes are
   exempt. Don't add a new state-mutating route without wiring
   `Depends(require_csrf)` (from `deps.py`) onto it. The bypass shim is
   keyed on `DIAGNOSIS_AUTH_BYPASS=1` and is for the self-check only.
9. **Canonical patient id is authoritative.** `sessions.patient_id` MUST
   be set by `patient.resolve_patient` only — never assigned the free-text
   `{code}` directly from a route handler. The free-text code stays the
   local session key (route path + `sessions.code` PK), but the
   cross-module identity is the canonical `patient.id` returned by the
   "Add New Patient" registry. A row whose `patient_id` equals its
   `code` is fine AND expected when `DIAGNOSIS_PATIENT_LOOKUP` is off
   (default) — but a route handler bypassing the adapter to write
   `patient_id=code` IS a contract break. The REST contract does not
   change when the env flips; only the column value semantics do.
10. **Seam split is a contract, not a stylistic choice.** The router is
    composed from three seams (`page.py`, `dashboard.py`,
    `diagnosis_api.py`) sharing one `deps.py`. Browser page route lives
    ONLY in `page.py`; Dashboard discovery routes (`/diagnosis/_meta`,
    `/diagnosis/_csrf`, `/internal/dashboard/module-routes/{moduleId}`,
    `/internal/diagnosis/audit/{code}` — the audit-log seam)
    + the audit-snapshot hook `_dump_for_audit` live
    ONLY in `dashboard.py`; per-patient state mutation lives ONLY in
    `diagnosis_api.py`. The shared `store` instance AND the
    role/CSRF deps live ONLY in `deps.py` — never instantiate
    `DiagnosisStore` in a seam and never re-write the role/CSRF deps
    in a route module. `api.py` keeps the public `router`,
    `_http_selfcheck`, and the back-compat re-exports (`store`,
    `Submission`, `RESULT_FIELDS`, `_dump_for_audit`, `_read_page`);
    `test_routes.py` locks the seams.
11. **Readiness is module-local and never leaks secrets.**
    `readiness.check_readiness()` returns `{ok, module, checks: {db,
    auth, patient}}` and MUST NOT raise, MUST NOT call live services,
    and MUST NOT echo any URL or path. The DB check reuses the live
    `DiagnosisStore` connection the route handlers share; the auth
    check verifies `AUTH_BASE_URL` is configured AND the
    `DIAGNOSIS_AUTH_BYPASS=1` shim is off (cookieless probes would
    401 falsely); the patient check verifies `PATIENT_BASE_URL` is
    configured when `DIAGNOSIS_PATIENT_LOOKUP=1` and reports
    `{enabled: False, configured: True}` as a clean "skipped" state
    otherwise. The HTTP route in `app.py` is `GET /ready` -> 200 when
    `ok` else 503 — distinct from `/health` (liveness). Tests live in
    `test_readiness.py` (function + HTTP 200/503 + no-leak).
    `bypass: True` on the auth check is the deploy alarm that fires
    when the shim is left on in production — surfacing the flag NAME
    (not the URL) is the contract.
12. **Server evaluation is the single source of truth for the UI's
    optimistic display.** `GET /diagnosis/_meta` returns a `rules` object
    (`criteria.meta_contract()`) exposing the SAME primitives
    `evaluate()` reads (symptom / core / duration / guard ids + the DSM
    thresholds). The browser page's `renderLocalEvaluation` is a pure
    projection of that contract + the checked ids — it MUST NOT reimplement
    the DSM logic in JS. A rule change ships through `meta_contract` first,
    and `test_unittest::test_meta_rules_match_engine_every_subset` locks
    equivalence across every id subset, so the UI can never drift from
    the engine. If you add a rule dimension, expose its primitive in
    `meta_contract` and extend that test in the same change.
13. **The web page is an embeddable module UI, not a standalone shell.**
    `static/index.html` exposes `window.createDiagnosisModule({root,
    apiBaseUrl})` and one mount point (`#diagnosis-root`). The standalone
    `GET /` shell bootstraps that fn against `document.body` with
    `embedded: false`; the larger Insight dashboard imports the same fn
    and calls it with `embedded: true` so it gets NO second standalone
    topbar, NO `history.replaceState` mutation, NO host-navigation
    placeholder. Don't bake a standalone shell, topbar, or ``Back to
    dashboard`` button back into the served bytes — host owns navigation.
    `test_embed.py` locks the contract (constructor signature, no host
    chrome / nav placeholder, topbar gated on `!embedded`, history gated
    on `!embedded`, route layer untouched, byte-clean bypass serve).
14. **Audit event seam: every decision-bearing PUT persists a local
    audit event, and the dashboard seam exposes the trail for the
    future Logs module.** `diagnosis_api.put_session` calls
    `_dump_for_audit(code)` (from `dashboard.py`, re-exported by
    `api.py`) AFTER `store.put` on every PUT — both the debounced
    checkbox-toggle writes from the UI AND the explicit confirm /
    bypass decision writes. The hook delegates to
    `store.audit_snapshot`, which INSERTs a row into the `audit` table
    whose `snapshot` is the JSON of the source session row (verbatim
    `decision` + `checked` ids) — NO derived `evaluation` key, so an
    audit row can never be read as a server auto-diagnosis (HANDOFF
    §6.1 extends through the audit trail). The dashboard seam's read
    route `GET /internal/diagnosis/audit/{code}` exposes the
    persisted trail as `{code, snapshots:[...]}` (oldest first) — it
    READS, never writes a snapshot on demand. An unknown /
    never-audited code yields an empty `snapshots` list (NOT a 404);
    `code` is the free-text local session key, and an empty trail is a
    legitimate state. Init alone does NOT audit — empty-session
    creation is not a clinician decision. Auth policy: `psychiatrist`
    or `admin` (same read policy as `_meta` / `_csrf`); admins read
    for review, never mutate. Lock families: `test_unittest.py::
    TestAuditSeam` (boot self-check loads it via `_http_selfcheck`),
    `test_routes.py::test_audit_seam_is_in_dashboard_seam_only` (seam
    ownership), and `test_routes.py` pathset / route-order assertions
    (the dashboard seam now owns ``/internal/diagnosis/audit/{code}``
    and it precedes ``/{code}``).

---

## 10. Gotchas that cost time if you don't know

- **The browser page is NOT a second implementation of the DSM rules.**
  `GET /diagnosis/_meta` returns a `rules` contract (`criteria.meta_contract`)
  and the JS `renderLocalEvaluation` consumes it — symptom / core / duration /
  guard ids + thresholds all come from the server. Don't add a new DSM rule to
  `evaluate()` and "also update the frontend" by hand-rolling JS constants;
  expose the new primitive in `meta_contract()` and the UI picks it up.
  `test_unittest::test_meta_rules_match_engine_every_subset` locks the
  equivalence over every id subset, so a rule change that forgets the
  contract FAILS the boot self-check.
- **`store` is a process-wide SQLite repository.** Its connection is
  process-scoped and reused; tests that don't `store.reset()` will leak state
  across runs. The `_http_selfcheck()` resets it at start and end — mirror
  this. `_store_selfcheck()` instead uses a `tempfile.mkstemp` DB path so it
  never touches the real store.
- **DB location: `DIAGNOSIS_DB_PATH` env var.** Defaults to
  `diagnosis_store.db` in the current working directory. Override per-process
  for tests / multi-tenant deployments.
- **`/diagnosis/{code}/init` returns `{"created": False}`** if the session
  exists — it does NOT 409. The frontend ignores the result; it just guarantees
  a session exists for the subsequent GET.
- **GET `/diagnosis/{code}` 404s for unknown codes.** The frontend POSTs
  `/init` first to prevent this; the contract is "caller creates sessions
  via PUT/init before GET."
- **`get_app()` is lazy** because importing `app.py` requires FastAPI.
  Keep it lazy — `criteria.py` must import without FastAPI installed.
- **`renderServer` in the HTML has a buggy-looking `guardsMet` line** that
  always evaluates truthy. It's harmless because the badge is driven by
  `updateBadge` separately. Don't "fix" it without testing the badge path;
  the line is dead but the surrounding logic isn't.
- **`A6` is duration, not a symptom.** Counting it as a symptom is the
  single most common bug in this kind of code. The engine already handles
  it via the `duration: True` flag — don't roll your own.
- **`__main__.py` runs self-checks imported lazily inside `main()`.** Keep
  them lazy so importing `diagnosis.__main__` for tooling doesn't boot
  FastAPI/uvicorn/TestClient.
- **No `DESIGN.md` lives in this repo.** It's referenced in comments and
  the README; it lives in the parent Insight app. Don't go looking for it
  here.
- **CSRF token is per-process.** The HMAC secret regenerates on every
  boot unless you pin `DIAGNOSIS_CSRF_SECRET`. That means: a token minted
  by one server process is invalid against another. Single-process dev is
  fine; multi-worker / multi-process MUST set the env var (and behind TLS
  set `DIAGNOSIS_CSRF_SECURE=1` so the cookie is Secure). Tests pin it via
  `csrf.reset_secret_for_tests`.
- **Auth runs before CSRF on writes.** Don't reorder the `Depends(...)`
  clauses on `init_session` / `put_session` — auth-first means an
  unauthenticated caller gets a clean 401 and never learns the CSRF
  token exists.
- **Patient lookup is opt-in.** Default unset → adapter disabled →
  `patient_id == code` (diagnosis-local). Production inside Insight sets
  `DIAGNOSIS_PATIENT_LOOKUP=1` + `PATIENT_BASE_URL` so the row binds to
  the canonical INSIGHT registry id. `test_patient.py` pops/pushes the
  env per case — don't leave it set across test runs or the next test
  suite's writes will hang against a dead registry.
- **`{code}` is still the local session key when lookup is enabled.** The
  REST contract doesn't change — only `sessions.patient_id` does. Don't
  add a `?patient_id=...` query param or re-route on canonical id; the
  cross-module identity lives in the row, not the URL.
- **Don't pre-nest `include_router` in `api.py`.** Composing the three
  seam sub-routers with `router.include_router(sub)` *inside* `api.py`
  and then mounting `diagnosis.api.router` into the standalone app (or
  into Insight) silently drops `/diagnosis/_csrf` from OpenAPI —
  FastAPI only unwraps one level of `include_router` when the parent
  app mounts us, so the extra nesting layer loses routes. The
  composition instead appends the sub-routers' `APIRoute` objects onto
  `router` in the `(page, dashboard, diagnosis)` order. The trap is
  silent at the call site (the route still dispatches correctly at
  runtime via the sub-router's own routes), so OpenAPI / OpenAPI-driven
  clients are the casualty. `test_routes.py`'s
  `test_composed_router_has_all_paths_from_app_openapi` guards it.
- **The graphify "Import Cycles" block through `__init__.py` is a false
  positive.** The static crawler models `diagnosis/__init__.py` as a node
  and draws `__init__ -> api.py` (from `from .api import router`) plus a
  spurious `deps.py -> __init__.py` edge (deps actually imports
  `.auth` / `.csrf` / `.store`, none of which import the package root).
  There is **no runtime import cycle** — `python -c "import diagnosis.api"`
  imports cleanly and the package boots. Don't refactor to chase the
  cosmetics; the seams are intentional.
- **Readiness != liveness.** `/health` means "the process is up"; `/ready`
  means "my dependencies are configured + reachable so a clinical request
  won't 401 / 422." A load balancer should gate traffic on `/ready`, not
  `/health`. The probe deliberately does NOT call the auth service or the
  patient registry — both need the user's `Cookie`, so a cookieless probe
  would 401 (false negative) or surface the configured base URL (leak). The
  auth check reports `bypass: True` when `DIAGNOSIS_AUTH_BYPASS=1` is set:
  that is the SAME signal a production readiness gate should alarm on, not
  a reason to add a live call. If you find yourself "making readiness more
  thorough" by adding a live round-trip, STOP — you are about to leak a
  secret or destabilise a load balancer. See `readiness.py` invariant §9.11.
- **`deps.py` reads `DIAGNOSIS_AUTH_BYPASS` at import time.** The bypass shim
  is wired in `deps.py` when the module is first imported; setting the env
  afterwards does NOT re-wire the dep callables (they're already bound). So
  `python -m diagnosis` only runs the in-process self-checks end-to-end when
  `DIAGNOSIS_AUTH_BYPASS=1` is preset in the shell (the parent package is
  imported before `__main__.main()` runs its `setdefault` — the setdefault
  runs first inside `main()`, then the first `diagnosis.*` import binds
  deps). Tests that need the real dep pop the env BEFORE the first
  `diagnosis.deps` import. `Settings.mock_auth` mirrors the same env flag for
  inspection but does NOT drive the deps wiring — deps keeps reading the env
  directly so the existing pre-import ordering contract is unchanged.
- **Settings is a frozen snapshot, not a config file.** `config.py :: _load`
  reads the env ONCE at import time into a frozen `Settings` dataclass; the
  `settings` singleton is the result. Production code never writes to it.
  Tests mutate the CONSUMER module globals (`auth.AUTH_BASE_URL`,
  `patient.PATIENT_BASE_URL`, `csrf._SECRET`) via the existing
  `reset_*_for_tests` hooks — they do NOT rebuild the singleton. Don't add a
  setter to `Settings`; the test surface relies on the mutable per-module
  shadow, not a mutable shared config. A fresh env that needs a different
  snapshot requires re-importing / `importlib.reload`-ing the affected module
  (see `test_config.py` for the pattern).
- **Don't scatter `os.environ.get` in consumer modules.** `config.py` is the
  single knob list. Adding a new integration knob means extending `Settings`
  + `_load` and re-pointing the consumer at `settings.<new>`, NOT adding a
  fresh `os.environ.get` in `auth.py` / `patient.py` / `csrf.py` / `app.py`
  / `dashboard.py` / `__main__.py`. The lone exceptions kept on purpose:
  `deps.py` re-reads `DIAGNOSIS_AUTH_BYPASS` at import (the pre-import
  ordering contract above) and `readiness._check_auth` / `_check_patient`
  read the module-level `AUTH_BASE_URL` / `PATIENT_BASE_URL` globals at call
  time so a test-only swap surfaces in the probe without re-importing.
- **`check_readiness()` swallows DB faults on purpose.** A paged operator
  does not want a `sqlite3.OperationalError` traceback from the readiness
  endpoint; they want `checks.db.ok == False` and a uvicorn log line. If
  you surface the exception message in the response you'll also surface
  the on-disk DB path (PII-adjacent in multi-tenant deploys). Don't.

---

## 11. Glossary

- **Insight** — the larger clinical decision support app this module plugs into.
- **DSM-5-TR** — *Diagnostic and Statistical Manual of Mental Disorders, 5th ed.,
  Text Revision* (APA, 2022). The authoritative reference; this module is a
  charitable paraphrase, not a substitute.
- **Criterion A** — characteristic symptoms (≥2, ≥1 from core triad A1–A3,
  plus duration A6).
- **Core triad** — A1 delusions, A2 hallucinations, A3 disorganized thinking.
- **Criterion B** — functional impairment. **C** — schizoaffective exclusion.
  **D** — substance / medical exclusion. Each has exactly one item (B1/C1/D1).
- **Confirmed** (`decision: "confirmed"`) — psychiatrist affirms criteria met.
- **Definite** (`decision: "definite"`) — psychiatrist bypasses the checklist.
  Both are the clinician's explicit voice; the model's `met` never
  auto-decides either. The invariant is a tested contract
  (`test_unittest.TestClinicianAuthority`, HANDOFF §6.1) — the boot
  self-check fails fast if it is broken.
- **Deep module** — Ousterhout's term: small interface hiding substantial
  implementation. The README and `__init__.py` docstring both invoke it.
- **Rule contract** — `criteria.meta_contract()`, served by
  `GET /diagnosis/_meta` as the `rules` field. The set of primitives
  (symptom / core / duration / guard ids + thresholds) the browser page
  consumes for its optimistic display. The DSM rules exist ONCE in
  `evaluate()`; the UI NEVER re-implements them in JS — it projects them
  from this contract. Locked against the engine across every id subset by
  `test_unittest::test_meta_rules_match_engine_every_subset` (see §9.12).
- **Canonical patient id** — the `patient.id` minted by the INSIGHT "Add
  New Patient" primitives app, the row the larger Insight app joins on.
  Contrast with the free-text `{code}` the clinician types, which is the
  local session key only. `resolve_patient(code) -> Patient(id=canonical, ...)`
  is the only seam between the two.
- **Add New Patient** — the INSIGHT primitives-app feature that creates /
  looks up patients in the central registry. The diagnosis module does
  NOT call the "create" path — only the lookup (`GET /api/patients/lookup`).
  A code that doesn't exist in the registry yet must be created there
  first; the diagnosis module reports it as 422 "Unknown patient code".
- **Seam** (post-split) — one of the three route modules composing the
  public `router`: `page.py` (browser page), `dashboard.py` (Dashboard
  discovery + audit-log seam + audit snapshot hook), `diagnosis_api.py`
  (protected per-patient REST). `deps.py` holds the shared store + role/CSRF wiring
  consumed by every seam; `api.py` composes them and re-exports the
  contract symbols. Pre-split, all of this lived in `api.py`.
- **Audit event seam** — the local audit trail wiring: `diagnosis_api.put_session`
  invokes `_dump_for_audit(code)` (owned by `dashboard.py`, re-exported by
  `api.py`) after every decision-bearing PUT; the hook INSERTs a row into the
  `audit` table via `store.audit_snapshot` whose snapshot is the source session
  row (decision + checked ids) — NO `evaluation` key. The dashboard seam
  exposes the persisted trail through `GET /internal/diagnosis/audit/{code}`
  read-only, so the future Insight Logs module reads chronological audit
  events without triggering writes. A never-audited code returns an empty
  trail (`{code, snapshots:[]}`), NOT a 404 — `code` is the free-text local
  session key. Init alone does NOT audit (empty-session creation is not a
  clinician decision). Locked by `test_unittest.TestAuditSeam` and `test_routes.py`.
  HANDOFF §9.14.
- **Settings adapter** — `config.py :: Settings` + `settings` singleton.
  The frozen snapshot of every integration knob the module reads: DB path,
  auth URL + timeout, patient URL + timeout + lookup flag, CORS origins,
  mock-auth flag, CSRF secret + secure flag, module base path, host/port.
  Sourced from the env once at import; production never writes. The
  `reset_*_for_tests` hooks mutate the consumer module globals (not the
  singleton) so the existing test surface stays intact. ``module_id``
  + ``launch_href`` derive from ``module_base_path`` so a non-default
  mount prefix flows through to the Dashboard descriptor. Locked by
  `test_config.py` + `_config_selfcheck`.
- **Canonical REST contract** — `docs/api-contract.md`. The README's
  interface table is a summary; this doc is the authoritative spec for
  route shapes, request/response bodies, error codes, auth, CSRF,
  route discovery, and invariants. If the README and this doc disagree,
  this doc wins. The route catalogue in §2 is locked against the live
  router by
  `test_unittest.TestRestContract.test_api_contract_doc_lists_every_live_route`
  so a route add/remove/rename without a matching doc edit fails the
  boot self-check. Added by the "Write canonical REST contract docs"
  issue.

---

## 12. If you only read four files

1. `diagnosis/api.py` — the composed router: how the three seams are wired and
   ordered, plus `_http_selfcheck` and the back-compat re-exports.
2. `diagnosis/diagnosis_api.py` — the protected per-patient REST contract (the
   seam with the actual clinical state mutation).
3. `diagnosis/criteria.py` — the rules and the only pure logic. Owns
   `evaluate()` AND `meta_contract()` (the rule contract the browser page
   consumes — see §9.12).
4. `README.md` — the user-facing summary; everything else extends it.
5. `docs/api-contract.md` — the canonical REST contract (route shapes,
   request/response bodies, errors, auth, CSRF, route discovery,
   invariants). The README table is a summary; this doc is the
   authoritative spec. Locked against the live router by
   `test_unittest.TestRestContract.test_api_contract_doc_lists_every_live_route`.

Everything else (`store.py`, `app.py`, `__main__.py`, `__init__.py`,
`index.html`, `page.py`, `dashboard.py`, `deps.py`, `config.py`) is wiring
around those. Understand the three seams + `criteria.py` and the rest is
mechanical — except `store.py`, which deserves a full read before you change
the persistence story, `patient.py`, which deserves a full read before you
touch anything that writes the `patient_id` column, and `config.py`, which
is the single source for every integration knob (read it before adding a
new env var anywhere). `test_routes.py` is the readable spec for the seam
split; `test_config.py` is the readable spec for the settings adapter.
