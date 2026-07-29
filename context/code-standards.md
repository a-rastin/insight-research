# INSIGHT Code Standards

> **Scope:** These standards apply to the INSIGHT clinical decision support system and all independently deployable modules, services, frontends, data stores, clinical rules, Bayesian-network assets, and integration adapters.

## Normative Language

- **MUST** and **MUST NOT** define mandatory requirements.
- **SHOULD** and **SHOULD NOT** define the expected default; exceptions require a documented reason.
- **MAY** identifies an optional practice.
- A module-specific canonical contract governs that module's request and response details.
- The system context map governs entity ownership and cross-module coupling.
- The unification plan governs migration toward the target architecture.
- READMEs and handoff documents describe current behavior and known gaps; they do not override stricter security, privacy, clinical-safety, or ownership rules.
- Generated diagrams and derivative artifacts are explanatory outputs, not independent sources of truth.
- Referenced canonical contracts that are absent from the supplied archive MUST be obtained before implementing or changing the affected interface. Their contents MUST NOT be inferred.

## General

- Keep every INSIGHT module independently runnable, testable, versioned, and deployable.
- Do not merge modules into a shared application codebase merely because they are packaged in one Docker image.
- A unified image MAY contain multiple processes, but each module MUST retain its own process boundary, configuration, routes, migrations, data directory, and health state.
- Communicate between modules through versioned REST APIs only.
- Do not use cross-module database queries, shared ORM models, shared mutable files, browser storage, or implementation-language imports as integration mechanisms.
- Assign exactly one owning module to every persistent entity instance.
- Keep modules small and single-purpose. Do not mix authentication, clinical reasoning, persistence, presentation, and integration concerns in one component or route.
- Fix root causes rather than layering compatibility workarounds indefinitely.
- Preserve existing public behavior through explicit, time-bounded compatibility adapters when contracts evolve.
- Prefer the smallest correct change. Do not introduce speculative dependencies or abstractions without a demonstrated requirement.
- Never simplify away input validation, authorization, privacy controls, auditability, accessibility, provenance, or clinical-safety checks.
- Do not silently guess missing, stale, ambiguous, conflicting, or unresolved clinical data. Represent the condition explicitly and degrade safely.
- Keep clinician judgment explicit. A model result, criteria result, or recommendation is evidence for review, not an automatic clinical decision.

## Source Precedence and Change Control

- For cross-module ownership and coupling, follow the normative context map.
- For a module's API shape and behavior, follow its declared canonical contract.
- When two supplied sources conflict, do not choose silently. Document the conflict and resolve it through an approved contract or ADR.
- Do not duplicate canonical contract definitions across READMEs, frontend code, tests, and schemas. Reference or generate from the canonical source where practical.
- Update documentation, schemas, tests, diagrams, and migration notes in the same change whenever a contract or controlled field changes.
- Do not commit PHI, credentials, signing keys, real signatures, clinical secrets, local databases, generated runtime state, or test residue to source control.

## Supported Languages and Runtime Boundaries

### Python

- Python is the standard backend language for the target INSIGHT architecture.
- Each Python service MUST declare and pin its supported Python version and dependencies.
- Existing module documents cite different Python baselines; the unified build MUST choose an explicit compatible version rather than assuming one.
- Use type annotations for public functions, service interfaces, repositories, domain entities, and boundary models.
- Keep route handlers thin. Place domain logic, clinical rules, repositories, adapters, and integrations in separate modules.
- Use explicit domain exceptions below the HTTP layer. Do not allow raw database, parser, or filesystem exceptions to define API behavior.
- Centralize configuration in a validated, immutable settings object. Do not scatter direct environment-variable reads throughout the codebase.
- Use context managers and deterministic cleanup for database connections, files, locks, temporary artifacts, and network clients.
- Do not use mutable global state for clinical data, authentication state, or request-specific decisions.
- Preserve deterministic behavior in scoring, criteria evaluation, safety rules, and model preprocessing.

### JavaScript and React

