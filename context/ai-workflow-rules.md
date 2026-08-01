# AI Workflow Rules

> **Project:** INSIGHT — schizophrenia Clinical Decision Support System (CDSS)  

## Approach

Build INSIGHT incrementally using a specification-driven, contract-first workflow.

Before changing code:

1. Identify the owning module and the exact clinical or technical decision point.
2. Read the module's normative context, API contract, schema, README, handoff, tests, and relevant clinical-model documentation.
3. Write a bounded acceptance statement for the change.
4. Confirm that the change preserves clinician authority, module ownership, patient identity, provenance, privacy, and model-safety boundaries.
5. Implement the smallest end-to-end increment that can be verified independently.

## Project Invariants

- INSIGHT is multi-module. Modules remain independently runnable and independently testable.
- Cross-module communication is through versioned internal REST APIs only.
- One unified Docker image does not mean one process, one database, one codebase, or merged module boundaries.
- Every persisted entity has exactly one owning module.
- Every persisted or exchanged dataset has an explicit, versioned schema.
- Canonical Patient and Encounter identifiers are UUIDs. `patientCode` is a human-facing alias, not the authoritative cross-module key.
- A system-generated treatment plan is an explainable draft, not a prescription, signed diagnosis, or clinical order.
- The psychiatrist remains the final decision-maker and must explicitly confirm or modify clinical outputs.
- 
- Clinical provenance and security audit are separate concerns and separate records.
- Finalized treatment plans are immutable. Later plans supersede prior versions; they do not rewrite them.
- Clinical model artifacts with placeholder or qualitative probabilities are not treated as clinically calibrated models.

## Scoping Rules

- Work on one feature unit, one contract change, or one clinical decision point at a time.
- Prefer small, verifiable increments over large speculative rewrites.
- Do not combine unrelated module boundaries in one implementation step.
- Do not combine a schema migration, API redesign, UI redesign, model change, and deployment change unless a single approved acceptance scenario genuinely requires all of them.
- Preserve compatibility through explicit adapters during migrations; do not maintain two independent domain implementations.
- Do not pay down documented prototype deferrals unless the current requirement triggers them or they block safety, correctness, privacy, or integration.
- Never use “cleanup” as justification for changing clinical behavior, model semantics, identifiers, persistence ownership, or public contracts.

Each work unit must state:
- user-visible outcome;
- affected API/schema versions;
- affected persisted entities;
- clinical rules or model artifacts involved;
- backward-compatibility impact;
- security/privacy impact;
- required tests and sign-offs.

## When to Split Work

Split an implementation step when it combines any of the following:

- UI behavior and an unrelated backend/domain change;
- a new endpoint and an unrelated migration;
- authentication changes and clinical decision logic;
- Bayesian-model calibration;
- model structure changes and probability/utility elicitation;
- more than one clinical decision point;
- a legacy compatibility adapter and removal of the legacy contract;
- production hardening and unrelated feature work;
- clinical validation and routine software refactoring.

If the change cannot be verified end to end with a focused test set and one clear rollback path, the scope is too broad.

## Clinical Safety and Clinician Authority

- Computed diagnosis criteria are evidence. The psychiatrist's explicit decision is the clinical assertion.
- A Primary Treatment Plan is a reproducible, explainable draft generated from an immutable Clinical Input Snapshot.
- A psychiatrist modification must preserve before/after values, author, timestamp, and rationale when required by policy.
- Finalization must occur server-side after safety revalidation and explicit clinician attestation.
- Hard contraindication rules must not be bypassed by a favorable posterior probability, recommendation rank, expected utility, UI preference, or model default.
- Relative risk factors may qualify or downgrade a recommendation but must not be promoted silently into absolute contraindications.
- Unknown evidence must trigger assessment, missing-information handling, or qualified output—not a fabricated certainty.
- Emergency or crisis instructions take precedence over routine treatment-setting and scheduling output. Urgent state must persist and must not be communicated by color alone.
- A dependency failure, model failure, unresolved medication, or incompatible schema must not produce a partial plan represented as complete.
- “No interactions found” is permitted only when all medication identities were resolved and all intended pairs were checked against a named knowledge-base version. Otherwise report incomplete coverage.

## Module Boundary and Ownership Rules

### Cross-module rules

- Never read, write, migrate, attach to, or query another module's database, JSON store, upload directory, cache, or runtime files.
- Never import another module's domain implementation to bypass its REST API.
- Never create shared ORM models, cross-database foreign keys, cross-schema SQL joins, or shared mutable clinical files.
- Shared packages may contain generated schema clients or low-level infrastructure only. They must not contain another module's domain behavior.
- A copied upstream payload is a snapshot, not authoritative state. Store its source module, contract/schema version, resource version or ETag, retrieval time, and response hash.
- Do not cascade deletes across modules. Owners publish lifecycle state; consumers handle unavailable, inactive, merged, stale, or superseded references explicitly.
- Ownership transfer requires a versioned architecture decision, export/import contracts, identifier-preservation plan, migration validation, and coordinated interface transition.

