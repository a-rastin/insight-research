# Progress Tracker

Update this file after every meaningful implementation change.

## Current Phase

- Phase 0 architecture decisions

## Current Goal

- INS-008: Resolve intended use, population, and diagnosis gates (in progress).

## Completed

- INS-007 now has versioned `contracts/model-manifest-v1.json` and its JSON
  Schema. The manifest inventories all 13 `BNs/` topics, 23 source model
  artifacts, seven model-only module copies, four BN Manager registry models,
  and the registry XSD without modifying protected artifacts.
- BN Manager is the sole runtime owner. Ten exact-copy groups are hash-locked;
  legacy module copies are designated for retirement; orphaned copies are
  quarantined; and `.net`, non-registry XML, missing-source, and unapproved
  models are blocked from runtime admission.
- Both manifest files passed `python3 -m json.tool`; Draft 2020-12 schema
  validation passed with `jsonschema`; focused manifest tests passed with
  `python3 -B -m unittest tests/test_model_manifest.py -v` (5 tests); full
  architecture discovery passed with `python3 -B -m unittest discover -s tests
  -v` (25 tests); BN Manager passed with `uv run --with httpx2 python -B -m
  unittest discover -s tests -v` (45 tests).
- INS-006 received task-level HITL approval to reject assistant scope for v1.
  Added ADR-0005 and versioned `contracts/assistant-policy-v1.json`; no provider,
  page context, tools, conversation storage, or provider transmission is enabled.
- The assistant policy requires structural identifier omission before
  defense-in-depth scrubbing, forbids names, codes, MRNs, contact details, and
  dates, exposes only a disabled-provider UI state, and cannot block or mutate
  clinical workflows.
- Verified JSON syntax with `python3 -m json.tool
  contracts/assistant-policy-v1.json`; focused policy tests passed with
  `python3 -B -m unittest tests/test_assistant_policy.py` (5 tests); full
  architecture discovery passed with `python3 -B -m unittest discover -s tests
  -v` (20 tests).
- INS-005 received task-level HITL approval: Dashboard owns navigation only;
  Authentication owns account administration and security audit; clinical
  modules retain provenance; emitting modules retain operational logs; and
  deployment operations owns metadata-only orchestration and aggregate records.
- Added ADR-0004 and versioned `contracts/administration-operations-v1.json` with
  admin-versus-psychiatrist permissions, PHI-safe backup metadata, owner-enforced
  retention, staged restore verification, and target-module-only restore writes.
- Verified JSON syntax with `python3 -m json.tool
  contracts/administration-operations-v1.json`; focused ownership tests passed
  with `python3 -B -m unittest tests/test_administration_operations.py` (5
  tests); full architecture discovery passed with `python3 -B -m unittest
  discover -s tests -v` (15 tests).
- INS-004 received task-level HITL approval: Follow-up is an orchestration flow,
  Add New Patient remains sole Encounter and Follow-up Delta writer, and a
  dedicated Suicide Risk module owns structured C-SSRS assessments.
- Added ADR-0003 and versioned `contracts/clinical-ownership-v1.json`; the
  registry assigns exactly one writer to every scoped entity and preserves
  Treatment Plan ownership of plan supersession.
- Added initial encounter, follow-up encounter, unknown risk, unavailable
  assessment, and supersession examples. No C-SSRS question or score was
  inferred; missing required risk blocks risk-dependent processing.
- Verified JSON syntax with `python3 -m json.tool
  contracts/clinical-ownership-v1.json`; focused ownership tests passed with
  `python3 -B -m unittest tests/test_clinical_ownership.py` (4 tests); full
  architecture discovery passed with `python3 -B -m unittest discover -s tests
  -v` (10 tests).
- INS-003 received HITL approval to select the simplest workable service-auth
  mechanism and chose per-service HMAC-SHA256 assertions over mTLS and OAuth2
  client credentials.
- Added ADR-0002 and versioned `contracts/internal-service-auth-v1.json` covering
  service identity, exact request signing, per-caller method/path capabilities,
  cookie forwarding, CSRF boundaries, trace propagation, SSRF allowlists,
  revocation, background-call limits, finalization revalidation, and audit
  separation.
- Added browser, user-attributed server, revoked-session, disabled-account,
  role-change, background-job, and untrusted-destination contract examples.
