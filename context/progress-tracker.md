# Progress Tracker

Update this file after every meaningful implementation change.

## Current Phase

- Phase 1 versioned contracts and canonical identity

## Current Goal

- INS-056: Build the unified multi-process image and internal gateway (In
  progress).
- INS-055: Implement the approved read-only assistant slice (In progress).
- INS-054: Conduct psychiatrist lifecycle walkthrough and retire prototype (In
  progress).
- INS-053: Wire follow-up supersession route and UI (In progress).
- INS-051: Connect React review UI to authenticated backend routes (In
  progress).
- INS-050: Implement recommendation-run create and status routes (In progress).
- INS-049: Implement Treatment Plan contract and schema discovery routes (In
  progress).
- INS-048: Replace hypothetical clinical-context URLs with provider contracts
  (In progress).
- INS-035: Reconcile BN Pharmacotherapy XML semantics and provenance (In
  progress).
- INS-030: Implement the approved structured suicide-risk module (In progress).
- INS-029: Connect Medical History UI and medication-resolution feedback (In
  progress).
- INS-028: Replace Medical History JSON with v2 repository and security (In
  progress).
- INS-027: Rebuild Severity UI integration without PHI browser storage (In
  progress).
- INS-026: Replace Severity JSON persistence with module-owned SQLite and
  security controls (In progress).
- INS-025: Implement server-authoritative PANSS evaluation (In progress).
- INS-024: Connect embedded Diagnosis UI to v2 assessment context (In
  progress).
- INS-023: Migrate Diagnosis storage and routes to assessment UUIDs (In
  progress).
- Capability completion packets INS-011 and INS-067 through INS-082 (In
  progress); INS-067 is complete and later packets remain separately gated.
- INS-020: Reconcile Treatment Plan OpenAPI with live routes (In progress).
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

- INS-067 rolls out the Authentication v2 trust contract to the bounded
  Dashboard consumer adapter. Dashboard now calls only
  `GET /api/auth/v2/session`, requires schema/interface `2.0.0`, UUID user and
  session identities, lowercase provider roles, an active future UTC `Z`
  expiry, `authorized: true`, and cleared password/disclaimer gates. Legacy,
  malformed, unsupported-major, gated, expired, and revoked responses fail
  closed; every protected Dashboard request revalidates Authentication, while
  the Authentication-owned v1 route remains only its deprecated compatibility
  adapter. The restored Dashboard adapter is module-owned and was copied from
  the protected source before being migrated; no protected source file was
  changed. Focused Dashboard normalization tests passed 2/2, its full backend
  suite passed 16/16, and its frontend test passed. Authentication provider and
  full suites passed 7/7 and 19/19, including expiry, revocation, disablement,
  role, disclaimer, password, CSRF, rate-limit, cookie, and v1 deprecation
  behavior. Common REST profile checks passed 8/8, root discovery passed 65/65,
  changed Python files compiled, and `git diff --check` passed. No file under
  `insight-research/doc/` was read or modified. Remaining feature-22 headings
  are separate packets and are not claimed complete.
- INS-021 implements Patient and Encounter v2 in the Add New Patient owner.
  Ordered `patient-intake-v1` and `patient-encounter-v2` migration records now
  apply schema and backfill changes atomically; collision or invalid-row failure
  preserves the pre-upgrade database. Legacy creation is a thin request/response
  adapter over the authoritative atomic Patient, alias, Encounter, and intake
  snapshot transaction. Authenticated UUID-only v2 create/read/list/search
  routes provide actor-scoped idempotency, strong ETags, request/correlation
  IDs, common RFC 9457 problem details, schema negotiation, psychiatrist-only
  CSRF-protected writes, and encounter-bound reads for Treatment Plan. No new
  URL contains a patient alias, no patient identifier is added to errors or
  logs, and pre-existing protected `graphify-out/` changes were preserved.
  Focused migration, rollback, collision, pagination, idempotency, ETag,
  auth/CSRF, request-trace, contract, and legacy-equivalence tests passed with
  `python3 -B -m unittest test_encounter_v2_contracts.py -v` (12 tests). The
  legacy backend suite passed with `python3 -B -m unittest
  test_add_new_patient_backend.py -v` (43 tests), equivalent full backend
  coverage is 55 tests, frontend tests passed with `node --test
  test_frontend.mjs` (3 tests), common REST profile tests passed with `python3
  -B -m unittest tests/test_common_rest_profile.py -v` (8 tests), and root
  discovery passed with `python3 -B -m unittest discover -s tests -v` (65
  tests). Both v2 JSON artifacts passed `python3 -m json.tool`, changed Python
  files passed `python3 -m py_compile`, and intended module paths passed `git
  diff --check`. Consumer rollout remains a separate packet; controlled
  clinical deployment remains blocked by the system-level gates recorded below.
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