- The archive establishes a hybrid frontend strategy; do not impose one framework on every module.
- Simple embeddable modules SHOULD use dependency-light vanilla HTML, CSS, and JavaScript when their complexity does not justify a build system.
- The Treatment Plan review workspace MAY use React with Vite because its interaction complexity is explicitly greater.
- A frontend module MUST expose a bounded lifecycle such as create, mount, and unmount when it is embedded in a host shell.
- A module MUST NOT mutate host navigation, global history, or unrelated DOM outside its mount boundary.
- Browser code MUST obtain API base URLs from configuration or the host integration contract. Do not hardcode localhost, ports, schemes, or deployment hosts.
- Keep clinical logic and authoritative scoring on the server. The browser MAY render server results but MUST NOT reimplement or supersede canonical rules.
- Do not mandate TypeScript project-wide. No project-wide TypeScript requirement is established by the supplied corpus. A module MAY use TypeScript only through an explicit module decision and consistent toolchain.
- Avoid adding a bundler, state-management library, or component framework to a simple module without a documented trigger.

## FastAPI Services

- FastAPI is the standard target framework for Python HTTP services.
- Validate all request path parameters, query parameters, headers, cookies, and bodies before domain logic runs.
- Use Pydantic or an equivalent declared schema as the runtime boundary contract.
- Keep routers focused on HTTP concerns: parsing, dependency resolution, authorization, status codes, and response serialization.
- Keep domain services independent from FastAPI request and response objects.
- Register literal routes before dynamic catch-all routes such as `/{code}` to prevent accidental shadowing.
- Resolve authentication before CSRF validation on newly protected write routes so unauthenticated callers receive the correct authentication failure without leaking token-validation behavior.
- Provide separate liveness and readiness endpoints.
- Liveness MUST not depend on downstream clinical services.
- Readiness MAY verify local configuration, storage, migrations, and required dependencies, but MUST NOT expose secrets or sensitive values.
- Implement graceful startup and shutdown, including connection cleanup and in-flight request handling.
- Run as a non-root user in production containers.

## API Routes and Inter-Module Contracts

- Version public module APIs under a stable prefix, such as `/api/<module>/v1`.
- Use REST only for module-to-module communication.
- Publish a machine-readable contract for every module API, including OpenAPI and versioned schemas where applicable.
- Provide a contract-discovery endpoint when required by the target common profile.
- Use consistent liveness, readiness, and contract endpoints across modules.
- Use canonical UUIDs for resources and encounters. Human-readable codes are aliases, not relational keys.
- Use UTC for persisted and exchanged timestamps and serialize them with an explicit offset.
- Propagate `X-Request-ID` or the approved request-correlation identifier across module calls.
- Preserve causation and correlation identifiers for multi-step clinical workflows.
- Support optimistic concurrency for mutable resources using ETags or an equivalent explicit resource version.
- Return `412 Precondition Failed` or the contract-defined equivalent for stale writes; do not silently overwrite concurrent changes.
- Require an idempotency key for retryable operations that create durable clinical effects, including recommendation runs and plan finalization.
- Return the prior successful result for a repeated idempotency key with the same request semantics.
- Reject reuse of an idempotency key with materially different input.
- Authenticate and authorize before every protected operation; do not trust role, user, patient, or clinician identifiers supplied in the request body.
- Enforce resource ownership and permitted scope before reads or mutations.
- Do not place PHI in query strings, URLs, filenames, cache keys, analytics identifiers, or downloadable artifact names.
- Use predictable response envelopes during a compatibility window and migrate toward RFC 9457 problem details for errors.
- Include a stable machine-readable error code, safe human-readable summary, request identifier, and field-level details when appropriate.
- Do not expose stack traces, SQL, filesystem paths, secrets, tokens, PHI, or internal dependency details in API errors.
- Represent downstream failure, partial coverage, stale data, and schema incompatibility as typed states. Do not convert them into a false successful response.
- Cache another module's data only as a documented snapshot containing the source module, interface version, resource version or ETag, retrieval time, and integrity hash where required.
- Do not implement cross-module cascade deletes. Coordinate lifecycle changes through explicit APIs and auditable workflows.

## Authentication and Authorization