- Verified JSON syntax with `python3 -m json.tool
  contracts/internal-service-auth-v1.json`; verified focused contract behavior
  with `python3 -B -m unittest tests/test_internal_service_auth.py` (4 tests
  passed); full architecture discovery passed with `python3 -B -m unittest
  discover -s tests -v` (6 tests passed).
- INS-002 received explicit HITL approval for nginx on public container port
  8080, supervisord as PID 1, Python 3.13, Node.js 22 LTS, loopback module ports
  8101-8109, all-required readiness aggregation, and a 30-second graceful stop.
- Added ADR-0001 with alternatives, trade-offs, module port/base-path and health
  map, non-root process policy, separate module data directories, relative
  browser routing, and Windows Docker Desktop and Ubuntu VPS paths.
- Added machine-readable `deploy/runtime-policy.json` and a static policy test
  that rejects public module ports, duplicate ports, root execution, missing
  health entries, non-loopback module binds, duplicate data directories, and
  absolute browser service URLs.
- Verified ADR schema and relative links plus deployment policy with
  `python3 -m unittest tests/test_runtime_policy.py` and full discovery via
  `python3 -m unittest discover -s tests -v` (2 tests passed in each run).
- Read all normative files under `context/`; no file under `doc/` was read.
- Inventoried all nine functional modules, their current repository state,
  runtimes, dependencies, start/test commands, routes, migrations, and contract
  or schema versions.
- Ran every module's documented full suite. Runtime and test storage used
  temporary paths where supported; Severity ran from a temporary worktree copy
  because its test writes to `data/assessments.json`.
- Verified module Git status after testing. No tracked module changes were added.
  Diagnosis-created bytecode residue was removed; the temporary Severity copy
  was removed.

## In Progress

- INS-008 intended-use, population, and diagnosis-gate decision packet.
  Psychiatrist/product resolutions and supporting evidence for DG-01, DG-03,
  and DG-07 are pending; unsupported-case behavior remains undefined.
- INS-007 model-source ownership and duplicate-artifact manifest packet.
  Technical inventory and fail-closed governance controls are implemented;
  attributable BN-owner and clinical-model-owner approvals remain unresolved.
- INS-006 assistant provider, data policy, and UI-boundary decision packet.
  V1 scope is rejected and fail-closed controls are implemented. Named
  accountable privacy, security, and product owners remain unresolved.

## Repository Baseline

Recorded before tests with `git status --short` and `git rev-parse HEAD` in each
available nested repository. Dirty files predated INS-001 and were preserved.

| Module | Commit | Baseline status |
| --- | --- | --- |
| Authentication | unavailable | No Git repository at module root |
| Dashboard | `9f295f2fb404fc99844cd98ef75c293fea15d801` | Dirty, 22 paths |
| Add New Patient | `71e79eab47021ec40650ca07cceb9fe472bf2ac1` | Dirty, 5 generated `graphify-out/` paths |
| Diagnosis | `07bc16fdad6f76afddbb526b3c557a583acd0019` | Dirty, 52 paths |
| Severity | `bace9714a6a2c2c10186dec068688f51d440e086` | Dirty, untracked `graphify-out/` |
| Medical History | `714e91b091efd5a5fbb1360c2d89bc58c7045abd` | Dirty, 19 paths |
| DDI Checker | `e463c6cf579d3ca3eb54c75aa27d7853ead67999` | Dirty, 35 paths |
| BN Manager | `998339219b83e9533651871e7e2e5f9f7952d55b` | Dirty, 15 paths; repository is one level below wrapper directory |
| Treatment Plan | `29e1cd0fe4a82b06f5decf3ca4410ff1946b83bc` | Dirty, 99 paths |

Host tools: Python command unavailable; `python3 3.12.3`; Node.js `22.23.1`;
npm `10.9.8`; Git `2.43.0`; Docker `29.6.2`; uv `0.11.31`.

## Module Inventory

### Authentication

- Runtime/dependencies: Python version undeclared; FastAPI `>=0.110`, Uvicorn
  `>=0.27`, bcrypt `>=4.1`, PyJWT `>=2.8`; SQLite.
- Start: `pip install -r requirements.txt`; `python main.py` or
  `uvicorn modules.auth.main:app --reload`.