## Identity, Persistence, and Concurrency

- Use canonical `patientId` and `encounterId` UUIDs for all clinical writes and relationships.
- `patientCode` may be accepted by a compatibility resolver, but resolve it through Add New Patient before persistence or clinical processing.
- Never join records through patient name, patient code, timestamps, medication display text, or other mutable aliases.
- Never reuse a patient code.
- Persist assessment UUID, assessment type, Patient UUID, Encounter UUID, schema/rule/scale version, author, status, timestamps, and resource version.
- Preserve original clinician-entered medication text while adding normalized medication identity where available.
- Creates and clinical actions must support idempotency where retries could duplicate state.
- Mutable resources must use ETag/resource-version concurrency control. Reject stale writes instead of applying last-writer-wins silently.
- Applied migrations are append-only. Do not rewrite an already released migration; add a new reversible migration and test fresh and upgraded databases.
- Test data must use temporary isolated storage and must not remain in tracked or real runtime data.
- Runtime databases, JSON stores, logs, exports, backups, generated caches, and PID files are not source artifacts and must not be committed.

## API and Contract Rules

For a module that participates in the unified runtime, provide or preserve:

- liveness and readiness endpoints;
- a machine-readable contract/discovery endpoint;
- versioned OpenAPI and JSON/schema contracts;
- UTC timestamps;
- UUID identifiers;
- stable machine-readable error codes using the common problem-details profile;
- `X-Request-ID` and correlation/causation identifiers;
- ETag/resource version for mutable records;
- `Idempotency-Key` for creates and retryable actions;
- explicit module, interface, schema, model, rule, and knowledge-base versions where applicable.

Additional rules:

- Keep compatibility routes as thin adapters to one authoritative implementation.
- Do not duplicate evaluation logic in caller-specific routes.
- Validate incoming and outgoing REST payloads against the declared versioned schema.
- Reject unsupported major schema versions explicitly.

- Browser code must not contain hard-coded localhost service calls. Use configured reverse-proxy-aware base paths.
- A failed module must appear unavailable with a typed reason; it must not disappear silently from Dashboard.

## Authentication and Authorization

- Authentication is the sole trust provider.
- Downstream modules call the Authentication session endpoint. They do not decode JWTs, read the auth database, or trust request-body identity.
- A valid JWT signature alone is not sufficient. Authorization must reflect current server-side session, account, role, password-change gate, and disclaimer state.
- Canonical public roles are lower-case `admin` and `psychiatrist`. Treat legacy `user` only as a compatibility alias at the Authentication boundary.
- Admin-only and psychiatrist-only operations must be enforced server-side.
- Disabled accounts and revoked sessions lose access immediately.
- Password reset, password change, role change, and account disable must revoke affected sessions according to the approved auth contract.
- Use bcrypt or the current approved password-hashing policy; never store or log plaintext passwords.
- Cookie-authenticated writes require CSRF protection.
- Production cookies must be `HttpOnly`, appropriately `SameSite`, and `Secure` behind TLS.
- Reject default credentials and weak/default secrets outside local development.
- Mock/bypass authentication is development-only, explicitly configured, visible in readiness, and fail-closed in production.

## PHI, Security, and AI Assistant Rules

- Do not place PHI or patient aliases in URLs, query strings, browser history, filenames, localStorage, sessionStorage, caches, analytics, telemetry, error traces, or unprotected exports.
- Redact logs and audit payloads.
- Encrypt transport. Define and test production encryption-at-rest and key-management policy.
- Supply secrets through environment variables or mounted secret files; never hard-code them or commit them.
- Separate clinical provenance from access/security audit logs.
- The AI assistant is advisory and page-aware but cannot create, update, delete, finalize, or approve clinical data.
- Scrub AI-bound content server-side before it reaches any model provider.
- Patient names, codes, MRNs, dates, contact details, and other direct identifiers must not be sent to the AI provider.

## Bayesian Network and Clinical Model Governance

- If source passages conflict in a way that affects a node, state, edge, eligibility rule, priority rule, or recommendation, pause for resolution.
- Distinguish clearly among:
  - Patient State Nodes;
  - Intervention Eligibility Nodes;
  - Intervention Priority Nodes;
  - final Management Recommendation/Clinical Action Pattern states.
- Use explicit Unknown states where information may be unavailable or unassessed.
- Recommendation states should describe clinically meaningful action patterns, including monitoring, reassessment, referral, urgent evaluation, or coordinated combinations when source-supported.
- Do not add outcome-tradeoff nodes, source-coverage nodes, or evidence-status nodes to qualitative models unless the modeling scope is explicitly changed.
- Hard Contraindication Gates may be deterministic only when directly supported by the approved source and reviewed clinically.
- 
- 
- Record model stable ID, version, hash, schema version, engine version, target, accepted/ignored evidence, warnings, posterior result, and evaluation ID/time.
- Preserve round-trip metadata for a format when compatibility is part of the active contract.
- Structural/XSD validation, row-sum checks, dimension checks, and successful inference do not establish therapeutic safety.
- 