- Authentication remains an independent FastAPI service and the canonical authority for user sessions and roles.
- Downstream modules MUST resolve and verify sessions through Authentication REST APIs.
- Downstream modules MUST NOT decode Authentication JWTs as their sole authorization mechanism and MUST NOT read the Authentication database directly.
- Treat a JWT as one component of a session, not sufficient proof by itself. Recheck user status, role, disclaimer state, revocation, and server-side session state as defined by the Authentication contract.
- Store browser authentication only in secure HttpOnly cookies. Do not store bearer tokens or session secrets in `localStorage` or `sessionStorage`.
- Configure production cookies with `Secure`, `HttpOnly`, and the approved `SameSite` policy.
- Apply signed double-submit CSRF protection or the canonical equivalent to every state-changing browser request.
- Normalize canonical role values to lowercase. Preserve legacy role compatibility only through an explicit adapter and removal plan.
- Use bcrypt with the documented work factor or a formally approved stronger password-hashing configuration.
- Revoke active sessions when a user is disabled, reset, or assigned a new role.
- Use generic login failures and rate limiting or lockout controls to reduce account enumeration and brute-force risk.
- Do not record plaintext passwords, password hashes, JWTs, session cookies, CSRF secrets, reset tokens, or equivalent credentials in audit logs.
- Development mock authentication MUST be explicitly gated, visibly marked, disabled by default, and impossible to enable in production or multi-worker deployment by accident.

## Privacy, PHI, and AI Integration

- Encrypt sensitive data in transit and at rest according to the deployment security design.
- Do not persist clinical PHI in browser storage, static files, unprotected JSON, client caches, analytics systems, or error telemetry.
- Move prototype browser and JSON persistence to module-owned server repositories before production clinical use.
- Scrub patient identifiers before any content is sent to an LLM, including names, patient codes, medical-record identifiers, phone numbers, email addresses, dates, and other policy-defined identifiers.
- The AI assistant MUST be page-aware but read-only. It MUST NOT create, mutate, sign, finalize, delete, or submit clinical records.
- AI output MUST be presented as advisory text requiring clinician review.
- Store AI conversations only in approved server-owned persistence with defined access control, retention, redaction, and audit behavior.
- Do not include PHI or secrets in logs. Use structured redaction at the logging boundary rather than relying on individual call sites.
- Separate clinical provenance from security audit events. They have different consumers, retention rules, and evidentiary purposes.

## Data and Storage

- Every persisted or exchanged dataset MUST have an explicit schema and version.
- Use module-owned repositories and migrations. Each module owns its tables, files, migration history, backup procedure, and restore validation.
- SQLite MAY be used for supported local or prototype deployments; production migration to PostgreSQL MUST occur through a repository seam and tested migrations rather than direct cross-database assumptions.
- Do not share database tables, schemas, connections, or ORM entities across module ownership boundaries.
- Do not use a patient code, display label, medication text, or other mutable alias as a foreign key.
- Use a canonical immutable patient UUID and encounter UUID.
- Treat patient codes as stable, case-insensitive aliases subject to uniqueness and collision handling.
- Quarantine unresolved identity collisions; do not guess which patient record is correct.
- Create logically coupled records, such as a patient and intake record, in one transaction when the module contract requires atomicity.
- Use repositories or protocol-defined storage interfaces so domain logic can be tested against in-memory and production implementations.
- Apply ordered, idempotent, and, where feasible, reversible migrations.
- Record the schema version and migration state in readiness checks without exposing sensitive data.
- Enable database integrity and concurrency controls appropriate to the engine, including transaction boundaries and SQLite WAL where the module design requires it.
- Do not swallow corruption, parse failure, or persistence failure and continue with empty data.
- On storage failure, roll back in-memory state and return an explicit failure.
- Define and test backup, restore, retention, and disaster-recovery procedures before production release.
- Keep large generated artifacts or model files in approved file or blob storage when appropriate; keep searchable metadata and ownership information in the database.
- Do not store large generated content directly in relational fields without a documented reason.
- Do not allow user-controlled filesystem paths. Resolve only registered, normalized, relative paths beneath an approved module-owned root.

## Clinical Data and Identity