- Test: `python -B -m unittest discover -s tests`.
- Routes: `GET /`, `/healthz`, `/readyz`, `/api/auth/health`,
  `/api/auth/ready`, `/api/auth/csrf`, `/api/auth/session`,
  `/api/auth/disclaimer`, `/api/auth/admin/users`, `/api/auth/docs`;
  `POST /api/auth/login`, `/api/auth/password/change`,
  `/api/auth/disclaimer/accept`, `/api/auth/logout`, `/api/auth/register`,
  `/api/auth/admin/users/{user_id}/disable`,
  `/api/auth/admin/users/{user_id}/enable`,
  `/api/auth/admin/users/{user_id}/reset-password`;
  `PATCH /api/auth/admin/users/{user_id}/role`; static catch-all.
- Migrations/schema: SQLite `user_version=6`; migrations 001 users, 002
  sessions, 003 role normalization, 004 account/login state, 005 disclaimer
  acceptances, 006 audit log. Contract final for INSIGHT v1; disclaimer version
  `2026-07-06`; standalone schema absent.

### Dashboard

- Runtime/dependencies: Python and Node versions undeclared; unpinned FastAPI
  and Uvicorn; package `0.1.0`; SQLite.
- Start: `npm start` or
  `python -m uvicorn dashboard_backend.main:app --host 127.0.0.1 --port 4173`.
- Test: `npm test`, expanding to `python -m unittest && node
  test_dashboard_frontend.mjs`.
- Routes: `GET /`, `/dashboard/`, `/healthz`, `/readyz`,
  `/api/auth/session`, `/internal/dashboard/workspace`,
  `/internal/dashboard/summary`,
  `/internal/dashboard/module-routes/{module_id}`;
  `POST /internal/dashboard/session`,
  `/internal/dashboard/disclaimer/accept`; `DELETE /internal/dashboard/session`.
- Migrations/schema: startup DDL drops four legacy tables, creates
  `dashboard_sessions` and `workspace_events`, and adds disclaimer acceptance.
  No numbered migrations, interface version, or schema version.

### Add New Patient

- Runtime/dependencies: Python `3.13+`, Pydantic v2; unpinned FastAPI,
  Uvicorn, Pydantic; SQLite.
- Start: `uvicorn add_new_patient_backend.main:app --port 4173` or
  `uvicorn server:app --port 4173`.
- Test: `python -m unittest test_add_new_patient_backend.py`; optional frontend
  suite `node --test test_frontend.mjs`.
- Routes: `GET /api/health`, `/api/auth/session`,
  `/api/add-new-patient/csrf`, `/api/patients`,
  `/api/patients/{id_or_code}`, `/api/patients/{id_or_code}/intake`,
  `/internal/dashboard/module-routes/add-new-patient`, `/`,
  `/modules/add-new-patient`, and static catch-alls; `POST /api/patients`.
- Migrations/schema: startup DDL creates normalized `patients` and
  `patient_intake_records`, migrates legacy denormalized patients transactionally.
  Identifier semantics v1; JSON schema and runtime DDL have no declared version.

### Diagnosis

- Runtime/dependencies: Python constraint absent; app `0.1.0`; FastAPI
  `>=0.110`, Uvicorn `>=0.27`, Pydantic `>=2.5`, httpx2 `>=1.0`, unbounded
  httpcore; SQLite.
- Start: `python -m diagnosis` or `python -m diagnosis --port 8010 --reload`.
- Test: nine documented module commands from `python -m test_unittest` through
  `python -m test_embed`; no consolidated full-suite command.
- Routes: `GET /`, `/health`, `/ready`, `/diagnosis/_meta`,
  `/diagnosis/_csrf`, `/internal/dashboard/module-routes/{moduleId}`,
  `/internal/diagnosis/audit/{code}`, `/diagnosis/{code}`;
  `POST /diagnosis/{code}/init`; `PUT /diagnosis/{code}`.
- Migrations/schema: startup DDL creates `sessions` and `audit`; no migration
  files, API version, schema version, or machine-readable schema.

### Severity

- Runtime/dependencies: Node version undeclared; ESM; Express `^4.21.2`, locked
  `4.22.2`; package `1.0.0`; UI `v1.0.0-alpha`.