### Current model-format conflict

The supplied materials describe both:

- BN Manager contract 2.0.0, which is XML-only, exposes exactly four BIF 0.3 models.

Do not add, convert, register, or remove models until the canonical runtime format, model registry, migration policy, and ownership of duplicated artifacts are explicitly confirmed.

## DDI Knowledge and Medication Identity

- Use one authoritative interaction engine and one authoritative parser/normalization path.
- Preserve each medication instance, including dose, route, frequency, formulation, and duplicate occurrences where clinically relevant.
- Medication resolution is fail-closed: `resolved`, `ambiguous`, or `unknown`.
- Ambiguous or unknown medications are excluded from definitive pair coverage and surfaced for clinician resolution.
- 
- 
- 
- Record all pairs checked, unresolved medications, alerts, severity, mechanism, evidence, recommendation, knowledge-base version, and medication-set hash.
- Overrides require an attributable nonblank clinical rationale and must not erase the original alert.
- Browser localStorage administration/audit is prototype behavior, not the production source of truth.

## Frontend and Accessibility Rules

- Preserve the clean academic clinical design and shared design tokens unless the task explicitly changes the design system.
- Use teal as an accent, not as small body text where contrast is insufficient.
- Never communicate urgency, warning, success, or follow-up status by color alone; pair color with text and an icon or equivalent semantic cue.
- Preserve visible clinician-control wording near recommendations.
- Use semantic labels, table headers, keyboard navigation, visible focus indicators, and reduced-motion behavior.
- Keep interactive targets at the documented minimum size.
- Do not duplicate clinical calculation logic in the browser. The server/domain engine is authoritative; client calculations may be projections only and must be equivalence-tested.
- Every asynchronous failure must produce a visible, specific state. Do not leave a clinical action appearing successful after persistence fails.
- Embedded modules must scope DOM and event listeners to their root, avoid owning host navigation, and release listeners/resources on unmount or destroy.

## Protected Files and Artifacts

Do not modify the following unless the task explicitly includes the required owner/reviewer and validation work:

- Clinical source extracts: `BNs/**/Guideline-*.txt`.
- Clinical model artifacts: `BNs/**/*.xml`, `BNs/**/*.net`, `Modules/**/*.xml`, `Modules/**/*.net`.
- Model schemas such as `XSD.xml`.
- Model diagrams when they are generated from a canonical model; regenerate rather than hand-diverge.
- `graphify-out/**` and other generated architecture artifacts; never hand-edit them.
- Third-party library internals, vendored dependencies, and `node_modules/**`.
- Applied migration files.
- Runtime SQLite/JSON data, logs, caches, backups, exports, PID files, and test-generated data.
- Finalized-plan and supersession records; these are immutable at the persistence layer.
- Shared `DESIGN.md` copies unless the work is an approved design-system change.

For model changes, require all of the following in the same approved workstream:

- clinical source and decision point;
- rationale for every changed node/state/edge or deterministic rule;
- updated schema/serialization validation;
- updated diagram and model documentation;
- version/hash update;
- model tests and golden cases;
- clinical/model-owner review.

## Keeping Documentation and Contracts in Sync

Update the relevant authoritative files whenever implementation changes:

- architecture or module ownership;
- API behavior, errors, auth, CSRF, discovery, or readiness;
- schema, identifiers, persistence, migrations, or lifecycle;
- clinical rule scope or clinician-authority behavior;
- model registry, evidence schema, nodes, states, CPT status, version, or hash;
- security/privacy controls;
- deployment paths, ports, configuration, backup, restore, or rollback;
- feature scope, known limitations, or prototype deferrals.

Update order:

1. normative context/ADR and acceptance criteria;
2. machine-readable schema/API contract;
3. implementation;
4. contract/unit/integration tests;
5. README and handoff summary;
6. generated architecture/model artifacts through their generator.

Do not edit a generated file to make it agree with code. Fix the source and regenerate it.

When a module states that a Pydantic model, executable contract, or another file is the runtime source of truth, do not promote a documentation-only JSON schema into an independent source of behavior.

## Before Moving to the Next Unit

1. The unit works end to end within its declared scope.
2. The owning module still runs and tests independently.
3. 
4. 
5. Missing, stale, conflicting, unresolved, and dependency-failure paths were tested explicitly.
6. Relevant provider and consumer contracts pass.
7. 
8.
9. Documentation, schemas, tests, and generated artifacts are synchronized according to their source-of-truth hierarchy.
10. `progress-tracker.md` records completed work, evidence, commands run, results, remaining limitations, and open questions.
11. The change has a documented rollback path when it affects schema, data, model, knowledge base, or deployment.
12. 