- Model clinical input as a versioned, immutable snapshot whenever it participates in a recommendation or finalized plan.
- A snapshot MUST identify its patient, encounter, source observations, timestamps, schema version, and provenance.
- Do not mutate historical snapshots after a recommendation has been generated.
- Represent missing, stale, contradictory, low-quality, or unresolved evidence explicitly.
- Do not substitute normal values, averages, or inferred answers for missing clinical evidence unless an approved clinical rule explicitly defines that behavior and records it.
- Keep assessment ownership with the module responsible for that assessment type.
- Use stable assessment identifiers and versions when another module references an assessment.
- Preserve source values and normalized values separately when normalization affects clinical interpretation.
- Keep medication instances distinct even when two rows normalize to the same medication; do not collapse exact duplicates without an explicit workflow decision.
- Medication identity resolution MUST return a typed state such as resolved, ambiguous, or unknown.
- Ambiguous or unknown medications MUST remain visible as unresolved coverage; do not invent an identifier or interaction result.

## Clinical Rules, Scoring, and Safety Logic

- The server is authoritative for clinical scoring, diagnostic criteria evaluation, safety checks, and eligibility rules.
- Recompute all derived scores and item totals from validated source inputs on the server.
- If a client submits derived values, compare them with the server result and reject mismatches rather than trusting them.
- Keep pure clinical evaluators deterministic and free of HTTP, UI, and persistence concerns.
- Version every rule set, scoring algorithm, threshold, terminology set, and safety policy that can affect an output.
- Store the exact rule or policy version used for each durable result.
- Distinguish hard contraindication gates from relative-risk signals.
- Deterministic safety gates MUST override or constrain probabilistic recommendations where the approved clinical design requires it.
- A diagnostic criteria result marked `met` is supporting evidence only. Diagnosis confirmation remains an explicit psychiatrist action.
- Permit an approved clinician bypass where the diagnosis workflow requires it, and record the clinician decision and checked criteria without fabricating a derived diagnosis key.
- Do not automatically confirm, coerce, or preselect a clinical decision based solely on model output.
- Safety findings MUST be typed and traceable, including drug-drug interactions, allergies, contraindications, risk conditions, missing data, stale data, conflicting data, and evidence-quality concerns.
- A safety override MUST require an attributable, non-empty rationale within the contract-defined limit.
- Do not conceal incomplete medication or knowledge-base coverage behind a green or successful status.

## Bayesian Networks and Model Assets

- Treat model files as versioned clinical artifacts, not ordinary configuration.
- The BN Manager canonical ingestion contract is XML BIF 0.3 for its registered networks.
- Register models by approved stable identifiers. Do not accept arbitrary caller-supplied model paths.
- Store or return the model identifier, semantic version, content hash, schema version, target variable, and provenance for every evaluation.
- Parse XML with external entities, network access, and unsafe expansion disabled.
- Validate every model structurally against the XSD and semantically against the network contract.
- Semantic validation MUST include unique node and state identifiers, valid references, parent ordering, complete table dimensions, finite numeric values, probability row sums within the approved tolerance, valid targets, and supported node types.
- XSD validity alone is not sufficient for clinical acceptance.
- Empty chance-node probability tables are invalid for clinical evaluation.
- Placeholder, neutral, compact, illustrative, or uncalibrated CPTs MUST be explicitly labeled and MUST block production clinical release until approved.
- A compact one-row conditional table MAY be broadcast only under the BN Manager's narrowly documented rule: exactly one complete child-state row and an explicit broadcast marker in the parsed result.
- Preserve parent ordering exactly. For Hugin-style tables, the leftmost parent changes slowest and the rightmost parent changes fastest.
- Keep decision-node and chance-node semantics distinct. An empty decision potential in an influence diagram MUST NOT be interpreted as a missing chance CPT.
- Include an explicit `Unknown` or equivalent state where the clinical model requires uncertainty rather than silently forcing evidence into a known state.
- Reject or report unknown evidence variables and states. Do not silently ignore them.
- Return accepted evidence, ignored evidence, warnings, target posterior, and model identity in a traceable evaluation result.
- Do not add outcome-tradeoff nodes merely to force agreement among source documents.
- Pause encoding when source recommendations conflict; resolve the conflict explicitly rather than averaging or reconciling silently.
- Rationale labels and intervention mappings MUST be source-backed and versioned.
- Clinical model changes require structural tests, semantic tests, regression fixtures, clinician review, calibration evidence where applicable, and approval before activation.

## Drug-Drug Interaction Knowledge Base