- Start: `npm install`; `npm start` (`node server.js`).
- Test: `node test_api.js`; no `npm test` script.
- Routes: `GET /api/severity/:patient_code`; `PUT
  /api/severity/:patient_code`; CORS `OPTIONS`; static and SPA fallback `GET`.
- Migrations/schema: none. Flat `data/assessments.json`, keyed by patient code;
  no API/schema version or storage-path override.

### Medical History

- Runtime/dependencies: Node `>=18`; no dependencies; package `1.0.0`.
- Start: `npm start` or `npm run dev`, both `node server.js`.
- Test: `npm test` (`node --test`).
- Routes: `GET /api/internal/medical-history/health`,
  `/activation/{code}`, `/options`, `/submissions`, `/schema`; `POST
  /api/internal/medical-history/activate`, `/submissions`; CORS and static
  fallback. All medical-history routes use `/api/internal/medical-history`.
- Migrations/schema: none. JSON-array persistence; submission model v2 and
  dataset/schema `2.0.0`; API version absent.

### DDI Checker

- Runtime/dependencies: static browser module; Node version undeclared for CLI
  and tests; package `0.1.0`; no third-party dependencies or lockfile.
- Start: open or statically serve `index.html`; ingestion `npm run ingest`;
  validation `npm run validate` and `npm run validate:clinical`.
- Test: `npm test` (`node --test test/*.test.mjs`).
- Routes: none; no HTTP service or REST contract.
- Migrations/schema: browser storage envelope migration v2; KB schema `1.0.0`,
  parser `2.0.0`, active KB `ikb-2026-07-12-bfeaa1ec` in
  `draft_parsed_pending_admin_review`; no standalone schema or OpenAPI.

### BN Manager

- Runtime/dependencies: Python `>=3.11`; package `0.1.0`; FastAPI `>=0.100`,
  lxml `>=5.0`, Uvicorn `>=0.20`; lock resolves FastAPI `0.139.0`, lxml
  `6.1.1`, Uvicorn `0.50.2`.
- Start: `python server.py`; installed script `bn-manager-backend`.
- Test: `python -m unittest discover -s tests -v`.
- Routes: `GET /api/health`, `/api/ready`, `/api/bn-manager/v1/contract`,
  `/models`, `/models/schema/xml-0.3`, `/models/{stable_id}`,
  `/internal/dashboard/module-routes/bn-manager`, `/modules/bn-manager`, and
  assets; `POST /api/bn-manager/v1/dashboard/evaluate`,
  `/add-new-patient/evaluate`, `/follow-up/evaluate`, `/models/validate`.
- Migrations/schema: no DB. Contract `2.0.0`, API prefix
  `/api/bn-manager/v1`, XML BIF/XSD `0.3`, four registry models at `1.0.0`.

### Treatment Plan

- Runtime/dependencies: Python package requires `>=3.11`; Node locked Vite
  requires `^20.19.0 || >=22.12.0`; backend package `0.1.0`; React `19.2.7`,
  Vite `8.1.4`, Vitest `4.1.10`; backend versions are locked.
- Start: `python -m treatment_plan` via `run.ps1`; frontend `npm run dev` or
  `npm run build`; Docker Compose supported.
- Test: `python -m unittest discover -s tests -v`; frontend `npm test`.
- Runtime routes: `GET /health`, `/ready`,
  `/api/treatment-plan/v1/session`, `/plans/{plan_id}`,
  `/plans/{plan_id}/provenance`, `/plans/{plan_id}/audit`,
  `/observability/dashboard`, `/metrics`; `PATCH /plans/{plan_id}/draft`;
  `POST /plans/{plan_id}/finalize`; plan paths use
  `/api/treatment-plan/v1`. OpenAPI additionally declares contract, schema,
  recommendation-run, and supersede routes not wired at runtime.
- Migrations/schema: migrations 0001 through 0006, each with down migration,
  covering runtime records, edit ledger, finalized plans, immutability,
  supersession, and full persistence. OpenAPI/manifest/schema registry `1.0.0`;
  runtime draft advertises `1.1.0`, absent from registry.

## Test Baseline

