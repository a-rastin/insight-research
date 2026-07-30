# Progress Tracker

Update this file after every meaningful implementation change.

## Current Phase

- Phase 1 versioned contracts and canonical identity

## Current Goal

- INS-019: Publish BN evaluation and registry-governance v3 contract (In
  progress).
- INS-017: Publish Medical History assessment v2 contract (In progress).
- INS-016: Publish PANSS Severity assessment v2 contract (In progress).
- INS-015: Publish Diagnosis assessment v2 contract (In progress).
- INS-014: Publish Patient and Encounter v2 contracts (In progress).
- INS-012: Publish the common internal REST profile (In progress).
- INS-010: Resolve plan breadth, scheduling, emergency, and override gates (In
  progress).
- INS-009: Resolve knowledge authority and terminology gates (In progress).

## Completed

- INS-013 upgrades Authentication to schema version 7 and publishes
  `GET /api/auth/v2/session` plus its Draft 2020-12 response schema and current
  contract. The standalone app, tests, static UI, configuration, and
  documentation are tracked under `Modules/Authentication-1.1.0/`. Stable user
  and session UUIDs are assigned without replacing legacy integer user keys; v2
  returns canonical lowercase roles, RFC 3339 UTC expiry, explicit
  password/disclaimer gates, interface/schema version `2.0.0`, and an explicit
  legacy-ID/role mapping without a human authorization message.
  Disablement, revocation, expiry, reset, role, password, and disclaimer checks
  continue through one live server-side resolver. The unchanged flat
  `/api/auth/session` shape remains a deprecated v1 adapter with successor
  headers. JSON syntax passed with `python3 -m json.tool
  docs/auth-session-v2.schema.json`; focused contract tests passed with
  `python3 -B -m unittest discover -s tests -p "test_contract.py" -v` (7
  tests); focused fresh/upgrade/rollback-plan migration tests passed with
  `python3 -B -m unittest discover -s tests -p "test_migrations.py" -v` (3
  tests); the full Authentication suite passed with `python3 -B -m unittest
  discover -s tests -v` (19 tests); common REST profile tests passed with
  `python3 -B -m unittest tests/test_common_rest_profile.py -v` (8 tests); and
  root `git diff --check` passed. Full root discovery ran 59 tests with 58
  passing and the known unrelated capability-matrix failure because `INS-011`
  and `INS-067` through `INS-082` are referenced but absent from current
  feature-spec issue headings.
- INS-012 publishes accepted ADR-0009 and a copy-unchanged common internal REST
  package: normative profile, Draft 2020-12 schemas, OpenAPI 3.1 components, and
  examples. It standardizes safe RFC 9457 problem details, liveness, readiness,
  contract discovery, UUID and UTC formats, schema and trace headers, strong
  ETags/`If-Match`, idempotency behavior, unsupported-major failure, and
  compatibility/deprecation rules. All five JSON files passed `python3 -m
  json.tool`; focused tests passed with `python3 -B -m unittest
  tests/test_common_rest_profile.py -v` (8 tests); `git diff --check` passed.
  Full discovery ran 59 tests with 58 passing and one unrelated existing
  capability-matrix failure because `INS-011` and `INS-067` through `INS-082`
  are referenced but absent from current feature-spec issue headings.
- INS-066 freezes versioned `contracts/capability-matrix-v1.json` and its Draft
  2020-12 schema. The matrix hash-locks `context/project-overview.md` and maps
  all 88 goals, core-flow steps, top-level and nested features, in-scope
  statements, exclusions, and success criteria to required or conditional
  status, implementation packets, contract/schema evidence, and research-build
  versus controlled-clinical applicability. `INS-011` and `INS-067` through
  `INS-082` record newly exposed one-session work before the freeze. Missing
  evidence fails closed, and technical completion does not authorize clinical
  deployment. Both JSON files passed `python3 -m json.tool`; focused tests
  passed with `python3 -B -m unittest tests/test_capability_matrix.py -v` (6
  tests); full discovery passed with `python3 -B -m unittest discover -s tests
  -v` (51 tests); `git diff --check` passed.
- INS-003 capability hardening separates runtime service origins from gateway
  base paths and defines validated, default-deny caller/destination/method/path
  configuration with segment-boundary matching and rejection of ambiguous path
  encodings before network access. Contract JSON passed `python3 -m json.tool`;
  focused tests passed with `python3 -B -m unittest
  tests/test_internal_service_auth.py -v` (4 tests); full discovery passed with
  `python3 -B -m unittest discover -s tests -v` (45 tests); `git diff --check`
  passed.