- Maintain one authoritative normalization and parsing pipeline for the DDI knowledge base.
- Derive the knowledge-base identity reproducibly from exact source bytes and declared parser, schema, and normalization versions.
- Do not include absolute paths or generation timestamps in the stable identity hash.
- Only approved interactions may enter the active clinical index.
- Block activation when the approved interaction set is empty or validation fails.
- Validate the knowledge-base root, schema, unique identifiers, aliases, review state, provenance, confidence, duplicate pairs, and conflicting pairs.
- Keep ingestion validation separate from the stricter clinical activation gate.
- Treat medication resolution as fail-closed. Skip unresolved or ambiguous pairs and report candidates and coverage gaps explicitly.
- Keep review and override records in server-owned, attributable, auditable persistence before production use.
- An override MUST not mutate the underlying knowledge-base fact.

## Treatment Plans, Provenance, and Audit

- Treat a generated primary plan as an explainable draft for psychiatrist review, not a prescription or order.
- Make recommendation runs idempotent and traceable to the exact clinical snapshot, rules, model versions, knowledge-base versions, and source evidence.
- Record recommendation evidence sufficient to reconstruct why each item appeared, including facts, policy or model version, posterior or deterministic result, and source metadata.
- Record clinician edits as attributable structured changes rather than overwriting the generated draft without history.
- Maintain an append-only edit ledger for clinically material changes.
- Enforce strong concurrency during plan review and finalization.
- Finalized plans MUST be immutable.
- Corrections to a finalized plan MUST create a superseding plan that references the prior version; never rewrite the signed historical record.
- Finalization MUST repeat server-side authorization, concurrency, required-field, and safety checks.
- Finalization MUST be idempotent and return the existing finalized result for a legitimate retry.
- Preserve signatures, timestamps, actor identity, source snapshot, recommendation run, edits, safety findings, and model or knowledge versions as part of plan provenance.
- Keep clinical provenance independent from operational and security logs.

## Validation and Error Handling

- Validate unknown external input at every trust boundary before use.
- Apply normalization only after preserving the submitted value where audit or clinical interpretation requires it.
- Reject unsupported fields when strict contracts require it; do not silently drop clinically meaningful input.
- Use consistent field-level validation messages without exposing internal implementation details.
- Fail closed for authentication, authorization, model activation, medication identity, and clinically material schema incompatibility.
- Fail visibly for partial dependencies. Do not fabricate recommendations when a required module is unavailable.
- Do not catch broad exceptions merely to return an empty array, empty object, default score, or normal status.
- Convert known domain failures to stable typed API errors at the HTTP boundary.
- Include enough context in internal structured logs to diagnose a failure without including PHI, secrets, tokens, or raw clinical payloads.
- Preserve the original exception as an internal cause where the language supports it.

## Configuration and Deployment

- Supply configuration through validated environment variables or approved read-only mounted configuration files.
- Do not hardcode deployment URLs, credentials, salts, secrets, database paths, or production feature flags.
- Distinguish development, test, and production behavior explicitly.
- Make services reverse-proxy aware for scheme, host, client address, and base path without blindly trusting forwarded headers from arbitrary sources.
- Expose only the gateway through the public container interface unless an approved deployment design states otherwise.
- Keep internal module ports configurable and non-public by default.
- Use Nginx or the approved gateway for TLS termination and routing.
- Systemd MAY manage the unified container, but MUST NOT erase module process or health boundaries inside it.
- Pin image dependencies, run as non-root, use minimal runtime images, and define persistent volumes explicitly.
- Do not bake runtime databases, PHI, secrets, mutable model registries, or local test artifacts into the image.
- Validate migrations before accepting traffic.
- Document volume mapping, backup, restore, upgrade, downgrade, and rollback procedures.

## Logging, Monitoring, and Audit

- Use structured logs with timestamp, service, environment, severity, request identifier, and safe event code.
- Propagate request and correlation identifiers across module calls.
- Do not log complete request or response bodies for clinical endpoints by default.
- Redact PHI and credentials centrally before emission.
- Keep security audit records append-only and attributable where required.
- Record authentication events, authorization failures, administrative changes, session revocation, and protected mutations without storing secrets.
- Record clinical provenance in its domain record rather than attempting to reconstruct it from application logs.
- Expose health and operational metrics without patient-level labels or high-cardinality PHI.
- Alert on repeated model-validation failures, database corruption, migration failure, authentication degradation, and persistent dependency failure.