| Module | Result | Evidence |
| --- | --- | --- |
| Authentication | PASS | 14 tests |
| Dashboard | PASS with runner deviation | Documented `npm test` failed because `python` command is absent; equivalent `python3 -m unittest && node test_dashboard_frontend.mjs` passed 15 tests |
| Add New Patient | PASS | 42 backend and 3 frontend tests |
| Diagnosis | PASS only as documented separate processes | 156 tests/checks passed. Consolidated discovery failed 18 tests and errored once because import order retained auth-enabled settings; module documents separate commands |
| Severity | PASS | Integration script passed from isolated copied worktree |
| Medical History | PASS | 4 tests |
| DDI Checker | PASS | 49 tests |
| BN Manager | FAIL | uv-created isolated environment collected 31 tests: 29 passed, 2 import errors because declared dependencies omit `httpx2`, required by Starlette `TestClient` |
| Treatment Plan | PARTIAL | Backend passed 112 tests with PostgreSQL repository contract skipped because `TP_TEST_POSTGRES_DSN` is unset; frontend failed before collection because optional native package `@rolldown/binding-linux-x64-gnu` is absent |

Commands used temporary directories under `/tmp/opencode` and explicit storage
variables: `AUTH_DB_PATH`, `DASHBOARD_DB_PATH`, `ADD_NEW_PATIENT_DB_PATH`,
`DIAGNOSIS_DB_PATH`, `MEDICAL_HISTORY_DATA_DIR`, and `TP_DATABASE_PATH`.

## First Failing Integration Boundary

- Authentication `GET /api/auth/session` returns a flat payload with lowercase
  role and no concrete nested session object. Dashboard and Add New Patient
  adapters expect nested `session`/`user` objects, uppercase role values, and a
  session ID. Their real Authentication integration therefore rejects or cannot
  normalize the current canonical response. Resolve the Authentication session
  contract and consumer adapters before testing later clinical boundaries.

## Next Up

- Obtain attributable BN-owner and clinical-model-owner review before changing
  any model approval state or allowing a registry model at runtime. Retire the
  seven model-only module copies only through an approved migration after all
  consumers use BN Manager REST.
- Keep assistant provider integration, prompt controls, page context, tools, and
  conversation storage disabled. Any future enablement requires a superseding
  approved policy covering provider, retention, encryption, access, deletion,
  backup, provider use, page allowlist, and read-only tools, plus runtime tests.
- Define approved retention periods, encryption/key-management controls,
  protected artifact storage, recovery objectives, and named accountable owners
  before implementing production backup or restore.
- Define versioned owner-local administration, log, backup, restore-verification,
  and retention APIs before wiring Dashboard or deployment orchestration.
- Obtain approved C-SSRS source/licensing contract and named clinical owner
  before defining any instrument questions, scoring, terminology, or release
  behavior.
- Define versioned Add New Patient Encounter and Follow-up Delta REST/schema
  contracts before implementing follow-up persistence or orchestration.
- Create the independently runnable Suicide Risk module/API/schema only after
  its instrument source, licensing, and clinical governance are approved.
- Implement ADR-0002 in module-local inbound/outbound adapters: issue per-service
  keys and capability sets, add signing/verification and nonce replay caches,
  narrow existing full-cookie/authorization forwarding, and run provider and
  consumer security tests.
- Implement ADR-0001 in a separate deployment packet. Add unified image,
  gateway and supervisor configuration, module configuration adapters, missing
  liveness/readiness routes, graceful-shutdown wiring, and Docker Desktop/VPS
  integration tests without merging module boundaries.
- Define and approve one versioned Authentication session response shape, then
  align Dashboard and Add New Patient adapters and provider/consumer tests.
- Add BN Manager's missing test dependency or test extra and rerun its suite.
- Restore Treatment Plan frontend optional native dependency and rerun Vitest;
  provide disposable PostgreSQL DSN to execute its skipped repository contract.

## Open Questions

- Attributable BN owner and clinical model owner are unnamed. All four registry
  models therefore remain unapproved in the INS-007 manifest and blocked from
  governed runtime admission despite their current BN Manager registry label.
- Named accountable privacy, security, and product owners for ADR-0005 remain
  unidentified. Assistant v1 remains rejected and disabled; no policy gap may
  be interpreted as approval.