- INS-056 unified multi-process image and internal gateway (In progress). A
  digest-pinned Python 3.13 and Node.js 22 multi-stage image now packages ten
  independently configured module processes and their UIs under non-root UID
  10001. Supervisord remains PID 1, uses process-group TERM/KILL handling with a
  30-second grace period and fail-fast required-process monitoring, and starts
  nginx as the sole published `8080` listener. Nginx routes gateway-relative UI
  and API paths to loopback-only ports `8101`-`8110`; Suicide Risk now has the
  previously missing runtime-policy entry at `8109`, and Treatment Plan moves to
  `8110`. Ten separate named data volumes preserve module ownership, Treatment
  Plan runs its ordered integrity-checked migration gate before supervision,
  other database services complete module-owned migrations before binding, and
  the gateway readiness aggregator reports only unavailable module IDs without
  internal URLs or response bodies. Python dependencies are transitively pinned
  with hashes, Node installs use package locks, and the Treatment Plan UI is
  built in its own stage. Add New Patient now supplies the selected liveness and
  readiness aliases; Treatment Plan accepts production HTTP only for numeric
  loopback origins and binds its configured internal host and port. Focused
  runtime-policy and image tests passed 7/7; root discovery passed 75/75;
  Treatment Plan passed 76/76; Add New Patient backend and v2 contract suites
  passed 43/43 and 12/12; DDI passed 46/46; Compose validation, changed Python
  compilation, JavaScript syntax, and `git diff --check` passed. The full image
  built successfully, started under a read-only root filesystem with all ten
  module processes, served gateway liveness and routed module UIs, returned
  `503` readiness naming only `ddi-checker`, and stopped in 3.28 seconds after
  SIGTERM. DDI remains a static prototype with no protected server-owned REST
  implementation, so its deployment adapter deliberately fails readiness with
  `production-rest-seam-unavailable`; implementing that separately approved DDI
  owner seam and then repeating an authenticated end-to-end gateway run is the
  next step. No file under `insight-research/doc/` was read or modified.
- INS-055 approved read-only assistant slice (In progress). Implementation has
  superseded the INS-006 disabled policy only for the Treatment Plan review
  page. ADR-0011 and assistant policy 1.1.0 approve a psychiatrist-only,
  non-persistent boundary with no tools, provider retention, training, backup,
  deletion workflow, or clinical mutation capability. The server loads the
  current plan, structurally projects only supported plan content, finding
  descriptors, and rationale, then scrubs the projected strings and prompt
  before calling a trusted-origin provider adapter. Plan, Patient, Encounter,
  run, finding, actor, source, timestamp, edit, and provenance fields are not
  projected. Provider output is scrubbed again and bounded to 8,000 characters.
  The versioned advisory route and responsive React rail label output as
  advisory, expose no clinical action, store no conversation, and keep plan
  workflows available when configuration or the provider fails. Focused
  assistant, contract, and security tests passed 19/19; assistant governance
  tests passed 5/5; the full Treatment Plan backend suite passed 75/75; frontend
  tests passed 6/6; TypeScript checking and the production build passed; common
  REST checks passed 8/8; root discovery passed 70/70; changed JSON syntax,
  Draft 2020-12 schema validation, changed Python compilation, and `git diff
  --check` passed. A named deployment provider satisfying the approved
  no-retention/no-training policy and a live authenticated gateway/provider run
  remain required, so INS-055 stays in progress. No file under
  `insight-research/doc/` was modified; one broad content search inadvertently
  returned matching snippets from `doc/plan.md`, but the file was not otherwise
  opened or used as implementation authority.
- INS-054 psychiatrist-role lifecycle walkthrough and prototype retirement (In
  progress). Controlled evidence `INS-054-WALKTHROUGH-2026-07-31` now maps five
  synthetic, no-PHI lifecycle cases to production behavior: required-input
  uncertainty blocks generation before model work; structured edits preserve
  the immutable recommendation and actor/session/before/after history;
  high-severity DDI override requires the exact attributable rationale;
  finalization repeats DDI validation and freezes the resulting Final Plan; and
  follow-up creates an explained successor without changing the prior Final
  Plan. The React walkthrough additionally confirms that urgent findings remain
  visible during editing and that successor section changes are textual and
  explained. ADR-0010 records the observations, commands, production-test
  evidence, retirement decision, and explicit limitation that no human
  psychiatrist participated. The repository had no `prototype/` directory at
  packet start and production/tests contain no prototype import, so no
  unverified code was deleted; generated `graphify-out/` references were left
  untouched. Focused backend walkthrough tests passed 5/5 and the focused UI
  walkthrough passed 1/1. The full Treatment Plan backend suite passed 71/71;
  frontend tests passed 5/5; TypeScript checking and the production build
  passed; common REST checks passed 8/8; root discovery passed 70/70; and `git
  diff --check` passed. No file under `insight-research/doc/`, protected
  clinical/model source, applied migration, runtime data, or generated artifact
  was modified. Findings are split into bounded INS-055 finalization UI,
  INS-056 composed authenticated lifecycle integration, and INS-057 independent
  psychiatrist walkthrough packets. INS-054 remains in progress until the
  independent psychiatrist evidence required by INS-057 is attributable and
  recorded; no clinical deployment approval is claimed.