## Testing

- Every nontrivial logic change MUST include at least one runnable verification.
- Unit-test pure clinical evaluators, normalization, validation, safety rules, and state transitions independently of HTTP and storage.
- Contract-test every module API against its canonical schema.
- Use consumer-driven contract tests for cross-module integrations.
- Integration-test each module with its real repository implementation and migration path.
- Run end-to-end tests through the gateway without direct database access.
- Test authentication revocation, role changes, CSRF rejection, ownership checks, session expiry, and disabled users.
- Test stale concurrent edits and verify the contract-defined precondition failure.
- Test idempotent retries and key-reuse conflicts.
- Test missing, stale, conflicting, ambiguous, and unresolved clinical inputs; expected behavior is explicit uncertainty, not guessed success.
- Test server recomputation of client-submitted scores and rejection of mismatches.
- Test DDI ambiguous and unknown medication paths and make incomplete coverage visible.
- Test model XSD validation and semantic validation separately.
- Include model fixtures for dimension mismatches, invalid row sums, unknown references, empty chance CPTs, compact broadcast rows, and parent-order regressions.
- Regression-test model and knowledge-base upgrades while retaining prior result provenance.
- Test backup and restore against representative module data.
- Test accessibility: keyboard navigation, focus visibility, semantic tables, labels, status communication without color, contrast, and reduced motion.
- Test graceful dependency failures and verify no false recommendation is produced.
- Keep tests deterministic. Do not depend on live third-party clinical services unless the test is explicitly an isolated integration test with controlled credentials and data.
- Remove temporary databases, generated files, and seeded records after tests.

## File Organization

The supplied archive does not establish one universal source tree for all modules. Use the following responsibility-based layout as a standard while preserving a module's existing documented structure:

- `modules/<module-name>/` — one independently runnable INSIGHT module; no implementation imports from another module.
- `modules/<module-name>/api/` — routers, request and response schemas, dependencies, and HTTP error mapping.
- `modules/<module-name>/domain/` — framework-independent entities, value objects, state transitions, and pure clinical rules owned by the module.
- `modules/<module-name>/services/` — application orchestration and use cases.
- `modules/<module-name>/repositories/` — repository protocols and persistence implementations owned by the module.
- `modules/<module-name>/integrations/` — versioned REST clients and adapters for other modules or approved external systems.
- `modules/<module-name>/migrations/` — ordered module-owned schema migrations.
- `modules/<module-name>/frontend/` — the module's bounded vanilla or React frontend, assets, and frontend tests.
- `modules/<module-name>/tests/` — unit, contract, integration, security, and module-level acceptance tests.
- `contracts/` — canonical versioned cross-module schemas and compatibility artifacts; no implementation logic.
- `models/bayesian/` — approved model source artifacts, schemas, registries, validation fixtures, hashes, and provenance metadata.
- `knowledge/ddi/` — DDI source data, schemas, review state, validation fixtures, and reproducible build metadata.
- `design/` — shared design tokens, accessibility guidance, and reusable visual assets.
- `docs/architecture/` — context maps, ADRs, ownership decisions, threat models, and deployment architecture.
- `docs/clinical/` — clinician-reviewed rationale, validation status, limitations, and release evidence; not executable source of truth unless a contract explicitly says so.
- `deploy/` — Docker, gateway, process supervision, health wiring, persistent-volume definitions, and deployment documentation.
- `scripts/` — reproducible development, validation, migration, backup, and build utilities; scripts must not contain embedded credentials or PHI.

### File-Placement Rules

- Put code in the owning module, not in a cross-module utility package that creates hidden coupling.
- Shared code is permitted only for non-domain infrastructure with a stable, versioned contract and a demonstrated need.
- Do not place clinical rules in frontend assets, route handlers, migration files, or deployment scripts.
- Do not place persistence queries in domain entities or HTTP routers.
- Do not place environment-specific values in source-controlled code.
- Keep generated files separate from hand-authored sources and make regeneration reproducible.
- Mark generated diagrams and reports clearly; do not edit them as canonical sources.
- Keep model files, schemas, validation evidence, and activation metadata together so an activated artifact can be audited.
- Keep local runtime databases, uploads, caches, logs, compiled assets, and temporary files outside source directories and excluded from version control.