- INS-005 retention hardening now explicitly protects required clinical
  provenance and security-audit records alongside immutable clinical records,
  matching ADR-0004's no-silent-deletion rule. Contract JSON passed `python3 -m
  json.tool`; focused tests passed with `python3 -B -m unittest
  tests/test_administration_operations.py -v` (6 tests); full discovery passed
  with `python3 -B -m unittest discover -s tests -v` (45 tests); `git diff
  --check` passed.
- INS-002 policy verification now requires the complete nine-module ID set and
  rejects duplicate module IDs and gateway base paths, closing the prior empty
  or incomplete-list vacuous pass. Runtime selections remain unchanged. Focused
  tests passed with `python3 -B -m unittest tests/test_runtime_policy.py -v` (2
  tests); full discovery passed with `python3 -B -m unittest discover -s tests
  -v` (44 tests); `git diff --check` passed.
- INS-009 schema hardening now requires exactly one source entry for each of the
  six authority domains; duplicate domain entries can no longer replace a
  required authority while preserving array length. Concrete source provenance
  remains unavailable and fail-closed under `source-ingestion-not-implemented`.
  Schema JSON passed `python3 -m json.tool`; focused tests passed with `python3
  -B -m unittest tests/test_knowledge_source_manifest.py -v` (7 tests); full
  discovery passed with `python3 -B -m unittest discover -s tests -v` (44
  tests); `git diff --check` passed.
- INS-010 safety-policy hardening binds the sole overridable gate to
  `high-severity-ddi`, schema-enforces the 20-2000 rationale bounds, and gives
  all six required-input uncertainty states distinct decision-table codes and
  resolution actions. Both JSON files passed `python3 -m json.tool`; focused
  tests passed with `python3 -B -m unittest
  tests/test_treatment_plan_safety_policy.py -v` (7 tests); full discovery passed
  with `python3 -B -m unittest discover -s tests -v` (43 tests); `git diff
  --check` passed.
- INS-010 now has ADR-0008, versioned
  `contracts/treatment-plan-safety-policy-v1.json`, its Draft 2020-12 JSON
  Schema, and policy decision-table tests covering DG-04, DG-05, and DG-06.
- System-generated plan breadth is limited to source-backed treatment setting,
  pharmacotherapy, and follow-up. Non-pharmacological generation and structured
  finalization remain unsupported. Appointment, availability, and timezone
  ownership remain unresolved, so calendar lookup, booking, and exact date/time
  recommendations are unavailable.
- Emergency, required-data uncertainty, allergy, absolute contraindication,
  urgent or unavailable suicide risk, unresolved medication, and unavailable
  DDI coverage fail closed. Only high-severity DDI is overridable, requiring an
  attributable psychiatrist rationale, preserved finding, repeated server-side
  validation, and final attestation.
- Both INS-010 JSON files passed `python3 -m json.tool`; focused policy and
  scope-matrix validation passed with `python3 -B -m unittest
  tests/test_treatment_plan_safety_policy.py -v` (7 tests); full architecture
  discovery passed with `python3 -B -m unittest discover -s tests -v` (43
  tests); `git diff --check` passed.
- INS-009 now has ADR-0007, versioned
  `contracts/knowledge-source-manifest-v1.json`, its Draft 2020-12 JSON Schema,
  and focused fail-closed contract tests covering DG-02 and DG-08.
- US research authorities are selected: product-specific FDA-approved labeling
  for dosing, contraindications, and monitoring; ICD-10-CM 2026 for diagnosis
  terminology; and RxNorm Current Prescribable Content 2026-07-06 for medication
  terminology. INSIGHT makes no formulary, coverage, reimbursement, stock, or
  local availability claim.
- Drugs@FDA is checked weekdays, RxNorm weekly, ICD-10-CM every 30 days, and the
  profile receives a 90-day governance review. Changes require validation and
  clinical review; missing, stale, or changed sources block affected output.
- Both JSON files passed `python3 -m json.tool`; Draft 2020-12 instance and
  negative provenance/formulary validation passed in `python3 -B -m unittest
  tests/test_knowledge_source_manifest.py -v` (6 tests); full architecture
  discovery passed with `python3 -B -m unittest discover -s tests -v` (36
  tests); `git diff --check` passed.
- INS-008 now has ADR-0006, versioned `contracts/scope-matrix-v1.json`, Draft
  2020-12 `contracts/scope-matrix.schema.json`, and negative fixtures for
  excluded or unknown diagnosis and population states.
- Scope policy is research-only and advisory. Treatment Plan requires an
  explicit psychiatrist-confirmed schizophrenia decision; no patient population
  is approved, no population eligibility may be inferred, and every unsupported
  or unknown case produces `scope-blocked` / `TP_SCOPE_UNSUPPORTED` without a
  recommendation run or Primary Treatment Plan.
- All three JSON files passed `python3 -m json.tool`; Draft 2020-12 schema and
  instance validation passed with `jsonschema`; focused scope tests passed with
  `python3 -B -m unittest tests/test_scope_matrix.py -v` (5 tests); full
  architecture discovery passed with `python3 -B -m unittest discover -s tests
  -v` (30 tests); `git diff --check` passed.
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

- INS-019 BN evaluation and registry-governance v3 contract packet (In
  progress). The mirrored standalone BN Manager now publishes v3 registry
  discovery and evaluation routes. Discovery exposes stable ID, semantic
  version, model and XSD hashes, BIF schema version, engine version,
  lifecycle/clinical-use status, target, and mapping version without returning
  model text. Clinical evaluation is registry-only and returns accepted and
  ignored evidence, warnings, posterior, mapping version, evaluation UUID, and
  UTC time. Actor-scoped idempotency returns the original result for an exact
  retry and rejects conflicting key reuse; caller XML remains available only
  to the admin validation route. The protected source repository was not
  changed and no protected model/schema bytes were edited. Contract tests
  passed 7/7 with `UV_CACHE_DIR=/tmp/insight-uv-cache uv run --with httpx2
  python -B -m unittest tests.test_contract -v`; Python compilation and
  `git diff --check` passed. Backend HTTP tests initially reached 11 passing
  cases before exposing and correcting a keyword-call defect and stale v2
  expectation; subsequent TestClient runs hung before response dispatch in the
  installed Python 3.13/httpx2 environment, so full HTTP and module-suite
  verification remains pending and the packet stays in progress.
- INS-018 DDI knowledge and clinical-check v1 contract packet. Interface/schema
  `1.0.0` now defines resolved, ambiguous, and unknown medication identity;
  immutable draft/reviewed/active/retired knowledge revisions; attributable
  review, activation, and rollback; exact medication-instance pairwise checks;
  incomplete coverage; findings and append-only clinical audit; the sole
  high-severity psychiatrist override; version/content and medication-set
  hashes; deterministic idempotency; role permissions; and typed errors.
  OpenAPI publishes the Treatment Plan-aligned `POST /api/ddi/v1/checks` seam
  plus knowledge lifecycle and finding-action routes. Contract JSON syntax and
  Draft 2020-12 schema checks passed; focused tests passed 5/5; the mirrored DDI
  module suite passed 6/6 after restoring its pre-existing missing parser,
  parity test, and report fixtures byte-for-byte from the protected source
  repository. Root discovery ran 64 tests with 62 passing and the same two
  unrelated existing capability-matrix failures for missing issue headings and
  a stale project-overview hash. Protected server runtime, authentication,
  authorization/CSRF, revision persistence, audit persistence, and endpoint
  implementation remain pending, so the packet stays in progress and clinical
  deployment remains blocked.
- INS-017 Medical History assessment v2 contract packet. Interface/schema
  `2.0.0`, versioned controlled options, canonical Patient/Encounter/Assessment
  and psychiatrist Actor UUIDs, created/updated timestamps, resource versions,
  original medication text, explicit medication-normalization states, explicit
  `unknown`/`not-assessed` clinical values, strong ETags, and idempotent creates
  are implemented. The legacy activation-code interface remains unchanged.
  Focused `node test_v2_api.js` and full `npm test` passed; all three contract
  JSON files passed `python3 -m json.tool`; the Draft 2020-12 schema passed
  `Draft202012Validator.check_schema`; common REST profile tests passed 8/8;
  focused changed-file `git diff --check` passed. Root discovery ran 59 tests
  with 57 passing and two unrelated existing capability-matrix failures for
  missing issue headings and a stale project-overview hash. Authentication,
  authorization/CSRF, consumer/UI migration, concurrency-safe production
  database persistence, audit, encryption, and retention remain pending, so
  clinical deployment remains blocked and the packet stays in progress. Every
  file changed by the owning module's INS-017 commit is mirrored under
  `Modules/Medical-History-1.0.0/` in this repository and byte-for-byte checked
  against module commits `e5c28d9` and `5f8fc37`.
- INS-016 PANSS Severity assessment v2 contract packet. Interface/schema
  `2.0.0`, all 30 score inputs, server-derived subscales/total, explicit
  in-progress/completed/skipped semantics, canonical UUIDs, strong ETags,
  idempotent creates, and provenance are implemented and verified. Focused
  `node test_v2_api.js` and full `npm test` passed; contract JSON and Draft
  2020-12 schema checks passed; common REST profile tests passed 8/8; both
  repository `git diff --check` commands passed. Root discovery ran 59 tests
  with 57 passing and two unrelated existing capability-matrix failures for
  missing issue headings and a stale project-overview hash. Authentication,
  CSRF, consumer/UI migration, and production database persistence remain
  pending, so packet and clinical deployment remain in progress.
- INS-015 Diagnosis assessment v2 contract packet (In progress).
- INS-014 Patient and Encounter v2 contract packet. Contract, migration,
  runtime, and provider verification are complete in the owning Add
  New Patient repository. Consumer rollout from v1 patient-code/intake routes to
  UUID-only v2 resources remains pending.
- INS-012 common internal REST profile packet. Canonical schemas, examples,
  compatibility/deprecation rules, and provider/consumer checks are complete.
  Per-module packaging and runtime conformance remain pending separate rollout
  packets.
- INS-010 plan breadth, scheduling, emergency, and override-gate decision packet.
  Governance controls and scenarios are implemented. Accountable psychiatrist
  and product approvals, scheduling ownership contracts, approved plan content,
  and module-runtime rollout remain pending; clinical deployment stays blocked.
- INS-009 knowledge-authority and terminology-gate decision packet. US research
  authorities, pinned baselines, provenance, and cadence are selected. Source
  ingestion/validation and named clinical/pharmacy release sign-off remain
  pending; clinical deployment stays blocked.
- INS-008 intended-use, population, and diagnosis-gate decision packet.
  Research-only status, supported diagnosis pathway, and observable fail-closed
  behavior are implemented. Supported-population evidence and attributable
  psychiatrist/product approvals remain unresolved, so plan generation and
  clinical release remain blocked.
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
- Test: `npm test`, running focused PANSS v2 and legacy v1 API checks.
- Routes: `GET /api/severity/:patient_code`; `PUT
  /api/severity/:patient_code`; `GET /api/severity/v2/contract` and its document,
  schema, and OpenAPI resources; `POST /api/severity/v2/assessments`; `GET` and
  `PUT /api/severity/v2/assessments/{assessmentId}`; CORS `OPTIONS`; static and
  SPA fallback `GET`.
- Migrations/schema: no database migration. V2 interface/schema `2.0.0` uses a
  separate module-owned JSON store with configurable test paths; v1 remains flat
  `data/assessments.json`, keyed by patient code. Production persistence rollout
  remains pending.

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
| Severity | PASS | Focused PANSS v2 checks and full v1/v2 `npm test` passed using isolated temporary persistence |
| Medical History | PASS | 4 tests |
| DDI Checker | PASS | 49 tests |
| BN Manager | FAIL | uv-created isolated environment collected 31 tests: 29 passed, 2 import errors because declared dependencies omit `httpx2`, required by Starlette `TestClient` |
| Treatment Plan | PARTIAL | Backend passed 112 tests with PostgreSQL repository contract skipped because `TP_TEST_POSTGRES_DSN` is unset; frontend failed before collection because optional native package `@rolldown/binding-linux-x64-gnu` is absent |

Commands used temporary directories under `/tmp/opencode` and explicit storage
variables: `AUTH_DB_PATH`, `DASHBOARD_DB_PATH`, `ADD_NEW_PATIENT_DB_PATH`,
`DIAGNOSIS_DB_PATH`, `MEDICAL_HISTORY_DATA_DIR`, and `TP_DATABASE_PATH`.

## First Failing Integration Boundary

- Authentication now publishes the canonical nested UUID contract at
  `GET /api/auth/v2/session`. Dashboard and Add New Patient still target the
  deprecated v1 path and expect uppercase role values. Their rollout packets
  must switch to v2, validate `interfaceVersion`, `authorized`, UUIDs, gates,
  and lowercase roles, then pass provider/consumer HTTP tests before later
  clinical boundaries are tested.

## Next Up

- Migrate Severity UI and REST consumers from patient-code v1 routes to UUID-only
  PANSS v2 resources. Add Authentication session verification, psychiatrist-role
  authorization, CSRF protection, and module-owned database migrations before
  production use; do not infer UUID links from legacy patient codes.
- Package the unchanged INS-012 artifacts in each module, reference the common
  OpenAPI components from module-owned contracts, then implement and test
  module-local health, readiness, discovery, error, concurrency, and idempotency
  adapters. Do not claim conformance before provider/consumer runtime tests pass.
- Complete INS-011 release-mode evidence and accountable sign-off contract,
  then execute INS-067 through INS-082 in dependency order. Use
  `contracts/capability-matrix-v1.json` as completion source of truth and keep
  controlled-clinical deployment blocked until every applicable gate passes.
- Obtain attributable psychiatrist and product approval for ADR-0008. Define
  owner-local appointment, availability, and timezone contracts before adding
  scheduling. Implement policy in Treatment Plan only after INS-008 scope and
  INS-009 knowledge release gates permit recommendation generation.
- Implement owner-local ingestion and validation for Drugs@FDA, ICD-10-CM, and
  RxNorm with pinned source bytes, hashes, identifiers, and review state. Obtain
  named clinical and pharmacy sign-off before clinical deployment.
- Obtain attributable psychiatrist/product approval and supporting evidence for
  a supported patient population and explicit exclusions. Supersede ADR-0006 and
  the scope matrix before allowing Treatment Plan generation for any population.
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
- Migrate Add New Patient consumers to the UUID-only Patient and Encounter v2
  resources and add consumer-driven HTTP checks. Define the separate Follow-up
  Delta REST/schema contract before follow-up persistence or orchestration.
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
- Align Dashboard and Add New Patient adapters and provider/consumer tests with
  `GET /api/auth/v2/session`; remove their broad historical response heuristics
  only after rollout tests pass.
- Add BN Manager's missing test dependency or test extra and rerun its suite.
- Restore Treatment Plan frontend optional native dependency and rerun Vitest;
  provide disposable PostgreSQL DSN to execute its skipped repository contract.

## Open Questions

- Which named psychiatrist and product owners approve ADR-0008, and which module
  owns appointments, availability, and timezone if scheduling enters scope?
- Which approved taxonomy and evidence contract, if any, should permit
  non-pharmacological recommendations in a future policy version?
- Which named clinical and pharmacy owners approve the selected US research
  authority profile for clinical deployment, and which deployment institution
  supplies any future local formulary authority?
- What evidence-backed patient population and exclusions should replace the
  empty INS-008 population allowlist? Accountable psychiatrist and product owners
  remain unnamed.
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

- ADR-0009 adopts common internal REST profile `1.0.0`, copy-unchanged JSON
  Schema/OpenAPI artifacts, major-version fail-closed behavior, safe typed
  errors, UUID tracing, UTC timestamps, strong ETag preconditions, deterministic
  idempotent replay, and compatibility-gated deprecation.
- ADR-0008 limits generated plan sections to source-backed treatment setting,
  pharmacotherapy, and follow-up; leaves scheduling and non-pharmacological
  generation unavailable; makes emergency and required safety/data gates hard
  blockers; and permits only attributable, revalidated high-severity DDI
  overrides.
- ADR-0007 selects a US research profile: FDA-approved product labeling for
  dosing, contraindications, and monitoring; ICD-10-CM 2026 for diagnosis
  terminology; RxNorm Current Prescribable Content 2026-07-06 for medication
  terminology; no formulary claims; scheduled checks and 90-day governance
  review; no automatic source-update activation.
- ADR-0006 keeps INSIGHT research-only, requires psychiatrist-confirmed
  schizophrenia for Treatment Plan scope, leaves the unsupported population
  allowlist empty, and returns explicit diagnosis/population reason codes without
  creating a recommendation run or Primary Treatment Plan.
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

- INS-018 publishes DDI v1 lifecycle, clinical-check, finding/audit/override,
  permissions, hash, idempotency, and error contracts with Draft 2020-12 schemas
  and OpenAPI. It does not claim the current browser-local workflow implements
  the protected server contract. The missing parser, parity test, and report
  fixtures in the destination DDI mirror were copied unchanged from
  `/root/research/Modules`; that protected source was not modified. No clinical
  knowledge bytes, active knowledge artifacts, runtime data, generated
  `graphify-out/` artifact, or file under `insight-research/doc/` was read or
  modified.
- INS-016 adds PANSS v2 contract/schema/OpenAPI artifacts, one deterministic
  server scorer, UUID assessment routes, idempotent create behavior, strong-ETag
  updates, provenance, isolated tests, and module documentation. Legacy v1 API
  behavior remains available without becoming authoritative for v2. Existing
  untracked `graphify-out/` was preserved. No protected runtime data or generated
  artifact was edited, and no file under `insight-research/doc/` was read or
  modified.
- INS-014 publishes Add New Patient interface/schema version `2.0.0` with Draft
  2020-12 JSON Schema, OpenAPI 3.1, runtime contract discovery, UUID-only Patient
  and Encounter paths, body-based exact patient-code alias resolution/search,
  opaque pagination, resource versions, provenance, strong ETags, and atomic
  idempotent Patient plus first-Encounter creation. Changed idempotency payloads,
  stale ETags, invalid UUIDs/UTC values, and alias collisions fail closed.
  Additive startup migration maps each existing UUID `intakeId` row one-to-one
  to a distinct Encounter UUID through explicit `legacyIntakeId`; dates are not
  used to infer or group encounters. Focused tests passed with `python3 -B -m
  unittest test_encounter_v2_contracts.py -v` (7 tests); full backend discovery
  passed with `python3 -B -m unittest discover -v` (49 tests); frontend tests
  passed with `node --test test_frontend.mjs` (3 tests); common REST profile
  checks passed with `python3 -B -m unittest tests/test_common_rest_profile.py
  -v` (8 tests); both v2 JSON files passed `python3 -m json.tool`; intended-file
  and root `git diff --check` passed. Existing v1 code-or-UUID routes remain as
  compatibility behavior; no consumer was silently migrated. Pre-existing
  protected `graphify-out/` changes were preserved. No file under
  `insight-research/doc/` was read or modified.
- INS-013 changes Authentication contracts, additive migration 007, session
  runtime behavior, focused tests, README, and this tracker. Existing integer
  keys remain compatibility-only mappings; no applied migration, runtime
  database, consumer module, clinical behavior, or protected artifact changed.
  Required standalone runtime, static UI, tests, configuration, and module
  documentation are copied into and tracked by the root repository; generated
  and runtime artifacts remain excluded. No file under `insight-research/doc/`
  was read or modified.
- INS-012 changes architecture contracts, examples, tests, and this tracker
  only. No module runtime, API route, persistence, UI, clinical source, model,
  or release state changed. No file under `doc/` was read or modified.
- INS-066 changes governance contracts, feature work packets, tests, and this
  tracker only. No module runtime, API, persistence, UI, clinical source, model,
  generated artifact, or release authorization changed.
- INS-003 audit hardening changed ADR-0002, its governance contract, focused
  test, and this tracker only. No service keys, deployment capability entries,
  runtime adapter, or user identity were invented. No file under `doc/` was read
  or modified.
- INS-005 audit hardening changed its ownership contract, focused test, and this
  tracker only. Retention periods and runtime deletion mechanisms remain blocked
  pending approved policy. No file under `doc/` was read or modified.
- INS-002 audit hardening changed its static policy test and this tracker only.
  Per-service UID isolation remains an unresolved security-hardening decision;
  accepted ADR-0001 runtime values were not silently changed. No file under
  `doc/` was read or modified.
- INS-009 audit hardening changed its governance schema, test, and this tracker
  only. No source bytes, hashes, retrieval metadata, runtime, API, or release
  state were invented or changed. No file under `doc/` was read or modified.
- INS-010 audit hardening changed governance contract, schema, tests, and this
  tracker only. No runtime, API, persistence, UI, clinical source, model, or
  release status changed. No file under `doc/` was read or modified.
- INS-010 changes governance contracts and tests only. No module runtime, API,
  persistence, UI, clinical source, model artifact, or release status changed.
  No file under `doc/` was read or modified.
- INS-009 changes governance contracts and tests only. No module runtime, API,
  persistence, UI, clinical source, terminology asset, model artifact, or
  release status changed. No file under `doc/` was read or modified.
- INS-008 changes governance contracts and tests only. No Treatment Plan runtime,
  module API, persistence, UI, clinical source, or model artifact changed. No
  demographic or population eligibility rule was inferred without evidence.
- No file under `doc/` was modified during INS-008.
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