- INS-053 follow-up supersession route and UI (In progress). The canonical
  Treatment Plan OpenAPI and runtime schema now publish authenticated,
  psychiatrist-only `POST /api/treatment-plan/v1/plans/{plan_id}/supersede`
  with CSRF, UUID request tracing, and a bounded idempotency key. The route is
  wired to the existing `PlanSuperseder`, validates the owner-produced Follow-up
  Delta against the prior immutable Final Plan, gathers and validates fresh
  source snapshots, atomically creates or exactly replays one successor review
  workflow, and returns its ETag plus the immutable supersession evidence. The
  React host contract accepts the fresh Follow-up Delta, submits it with cookie
  credentials, switches subsequent edits to the successor Plan UUID, and shows
  explicit Changed or Unchanged text with the server-derived reason for setting,
  pharmacotherapy, and next appointment. Focused supersession and contract tests
  passed 15/15; the full Treatment Plan backend suite passed 71/71; frontend
  tests passed 5/5; TypeScript checking and the production build passed; common
  REST checks passed 8/8; root discovery passed 70/70; changed Python files
  compiled; both JSON artifacts passed syntax and Draft 2020-12 schema checks;
  and both repository `git diff --check` commands passed. No file under
  `insight-research/doc/`, protected clinical/model source, applied migration, or
  runtime data was read or modified. Release composition must still inject the
  configured fresh-snapshot provider and approved successor generator, and the
  host follow-up flow must supply the Add New Patient-owned Follow-up Delta; the
  route fails closed with 503 when the supersession service is absent. A live
  authenticated host/gateway run is the next integration verification, so
  INS-053 remains in progress.
- INS-051 Treatment Plan authenticated review UI connection (In progress).
  The React workspace copied into the mirrored Treatment Plan module now
  replaces all synthetic plan, finding, rationale, alternative, and provenance
  content with credentialed gateway-relative reads of
  `GET /api/treatment-plan/v1/plans/{plan_id}` and its `/provenance` route. The
  host supplies the Plan UUID and CSRF token without URL or browser-storage
  persistence. Content-shaped loading, retryable read errors, unavailable
  finalization provenance, missing ETag, and missing CSRF context are explicit;
  the plan remains reviewable when optional provenance fails, while editing
  fails closed. The UI validates and maps the server plan, keeps the immutable
  recommendation visible beside psychiatrist changes, displays plan and source
  provenance, never invents omitted alternatives, and submits canonical JSON
  Pointer edits to the draft route. Sequential writes carry the newest strong
  ETag in each `If-Match`, include cookie credentials and `X-CSRF-Token`, retain
  failed edits, and expose server rejection without presenting the edit as
  saved. Focused frontend API and screen tests passed 4/4 with `npm test`;
  `npm run typecheck` and `npm run build` passed. The full Treatment Plan suite
  passed 70/70 with `python3 -B -m unittest discover -s tests -v`; common REST
  checks passed 8/8; root discovery passed 70/70; and `git diff --check` passed.
  Generated `node_modules/` and `dist/` were removed after verification. No file
  under `insight-research/doc/`, protected source/module file, runtime data, or
  generated `graphify-out/` was read or modified. A configured host/gateway
  must still inject a live Plan UUID and CSRF token and serve the built frontend;
  no such integrated browser harness exists in this repository, so a real
  authenticated gateway browser run is the next step and INS-051 remains in
  progress.
- INS-050 recommendation-run create and status routes (In progress). The
  canonical OpenAPI and runtime schema now publish authenticated, psychiatrist-
  only `POST /api/treatment-plan/v1/recommendation-runs` and actor-scoped
  `GET /api/treatment-plan/v1/recommendation-runs/{run_id}`. Creates require
  CSRF, a UUID request ID, canonical Patient/Encounter/Severity Assessment UUIDs,
  an IANA-style timezone, and a bounded actor-scoped idempotency key. Exact
  retries replay the persisted result without re-running dependencies; changed
  key reuse returns 409, another psychiatrist receives 404, and every state
  transition is monotonic and persisted through `requested`,
  `gathering-inputs`, `inputs-incomplete`, `evaluating`, `generated`, or
  `generation-failed`. The workflow calls the existing authoritative context
  assembler and eligibility policy before any model work, skips model generation
  for explicit blockers, and provides a concrete adapter over the existing BN,
  deterministic safety, constrained synthesis, exact current-plus-proposed DDI,
  and immutable Primary Plan ledger seams. DDI failure or unresolved identity
  blocks plan persistence; deterministic candidate metadata must exactly cover
  the BN posterior; unsupported DDI severity also fails closed. Focused route,
  lifecycle, idempotency, actor-scope, dependency-failure, response-schema, and
  OpenAPI parity checks passed 12/12 with `python3 -B -m unittest
  tests.test_tp50_recommendation_runs tests.test_tp05_contracts -v`. The full
  Treatment Plan suite passed 70/70 with `python3 -B -m unittest discover -s
  tests -v`; common REST checks passed 8/8; root discovery passed 70/70; changed
  Python compilation, all changed JSON syntax, both Draft 2020-12 schema checks,
  and `git diff --check` passed. No file under `insight-research/doc/`, protected
  clinical/model source, runtime data, or generated `graphify-out/` was modified.
  Release composition must still inject configured provider adapters and an
  approved source-backed `RecommendationInputMapper`; absent that configuration,
  the route fails closed with 503. The active scope policy also remains
  unapproved, so real requests stop at explicit `inputs-incomplete` rather than
  producing a clinical recommendation. Those governance and deployment wiring
  gates keep INS-050 in progress; the next step is approval of the mapper and
  runtime provider configuration followed by a real HTTP integration run.
