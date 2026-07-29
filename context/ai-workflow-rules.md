# AI Workflow Rules

> **Project:** INSIGHT — schizophrenia Clinical Decision Support System (CDSS)  
> **Status:** Derived from the supplied project documents and model artifacts.  
> **Safety status:** Research/decision-support software. The supplied materials do not establish clinical, regulatory, privacy, or production release approval.

## Approach

Build INSIGHT incrementally using a specification-driven, contract-first workflow.

Before changing code:

1. Identify the owning module and the exact clinical or technical decision point.
2. Read the module's normative context, API contract, schema, README, handoff, tests, and relevant clinical-model documentation.
3. Write a bounded acceptance statement for the change.
4. Confirm that the change preserves clinician authority, module ownership, patient identity, provenance, privacy, and model-safety boundaries.
5. Implement the smallest end-to-end increment that can be verified independently.

Do not infer product behavior, clinical rules, probability values, utility values, source authority, role permissions, or data ownership from filenames, UI text, model shape, or adjacent modules.

A passing parser, schema validator, unit test, or Bayesian-network inference run proves technical consistency only. It does not prove clinical validity or release readiness.

## Requirement Authority and Precedence

Use the following precedence when sources overlap:

1. The current explicit user task and approved product/clinical decisions.
2. Files explicitly marked normative or source of truth, including:
   - `Modules/Treatment Plan/CONTEXT-MAP.md`
   - `CONTEXT.md`
   - a module-local API contract or governance file explicitly named as authoritative by that module
   - versioned runtime schemas and executable contract tests
3. Module-local context, README, handoff, and current tests.
4. `BNs/CONTEXT.md` for source-backed clinical-model terminology and modeling rules.
5. Cross-module plans such as `INSIGHT_Treatment_Plan_and_Unification_Plan.md`.
6. General prompts, design descriptions, diagrams, screenshots, and legacy artifacts.

When a README or handoff names an authoritative file that is not available, do not reconstruct the missing contract from summaries. Record the missing source as a blocker in `progress-tracker.md` and request it.

When two sources of equal authority disagree, stop. Document the conflict, affected modules, safety impact, and available options. Do not silently select the newer-looking file, the more convenient implementation, or the stricter/looser clinical rule.

## Project Invariants

- INSIGHT is multi-module. Modules remain independently runnable and independently testable.
- Cross-module communication is through versioned internal REST APIs only.
- One unified Docker image does not mean one process, one database, one codebase, or merged module boundaries.
- Every persisted entity has exactly one owning module.
- Every persisted or exchanged dataset has an explicit, versioned schema.
- Canonical Patient and Encounter identifiers are UUIDs. `patientCode` is a human-facing alias, not the authoritative cross-module key.
- A system-generated treatment plan is an explainable draft, not a prescription, signed diagnosis, or clinical order.
- The psychiatrist remains the final decision-maker and must explicitly confirm or modify clinical outputs.
- Missing, unknown, stale, unresolved, or conflicting information is represented explicitly and is never converted silently into a negative, normal, safe, or absent state.
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

- owning module;
- user-visible outcome;
- affected API/schema versions;
- affected persisted entities;
- clinical rules or model artifacts involved;
- backward-compatibility impact;
- security/privacy impact;
- required tests and sign-offs.

## When to Split Work

Split an implementation step when it combines any of the following:

- two or more owning modules;
- UI behavior and an unrelated backend/domain change;
- a new endpoint and an unrelated migration;
- authentication changes and clinical decision logic;
- deterministic safety policy and Bayesian-model calibration;
- model structure changes and probability/utility elicitation;
- more than one clinical decision point;
- a legacy compatibility adapter and removal of the legacy contract;
- behavior not defined in available context or contract files;
- production hardening and unrelated feature work;
- clinical validation and routine software refactoring.

If the change cannot be verified end to end with a focused test set and one clear rollback path, the scope is too broad.

## Clinical Safety and Clinician Authority

- Do not present INSIGHT output as an autonomous diagnosis, prescription, treatment order, or mandatory action.
- Computed diagnosis criteria are evidence. The psychiatrist's explicit decision is the clinical assertion.
- A Primary Treatment Plan is a reproducible, explainable draft generated from an immutable Clinical Input Snapshot.
- A psychiatrist modification must preserve before/after values, author, timestamp, and rationale when required by policy.
- Re-run all affected deterministic safety checks after a clinician changes medication, dose, route, frequency, setting, or follow-up timing.
- Finalization must occur server-side after safety revalidation and explicit clinician attestation.
- Hard contraindication rules must not be bypassed by a favorable posterior probability, recommendation rank, expected utility, UI preference, or model default.
- Relative risk factors may qualify or downgrade a recommendation but must not be promoted silently into absolute contraindications.
- Unknown evidence must trigger assessment, missing-information handling, or qualified output—not a fabricated certainty.
- Emergency or crisis instructions take precedence over routine treatment-setting and scheduling output. Urgent state must persist and must not be communicated by color alone.
- A dependency failure, model failure, unresolved medication, or incompatible schema must not produce a partial plan represented as complete.
- “No interactions found” is permitted only when all medication identities were resolved and all intended pairs were checked against a named knowledge-base version. Otherwise report incomplete coverage.
- Clinical release requires independent psychiatrist review, approved reference cases, hazard analysis, privacy/regulatory review, and explicit sign-off. Software tests alone are insufficient.