- Named accountable architecture, security, and operations owners for ADR-0004
  remain unidentified. Task-level approval resolves ownership selection but not
  release governance.
- Retention periods, backup encryption and key custody, artifact storage,
  recovery objectives, and disaster-recovery approval are not yet defined;
  production backup and restore remain blocked.
- Named accountable product, clinical, and architecture owners for ADR-0003
  remain unidentified; task-level approval resolves ownership selection but not
  release governance.
- Approved C-SSRS source/licensing contract is unavailable. Suicide Risk cannot
  define questions or scoring, and required risk-dependent processing remains
  fail-closed.
- Named accountable Architecture and Operations owners remain unidentified;
  task-level HITL approval resolved INS-002 selection but not release governance.
- Which Authentication session payload is authoritative: current flat v1
  contract or nested shape consumed by Dashboard and Add New Patient?
- Should the repository baseline require Python command compatibility, or should
  module scripts standardize on `python3` for this Linux environment?
- No live PostgreSQL test DSN is available; Treatment Plan's PostgreSQL contract
  remains unverified.

## Architecture Decisions

- ADR-0005 rejects assistant scope for v1: no provider, transmission, retained
  conversation, page context, or tools. Unsupported policy resolves to disabled,
  forbidden identifiers require structural omission plus scrubbing, and
  assistant failure cannot affect clinical workflows.
- ADR-0004 keeps Dashboard navigation-only, assigns account and security-audit
  data to Authentication, clinical provenance to its clinical owner, operational
  logs to each emitter, module backup/restore to each module, and metadata-only
  aggregate orchestration to deployment operations. Restore is target-module-only
  and rejects mismatched module identities before writes.
- ADR-0003 makes Follow-up an orchestration flow, keeps Encounter and Follow-up
  Delta ownership in Add New Patient, assigns structured C-SSRS assessments to a
  dedicated Suicide Risk module, and blocks score/question inference until an
  approved source/licensing contract exists.
- ADR-0002 selects per-service HMAC-SHA256 request assertions, current-session
  revalidation through Authentication for user-attributed calls, service-only
  background identity, first-module browser CSRF enforcement, exact outbound
  allowlists, safe UUID trace propagation, and separate security audit and
  clinical provenance.
- ADR-0001 selects nginx as internal gateway, supervisord as PID 1, Python 3.13,
  Node.js 22 LTS, gateway port 8080, module ports 8101-8109, all-required
  readiness, and a 30-second SIGTERM grace period. Only gateway is published;
  modules bind loopback and retain separate processes and data directories.
- INS-001 made no architecture decision and changed no public contract, module
  ownership, persistence, clinical behavior, or deployment design.

## Session Notes

- INS-007 changed governance contracts and tests only. No clinical source,
  model, schema, BN Manager runtime file, generated artifact, or module API was
  modified. The pre-existing dirty BN Manager worktree, including its modified
  Pharmacotherapy registry XML, was preserved.
- INS-006 changes governance contracts only. No provider integration, runtime
  endpoint, conversation persistence, active chat UI, clinical API, or clinical
  workflow behavior was added.
- No file under `doc/` was read or modified during INS-006.
- INS-005 defines and tests ownership and permissions only. No runtime API, UI,
  backup artifact, restore, retention deletion, database, or deployment behavior
  changed.
- No file under `doc/` was read or modified during INS-005.
- INS-004 changes ownership contracts only. No module runtime, persistence, API,
  UI, clinical instrument, risk score, question set, or release status changed.
- No file under `doc/` was read or modified during INS-004.
- INS-003 defines and tests the security contract only. No module runtime,
  persistence, public clinical API, or release status changed. Existing
  Dashboard and Add New Patient adapters still forward broader headers and must
  be narrowed during rollout.
- Authentication's current flat v1 session response still lacks the stable
  session UUID expected by consumers. ADR-0002 binds authorization and
  finalization to immediate opaque-cookie revalidation without resolving that
  separate response-shape decision.
- INS-002 changed decision records and static policy checks only. No module
  implementation, public API, persistence, clinical behavior, or release status
  changed.
- No unrelated failure was fixed, per INS-001 scope.
- No runtime DB, fixture residue, generated bytecode, or temporary copied
  worktree remains from this baseline run.
- Clinical/model release remains blocked; this baseline makes no release claim.