- INS-049 Treatment Plan contract and schema discovery (In progress). The
  unauthenticated `GET /api/treatment-plan/v1/contract` response now conforms
  to the accepted common REST discovery schema, identifies interface `1.1.0`
  and schema versions `1.0.0`/`1.1.0`, publishes the canonical OpenAPI path and
  24-hour idempotency-key retention, emits a UTC `Z` timestamp, and returns
  per-hop request plus root-preserving correlation UUID headers. The canonical
  OpenAPI artifact is served at `GET /api/treatment-plan/v1/openapi.json` and
  only three registered artifacts are available through
  `GET /api/treatment-plan/v1/schemas/{name}/{version}`; unknown names,
  versions, and traversal-shaped requests return 404 without filesystem lookup.
  The release image now includes the unchanged canonical contract directory.
  Focused discovery and OpenAPI parity checks passed 10/10, the Treatment Plan
  full suite passed 65/65, common REST profile checks passed 8/8, and root
  discovery passed 70/70. All discoverable schemas passed Draft 2020-12 schema
  checking, the OpenAPI artifact passed JSON syntax checking, changed Python
  files compiled, and `git diff --check` passed. No clinical behavior,
  persistence, authentication requirement, or schema content changed. No file
  under `insight-research/doc/` or generated `graphify-out/` was read or
  modified. Unified gateway routing and a built-container HTTP smoke test remain
  outside this bounded packet, so INS-049 stays in progress; that deployment
  verification is the next step.
- INS-048 clinical-context provider contract migration (In progress). The
  Treatment Plan assembler now calls the published Add New Patient intake v2,
  Diagnosis snapshot v2, Severity assessment v2, Medical History latest v2,
  and Suicide Risk snapshot v1 reads. Severity requires its authoritative
  Assessment UUID because that provider has no Encounter-latest route. The
  fabricated DDI and BN latest-read dependencies were removed; those remain
  versioned recommendation-stage POST computations. Responses are validated
  against their provider shapes and header/body versions before use, canonical
  Patient/Encounter/resource UUIDs and strong ETags are enforced, and source
  capture binds interface/schema/resource and provider-specific versions,
  retrieval time, exact response SHA-256, ETag, and the Suicide Risk provider
  content hash. Outbound reads forward only the configured Authentication
  session cookie and safe request/correlation/causation UUIDs, add a new request
  UUID per hop, and sign the exact GET path and empty body with per-destination
  HMAC credentials; browser CSRF, authorization, and asserted user/role headers
  are not forwarded. Eligibility now consumes the real owner shapes, keeps the
  psychiatrist diagnosis decision separate from computed criteria, requires a
  complete PANSS source, blocks unresolved medication identities, and treats
  Suicide Risk as its own fail-closed owner. Focused assembler tests passed 7/7;
  the Treatment Plan full suite passed 62/62; Add New Patient and Diagnosis
  provider contract suites each passed 12/12; Medical History's full suite
  passed; and common REST plus internal-service-auth checks passed 12/12.
  Changed Python compilation and `git diff --check` passed. Severity's locked
  dependencies were subsequently restored with `npm ci`; its full repository,
  configuration, v2 API, legacy-failure, and UI suite passed. Suicide Risk
  domain checks passed 5/5, but its repository test uses a fixed 2026-07-30
  creation time that now expires before its immediate idempotency replay,
  causing a duplicate-ID failure; no runtime test data was modified.
  Provider-side HMAC enforcement and a Severity
  Encounter-latest contract remain separate rollout gaps, so INS-048 stays in
  progress. No file under `insight-research/doc/` was read or modified.