## Module Boundary and Ownership Rules

### Cross-module rules

- Never read, write, migrate, attach to, or query another module's database, JSON store, upload directory, cache, or runtime files.
- Never import another module's domain implementation to bypass its REST API.
- Never create shared ORM models, cross-database foreign keys, cross-schema SQL joins, or shared mutable clinical files.
- Shared packages may contain generated schema clients or low-level infrastructure only. They must not contain another module's domain behavior.
- A copied upstream payload is a snapshot, not authoritative state. Store its source module, contract/schema version, resource version or ETag, retrieval time, and response hash.
- Do not cascade deletes across modules. Owners publish lifecycle state; consumers handle unavailable, inactive, merged, stale, or superseded references explicitly.
- Ownership transfer requires a versioned architecture decision, export/import contracts, identifier-preservation plan, migration validation, and coordinated interface transition.

### Entity ownership

- **Authentication:** credentials, accounts, roles, sessions, disclaimer acceptance, and security/auth audit events.
- **Dashboard:** navigation shell, dashboard-local sessions, and workspace shell events only.
- **Add New Patient:** canonical Patient and Encounter identity and lifecycle.
- **Diagnosis:** diagnosis assessments and computed diagnostic evidence.
- **Severity:** severity assessments and scale responses.
- **Medical History:** medical-history assessments/submissions.
- **DDI Checker:** medication knowledge, knowledge-base revisions, interaction evaluation, and associated evidence governance.
- **BN Manager:** registered clinical model loading, validation, and evaluation.
- **Treatment Plan:** Recommendation Runs, immutable Clinical Input Snapshots, Primary Plans, Plan Edits, Final Plans, supersession, and treatment-plan clinical provenance.

Do not create a second writer for an entity because the current owner is incomplete or inconvenient.

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
- Readiness must fail when a required dependency or production configuration is unavailable; it must not expose secrets, internal paths, or credentials.
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
- Redact logs and audit payloads. Store stable identifiers only where required and authorized.
- Encrypt transport. Define and test production encryption-at-rest and key-management policy.
- Supply secrets through environment variables or mounted secret files; never hard-code them or commit them.
- Separate clinical provenance from access/security audit logs.
- The AI assistant is advisory and page-aware but cannot create, update, delete, finalize, or approve clinical data.
- Scrub AI-bound content server-side before it reaches any model provider.
- Patient names, codes, MRNs, dates, contact details, and other direct identifiers must not be sent to the AI provider.
- Do not rely only on regex scrubbing when structured fields are available; omit identifiers structurally first, then apply scrubbing as defense in depth.
- Store AI conversations only under an approved retention, access, encryption, deletion, backup, and provider policy. The archive does not define that policy fully.
- Do not select an LLM provider, model, hosting location, or data-retention mode until those requirements are approved.

## Bayesian Network and Clinical Model Governance

- Begin with one approved Clinical Decision Point. Splitting one source into multiple decision points requires explicit permission.
- Build only from supplied, approved clinical sources. Do not add medical rules from memory or general knowledge.
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
- Placeholder CPTs must be labeled as placeholders. Neutral or directional seed values are not calibrated evidence.
- Do not invent probabilities, utilities, calibration claims, sensitivity/specificity, treatment effects, or population performance.
- Record model stable ID, version, hash, schema version, engine version, target, accepted/ignored evidence, warnings, posterior result, and evaluation ID/time.
- Preserve round-trip metadata for a format when compatibility is part of the active contract.
- Structural/XSD validation, row-sum checks, dimension checks, and successful inference do not establish therapeutic safety.
- Approved model artifacts must be versioned and signed or otherwise integrity-protected before clinical use.

### Current model-format conflict

The supplied materials describe both:

- legacy/frozen Hugin `.net` models, including Bayesian Networks and influence diagrams; and
- BN Manager contract 2.0.0, which is XML-only, exposes exactly four BIF 0.3 models, and excludes `.net` and the legacy workbench.

Do not add, convert, register, or remove models until the canonical runtime format, model registry, migration policy, and ownership of duplicated artifacts are explicitly confirmed.

## DDI Knowledge and Medication Identity