- INS-035 BN Pharmacotherapy XML reconciliation (In progress). Mapping version
  `2.0.0` now hash-locks the exact APA Statement 4 extract and unchanged
  canonical registry XML, maps every XML node once to source line references,
  distinguishes patient state, candidate safety gate, intervention eligibility,
  intervention priority, and clinical-action roles, and validates through a
  versioned Draft 2020-12 schema. Candidate semantics are explicitly
  one-candidate-at-a-time: they do not rank medications, prefer FGA versus SGA,
  treat candidate identity as model evidence, or automatically select therapy.
  A pure deterministic evaluator gives absolute candidate contraindication
  precedence, blocks unconfirmed diagnosis and missing/unknown required facts,
  and treats a gate-passing candidate only as eligible for psychiatrist
  comparison. Five golden cases cover eligible, contraindicated, unconfirmed,
  unknown, and review-factor paths. BN Manager contract `3.1.0` now requires an
  explicit `candidate_id` and complete exact-node evidence for Pharmacotherapy,
  applies hard gates before inference, and returns the candidate gate result,
  posterior, active semantic version, model hash, mapping version/hash, and
  calibration warning. Gate-blocked requests fail with
  `BNM_SAFETY_REVIEW_REQUIRED`; gate-clearing requests may be evaluated for
  research, and regression coverage proves changed patient evidence reaches the
  versioned CPT inference seam and can change returned probabilities when the
  active CPTs support it. Because the current candidate-priority and final
  recommendation CPT rows remain uniform placeholders, registry discovery and
  evaluation label them `qualitative-uncalibrated` and
  `blocked-until-calibrated-and-approved` for clinical recommendation use.
  Focused governance/provider tests passed 30/30
  with `UV_CACHE_DIR=/tmp/insight-uv-cache uv run --with httpx2 python -B -m
  unittest tests.test_pharmacotherapy_governance tests.test_contract
  tests.test_bn_manager_backend -v`; the full BN Manager suite passed 57/57;
  workspace source/schema tests passed 5/5; model-manifest checks passed 5/5;
  safety-precedence checks passed 7/7; and final root discovery passed 70/70.
  Changed JSON syntax, Python compilation, and
  `git diff --check` passed. The protected guideline and XML bytes were not
  modified. Clinical/model-owner approval, calibrated and validated CPTs,
  authoritative labeling/DDI inputs for candidate contraindications, and a
  consumer migration away from the Treatment Plan's synthetic Pharmacotherapy
  vocabulary remain unresolved. CPT mutation/activation is intentionally not
  claimed by v3.1 and remains a separate BN Manager governance operation. The
  next step is to activate an approved calibrated CPT revision with a new
  semantic version/content hash and reconcile consumer mappings; until then,
  the returned posterior remains research-only and cannot drive a clinical
  recommendation.
- INS-030 approved structured suicide-risk module (In progress). The independent
  `Modules/Suicide-Risk-1.0.0/` Node service now publishes interface/schema
  `1.0.0`, module-owned SQLite persistence with immutable attributed versions,
  actor-scoped idempotent creates, strong ETag updates, Encounter latest reads,
  and a Treatment Plan snapshot containing owner, resource version, ETag, and
  content hash. Every protected request revalidates Authentication v2; only a
  current psychiatrist is authorized, writes require session-bound signed
  double-submit CSRF, credentialed CORS permits only exact configured origins,
  readiness checks local storage and Authentication, and safe problem responses
  exclude patient identifiers. The bounded host-context UI uses no browser
  storage or navigation identity, starts with no selected assertion, retains
  failed saves, and communicates blocked and urgent states with persistent text,
  native keyboard controls, visible focus, 44px targets, responsive layout, and
  reduced-motion behavior. Because no approved C-SSRS source/licensing handoff
  exists, the contract explicitly claims no instrument completion and defines
  no question, answer, score, threshold, negative/low-risk state, or
  location-specific emergency instruction. It permits only `unknown`,
  `unavailable`, and `conflicting`, plus the two exact psychiatrist-asserted
  urgent trigger states already accepted by INS-010; server-derived disposition
  applies the exact fail-closed INS-010 codes and general emergency guidance.
  Source-to-field, forbidden-field, missing/conflicting/urgent, authority,
  repository, auth/role/CSRF, CORS, ETag/concurrency, idempotency, latest,
  snapshot, readiness, accessibility, lifecycle, and no-PHI checks passed with
  `npm test` (six Node test-runner cases plus HTTP and UI acceptance scripts).
  JavaScript syntax passed `node --check`; all three JSON artifacts passed
  `python3 -m json.tool`; the assessment schema passed Draft 2020-12 schema
  checking; common REST profile checks passed 8/8; ownership and Treatment Plan
  safety-policy checks passed 11/11; root discovery passed 65/65; and `git diff
  --check` passed. No file under `insight-research/doc/`, protected
  clinical/model source, runtime data, or generated `graphify-out/` was read or
  modified. An approved C-SSRS source/license and named clinical governance,
  database-at-rest encryption, backup/restore, retention, and a live
  Dashboard/gateway host integration remain blocked or unverified, so INS-030
  stays in progress; the next step is to obtain that handoff before adding any
  instrument content and run the existing bounded UI through the configured
  host.
- INS-029 Medical History UI and medication-resolution feedback (In progress).
  The bounded Medical History frontend now exposes frozen
  `window.InsightMedicalHistory` mount/unmount APIs and consumes host-supplied
  canonical Patient, Encounter, authenticated Actor, and optional Assessment
  UUID context. It uses only credentialed gateway-relative v2 requests, loads a
  named assessment or the Encounter latest record, obtains a session-bound CSRF
  token before writes, uses idempotency for creates and ETags for updates,
  validates returned identity/schema/version/status/actor/medication state, and
  aborts active requests and removes listeners on unmount. Activation-code
  forms, query-string restoration, host navigation, and code-based submission
  were removed from the browser while the server compatibility adapter remains
  unchanged. Every medication row remains a separate instance, including exact
  duplicates; original text and server-supplied matched, unresolved, ambiguous,
  or not-assessed identity status remain visible and are never silently resolved
  or candidate-selected. Clinical controls start with no selection and visible
  `Unanswered` text; unsupplied values persist as `not-assessed`, never `no`.
  Save failures remain in a focused semantic alert until a later save succeeds.
  Controls retain native keyboard operation, visible focus, 44px targets,
  non-color status text, responsive layout, and reduced-motion behavior. Focused
  UI checks passed with `node test_ui.mjs`; JavaScript syntax passed with `node
  --check public/app.js`; the full `npm test` suite passed repository,
  configuration, conditional legacy compatibility, real HTTP Authentication/
  role/revocation, CSRF, restricted CORS, idempotency, ETag/concurrency, latest,
  readiness, duplicate/unresolved medication, privacy, lifecycle, keyboard/focus,
  and persistent-error checks. Common REST profile checks passed 8/8, root
  discovery passed 65/65, and both repository `git diff --check` commands passed.
  No file under `insight-research/doc/`, protected clinical/model source, runtime
  data, or generated `graphify-out/` was read or modified. A configured Dashboard
  or gateway host harness supplying live UUID context is not present, so a real
  integrated host-browser run remains the next verification step and INS-029
  stays marked in progress. Live DDI resolution remains owned by INS-031.
- INS-028 Medical History v2 repository and security replacement (In progress).
  Medical History now uses a module-owned native SQLite repository with two
  ordered transactional migrations, WAL, strict migration-history checks,
  current assessments, immutable actor/request-attributed versions,
  actor-scoped idempotency, compatibility aliases, import metadata, and
  quarantine. Existing activation, submission, and v2 JSON files are ordered
  one-time import sources: canonical records and aliases retain UUID identity,
  unmapped or invalid records are quarantined without guessed values, corrupt
  or post-import-modified sources fail startup, and a failed import cannot
  replace visible database state with an empty store. The canonical create,
  UUID read/update, and Encounter-bound latest routes revalidate Authentication
  v2 on every request, permit only current psychiatrists, bind body attribution
  to the authenticated actor, require session-bound signed double-submit CSRF
  on writes, and expose credentialed CORS only to exact configured origins.
  Creates are transactionally idempotent, updates compare resource versions
  again under `BEGIN IMMEDIATE`, strong ETags prevent lost writes, liveness is
  dependency-free, readiness checks SQLite migration/integrity and
  Authentication reachability, and storage failures return explicit safe
  problem responses. Existing controlled-option, conditional, 20-medication,
  explicit-uncertainty, and medication-normalization validation remains
  authoritative; activation codes are compatibility aliases over canonical
  UUID assessments only. The full `npm test` suite passed repository fresh,
  canonical/legacy import, alias import, changed-source, corrupt-source,
  quarantine, configuration, existing validation, auth/role/revocation, CSRF,
  CORS, idempotency, ETag/concurrency, latest, and readiness checks. Changed
  JavaScript syntax passed `node --check`; all four JSON artifacts passed
  `python3 -m json.tool`; the assessment schema passed Draft 2020-12 schema
  checking; common REST profile checks passed 8/8; root discovery passed 65/65;
  and `git diff --check` passed. Database-at-rest encryption, backup/restore,
  retention operations, and controlled-clinical governance remain deployment
  gates; those release-level controls are the next work and keep INS-028 marked
  in progress. No file under `insight-research/doc/`, protected model/clinical
  source, runtime data, or generated `graphify-out/` was read or modified.
- INS-027 Severity UI integration without PHI browser storage (In progress).
  The bounded packet replaces patient-code lookup, query/history mutation,
  browser recents, and v1 calls with host-provided canonical Patient and
  Encounter UUID context and an optional Assessment UUID. The dependency-light
  frontend now exposes ES-module and frozen `window.InsightSeverity` mount/unmount
  APIs, confines rendering and listeners to the supplied root, aborts active
  requests during teardown, and permits only gateway-relative v2 API paths. It
  uses cookie credentials, CSRF, idempotent creates, ETag updates, validates
  returned identity/version/status, and displays only server-persisted evaluation
  state and scores; local ratings provide completion progress but no clinical
  interpretation. Completed and passed/skipped states are textually distinct,
  skipped explicitly infers no score, and request/context errors remain visible
  semantic urgent alerts until a later server action succeeds. All 30 score
  controls remain native keyboard buttons with textual labels, 44px targets,
  visible focus, non-color status text, WCAG AA-tested palette pairs, and
  reduced-motion suppression. The UI contract, README, and handoff now describe
  the host lifecycle and privacy boundary. The isolated full `npm test` suite
  passed repository, migration/import, configuration, server evaluator, auth,
  CSRF, CORS, concurrency, idempotency, legacy-failure, UI lifecycle/privacy/
  accessibility, and real HTTP UI completion/pass/load/error checks. JavaScript
  syntax, contract JSON syntax, Draft 2020-12 schema checking, browser storage/
  URL scans, common REST profile checks (8/8), root discovery (65/65), and both
  repository `git diff --check` commands passed. Pre-existing tracked
  `node_modules` deletions and untracked `graphify-out/` were preserved. No file
  under `insight-research/doc/`, protected clinical/model source, runtime data,
  or generated artifact was read or modified. A real Dashboard/gateway host
  harness supplying live UUID context is not present in this repository, so that
  integrated browser run remains the next verification step and INS-027 stays in
  progress.