- Use one authoritative interaction engine and one authoritative parser/normalization path.
- Preserve each medication instance, including dose, route, frequency, formulation, and duplicate occurrences where clinically relevant.
- Medication resolution is fail-closed: `resolved`, `ambiguous`, or `unknown`.
- Ambiguous or unknown medications are excluded from definitive pair coverage and surfaced for clinician resolution.
- Only reviewed and approved interaction records may generate clinical alerts.
- Never activate `rxnorm-pending` or otherwise unresolved identities silently.
- Knowledge-base revisions use an immutable lifecycle such as `draft -> reviewed -> active -> retired`, with authorization, provenance, rollback, and clinical approval.
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

## Handling Missing or Ambiguous Requirements

- Do not invent behavior absent from the context and contract files.
- Add each unresolved question to `progress-tracker.md` with:
  - affected module(s);
  - conflicting/missing source files;
  - exact decision required;
  - safety, privacy, migration, and compatibility impact;
  - whether work is blocked or can proceed in an isolated unit.
- Resolve the question in the owning context, contract, schema, or ADR before implementation.
- Do not encode a recommendation from a source summary when the underlying source excerpt is unavailable.
- Do not infer stakeholder approval, clinical sign-off, regulatory classification, licensing permission, or production readiness.

### Blocking questions identified in the supplied archive

1. Which architecture is the implementation baseline: the older monolithic React/FastAPI prototype in `insight-prompt.md`, or the newer standalone REST-only module architecture?
2. Which Bayesian-model format and registry are canonical: frozen `.net` artifacts or BN Manager 2.0 XML-only four-model registry?
3. Which duplicated BN/model copies are authoritative: `BNs/**` or the copies under `Modules/**`?
4. Several module READMEs name authoritative API-contract/governance files that were not included. Those files are required before modifying the corresponding public contracts.
5. Is INSIGHT limited to an academic research prototype, or is real clinical deployment intended? The supplied Treatment Plan release gate is explicitly blocked.
6. What are the approved AI provider, hosting, data-use, retention, chat-access, deletion, and backup policies?
7. What is the approved resolution for overlapping suicide-risk observations and authoritative medication/allergy ownership?
8. Which current prototype behaviors must remain temporarily compatible: patient-code routes, JSON persistence, open CORS, localStorage state, and auth bypasses?

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

## Verification by Affected Module

Use the module's documented command and preserve independent execution. Based on the supplied handoffs, the expected verification surfaces include:

| Module | Minimum documented verification |
|---|---|
| Authentication | `python -B -m unittest discover -s tests` |
| Dashboard | `npm test` |
| Add New Patient | `python -m unittest test_add_new_patient_backend.py` and the applicable frontend smoke test |
| Diagnosis | the documented stdlib test modules, including core REST/criteria, auth, CSRF, patient identity, readiness, discovery, embedding, and contract checks |
| Severity | `node test_api.js` plus focused manual/API verification when UI behavior changes |
| Medical History | `node --check server.js`, `node --check public/app.js`, and `npm test` |
| DDI Checker | `npm test`, ingestion/parser parity tests, and the applicable KB validation command; use the clinical activation validator only for release-candidate KBs |
| BN Manager | `python -m unittest discover -s tests -v` |
| Treatment Plan | backend tests, frontend tests, ownership/identifier/contract governance scripts, migration tests, and the release-gate check |

Also run:

- provider contract tests for changed APIs;
- consumer contract tests for affected callers;
- real HTTP integration tests for cross-module changes;
- fresh-database and upgrade migration tests for persistence changes;
- restart/recovery and rollback tests for deployment changes;
- Windows Docker Desktop and Ubuntu unified-image smoke tests for packaging changes;
- security-header/TLS tests when nginx or public routing changes;
- accessibility checks for affected clinical UI;
- clinician-authored golden, edge, counterfactual, failure, and override cases for clinical behavior.

Do not substitute `npm run build` for the module's actual verification command. Run it only where a build script exists. For unified deployment changes, the final Docker image must build and all module health/readiness and integration checks must pass.

## Before Moving to the Next Unit

1. The unit works end to end within its declared scope.
2. The owning module still runs and tests independently.
3. All changed persisted/exchanged data validates against the declared versioned schema.
4. No module-ownership, REST-only, canonical-identity, clinician-authority, privacy, or provenance invariant was violated.
5. Missing, stale, conflicting, unresolved, and dependency-failure paths were tested explicitly.
6. Relevant provider and consumer contracts pass.
7. Security, CSRF, role, and session-revocation behavior remains enforced where applicable.
8. Clinical models remain clearly labeled as calibrated, qualitative, placeholder, or unapproved; no status was upgraded without evidence and sign-off.
9. Documentation, schemas, tests, and generated artifacts are synchronized according to their source-of-truth hierarchy.
10. `progress-tracker.md` records completed work, evidence, commands run, results, remaining limitations, and open questions.
11. The change has a documented rollback path when it affects schema, data, model, knowledge base, or deployment.
12. No release claim is made while the clinical/regulatory/privacy gate remains blocked.