- INS-026 Severity database and security replacement (In progress). The bounded
  packet replaces both writable JSON stores with a Node `DatabaseSync`
  repository and two ordered transactional SQLite migrations. Canonical v2
  assessments now persist Patient, Encounter, and Assessment UUIDs, resource
  versions, actor-scoped idempotency, and immutable actor/request-attributed
  version snapshots under WAL and `BEGIN IMMEDIATE` write transactions. Existing
  canonical v2 JSON records import once by source hash; records without canonical
  identity are retained in quarantine, while corrupt or post-import-modified JSON
  aborts startup instead of becoming an empty store. Every v2 clinical request
  revalidates the opaque cookie against Authentication
  `GET /api/auth/v2/session`, fails closed for revocation, malformed responses,
  gates, expiry, or role mismatch, and permits only psychiatrists. Writes require
  signed double-submit CSRF; CORS permits credentials only for exact configured
  origins; no auth bypass exists; production requires an explicit CSRF secret.
  Strong ETag updates are checked again inside the write transaction, preventing
  concurrent lost updates. Liveness is dependency-free and readiness checks
  configuration, SQLite integrity/migration state, and Authentication reachability
  with safe errors. Patient-code routes now fail closed with
  `SEVERITY_LEGACY_IDENTITY_UNMAPPED` rather than persisting unverifiable identity.
  The isolated full `npm test` suite passed all repository, fresh/import,
  quarantine, corruption, rollback, production configuration, auth/revocation/
  role, CSRF, CORS, ETag/concurrency, idempotency, evaluator, liveness/readiness,
  and legacy failure checks. JavaScript syntax, all three contract JSON files,
  Draft 2020-12 schema checking, common REST profile checks (8/8), root discovery
  (65/65), and both repository `git diff --check` commands passed. Pre-existing
  tracked `node_modules` deletions, earlier INS-025 edits, and `graphify-out/` were
  preserved; module HTTP tests therefore ran from `/tmp/kilo/severity-ins026` with
  freshly installed Express. No file under `insight-research/doc/`, protected
  source/model data, runtime JSON/database data, or generated artifact was read or
  modified. The standalone Severity UI still uses patient-code v1 calls and cannot
  submit until its separate UUID-context/auth/CSRF consumer migration, so INS-026
  remains marked in progress.
- INS-025 server-authoritative PANSS evaluation (In progress). Severity now has
  one pure evaluator for the exact P1-P7, N1-N7, and G1-G16 item set. It returns
  explicit `incomplete`, `passed`, or `completed` evaluation state, exact missing
  item codes for incomplete input, server-derived subscales/total for completed
  input, and scale/rule versions. V2 create/update routes and the retained v1 PUT
  adapter use the same evaluator; malformed ratings, unknown items, incomplete
  completion attempts, and malformed or mismatched browser score projections
  fail validation instead of being persisted. The v2 schema and contract now
  describe this evaluation envelope and projection-check behavior. Pure minimum
  and maximum vectors, malformed/incomplete/pass behavior, v2 HTTP behavior, and
  legacy equivalence passed in the isolated full `npm test` suite. JavaScript
  syntax, all three contract JSON files, Draft 2020-12 schema checking, common
  REST profile checks (8/8), root discovery (65/65), and both repository `git
  diff --check` commands passed. Pre-existing tracked dependency deletions,
  `graphify-out/`, and unrelated in-flight Severity edits were preserved. The
  next separate packet is UUID-only Severity UI/consumer migration; production
  authentication, CSRF, and database persistence remain separately gated.
- INS-024 embedded Diagnosis UI v2 assessment-context migration (In progress).
  The bounded packet now replaces patient-code state and alias query strings
  with host-provided Patient and Encounter UUID context. The embedded UI reads
  or idempotently initializes only v2 Encounter-bound assessments, validates
  returned context/schema, carries CSRF, schema, idempotency, and ETag headers,
  renders only server evaluation, and records confirm/bypass only through
  explicit clinician actions. Failed persistence restores the last server
  state and remains visible in a focused alert; context switches and unmount
  abort requests, clear timers, remove listeners, and never mutate host
  navigation. Focused embed acceptance and JavaScript syntax checks passed
  15/15 with `python3 -B -m test_embed`; v2 HTTP, UUID-only URL,
  server/legacy evaluation-equivalence, authority, concurrency, migration, and
  failure checks passed 12/12 with `python3 -B -m unittest
  test_diagnosis_v2_contracts.py -v`; v2 security passed 3/3. The full
  documented Diagnosis surface passed 157 checks across its isolated commands;
  common REST profile checks passed 8/8 and root discovery passed 65/65.
  Changed Python compilation and both repository `git diff --check` commands
  passed. No file under `insight-research/doc/`, protected clinical/model
  source, runtime database, or generated `graphify-out/` was read or modified.
  A real Dashboard/gateway browser integration run remains pending because this
  repository has no configured host harness that supplies live UUID context;
  that is the next integration verification step.
- INS-023 Diagnosis assessment UUID storage and route migration (In progress).
  Diagnosis now applies an ordered, idempotent v2 storage migration that stages
  every unmapped code-keyed session in a lossless quarantine instead of
  guessing an Encounter UUID. The explicit resolver accepts canonical Patient
  and Encounter UUID mappings, records typed unresolved/conflict/unavailable
  reasons, and atomically creates the assessment, legacy link, and immutable
  versioned `migrated` audit snapshot. Resolved legacy routes adapt to the same
  assessment and evaluator as v2, including explicit `definite`/`bypass`
  translation; criteria evidence and clinician decisions remain separate. V2
  create/read/update/latest and Treatment Plan snapshot routes now provide
  strong ETags, stale-write rejection, exact-body actor-scoped idempotency with
  exact create-response replay, generated or propagated request/correlation
  IDs, common problem responses, role authorization, and CSRF-protected writes.
  Focused migration/quarantine, v2 contract, authority, stale-write,
  idempotency, latest/snapshot, request-ID, legacy-equivalence, and audit tests
  passed 12/12 with `python3 -B -m unittest
  test_diagnosis_v2_contracts.py -v`; v2 Authentication/role/CSRF tests passed
  3/3 with `python3 -B -m unittest test_diagnosis_v2_security.py -v`. The full
  documented Diagnosis surface passed 153 checks across its isolated commands;
  common REST profile tests passed 8/8 and root discovery passed 65/65. Draft
  2020-12 schema validation, JSON syntax, changed-file Python compilation, and
  `git diff --check` passed. No file under `insight-research/doc/`, runtime
  database, protected clinical/model source, or generated `graphify-out/` was
  read or modified. Existing deployed legacy rows still require an operator or
  integration to supply verified Encounter mappings through the explicit
  resolver; unresolved rows remain quarantined. The next step is to execute
  that resolver against controlled deployment data and migrate consumers to the
  UUID-only latest/snapshot routes before retiring code-keyed compatibility.
- Feature 22 capability-completion sequence (In progress). INS-067 is complete;
  INS-011 still requires named accountable owners and release evidence, and
  INS-068 through INS-082 remain separate dependency-ordered work packets.
- INS-020 Treatment Plan OpenAPI reconciliation packet (In progress).
  OpenAPI `1.1.0` now matches the ten unconditional routes in the live FastAPI
  router, publishes exact current response envelopes and schema-version
  headers, references the real Authentication and DDI provider contracts, and
  records the BN Manager v3 provider operation. It documents current
  cookie-authentication, role, CSRF, `If-Match`, idempotency, request/correlation
  header, and error-envelope behavior without adding runtime behavior. The
  compatibility record classifies removal of five previously claimed but
  unimplemented operations as a breaking contract correction. The versioned
  runtime-envelope schema and both JSON contracts passed syntax checks and
  Draft 2020-12 schema validation. Focused TP-05 lint, compatibility,
  live-router parity, operation-issue mapping, provider-path, response-envelope,
  and recursive external-reference checks passed 6/6 with `python3 -B -m
  unittest tests/test_tp05_contracts.py -v`. Common REST profile checks passed
  8/8. Treatment Plan full discovery ran 22 cases: 15 passed and seven modules
  failed during import because pre-existing tracked runtime files, including
  `treatment_plan/safety_policy.py` and `treatment_plan/migration.py`, are absent
  from the mirrored repository. Root discovery ran 64 tests with 62 passing and
  the same two unrelated capability-matrix failures for missing issue headings
  and a stale project-overview hash. Runtime error envelopes still use FastAPI's
  legacy `{"detail": ...}` shape rather than the common RFC 9457 profile; fixing
  runtime behavior belongs to a later implementation packet, so INS-020 remains
  in progress.
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

- The 2026-07-30 audit of feature specs 11 through 20 corrected the confirmed
  packet-level gaps without changing protected source repositories. INS-066 now
  covers the current fourth project goal, has a current source hash, and defines
  every referenced completion packet. Authentication v2 enforces and tests UTC
  `Z` expiry. Add New Patient and Diagnosis consume the versioned Authentication
  UUID session shape; Diagnosis also rejects implicit confirmation when criteria
  are unmet. PANSS and Medical History now use semantic idempotency fingerprints,
  immutable create-response replay, stricter schema parity, and complete contract
  route documentation. The Medical History and Treatment Plan mirrors were made
  runnable at their canonical paths by restoring only missing module-owned files.
- DDI v1 now separates caller actions from server-owned audit attribution,
  machine-defines lifecycle preconditions, and fails closed on resolution and
  coverage consistency. BN Manager now publishes a strict v3 JSON Schema and
  OpenAPI for its real registry-only routes and rejects caller model text on the
  clinical endpoint. Treatment Plan now references that real BN v3 operation,
  validates UUID plan/request identifiers, and resolves provider references
  recursively.
- Verification passed: root contracts 65/65; Authentication 19/19; Add New
  Patient 50/50 plus frontend 3/3; Diagnosis v2 7/7 and its documented suites
  when run in isolated processes; Severity full suite; Medical History full
  suite; DDI 46/46; BN Manager 49/49; and Treatment Plan 61/61. Root and changed
  module `git diff --check` passed. One low-severity npm advisory remains in the
  locked Severity dependency tree.
- Clinical deployment remains blocked. INS-012 common-profile runtime rollout,
  protected DDI server implementation, PANSS and Medical History Authentication
  and CSRF integration, Diagnosis legacy-route delegation to the v2 authority,
  and cross-module end-to-end verification remain separate completion packets;
  this audit does not claim those deferred capabilities are deployed.
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
