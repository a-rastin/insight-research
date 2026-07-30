# INSIGHT capability completion packets

Each heading below defines one bounded implementation or verification session
for capabilities referenced by `contracts/capability-matrix-v1.json`. Contract
packets INS-013 through INS-020 are predecessors; completing a contract packet
does not complete its corresponding runtime capability.

### INS-011 - Name accountable owners and complete regulatory evidence workflow

- **Type / owner:** HITL / product, clinical safety, privacy, security, quality
- **Blocked by:** INS-008, INS-009, INS-010
- **Build:** Record named accountable owners, the regulatory assessment, the canonical scope and capability-matrix hashes, evidence references, and the signature workflow. Keep protected minutes and signatures outside source control.
- **Acceptance:** Required roles are named; approvals bind exact versioned content; changed signed content requires a new approval; missing approval remains an explicit controlled-clinical release blocker.
- **Tests:** Release-gate fixtures for incomplete and structurally complete synthetic records; hash and signature-reference binding checks.

### INS-067 - Implement and roll out the Authentication v2 trust contract

- **Type / owner:** AFK / Authentication and session-contract consumers
- **Contract predecessor:** INS-013
- **Blocked by:** INS-003, INS-012, INS-013
- **Build:** Harden the Authentication-owned v2 session runtime and migrate one bounded consumer adapter set to validate its UUID identity, lowercase roles, UTC expiry, password/disclaimer gates, and immediate server-side revocation. Keep v1 as a documented compatibility adapter only.
- **Acceptance:** Consumers authorize without JWT decoding or message parsing; disabled, revoked, expired, reset, or role-changed sessions fail immediately; cookie, CSRF, rate-limit, and production-secret controls remain enforced.
- **Tests:** Authentication provider schema tests; consumer contract tests; expiry, revocation, disablement, role, disclaimer, password, CSRF, rate-limit, and v1 deprecation cases.

### INS-068 - Implement the role-scoped Dashboard workspace

- **Type / owner:** AFK / Dashboard
- **Blocked by:** INS-002, INS-012, INS-067
- **Build:** Replace placeholder navigation with gateway-relative module discovery for one administrator and one psychiatrist workspace slice, showing available, unavailable, and unauthorized modules without copying downstream domain data.
- **Acceptance:** Destinations reflect the current Authentication session and provider readiness; Dashboard remains navigation-only; no localhost URL, patient alias, or production mock identity reaches browser navigation.
- **Tests:** Discovery and Authentication consumer contracts; role, unavailable, unsupported-version, revocation, keyboard, focus, and no-PHI navigation cases.

### INS-069 - Implement Patient and Encounter v2 persistence and APIs

- **Type / owner:** AFK / Add New Patient
- **Contract predecessor:** INS-014
- **Blocked by:** INS-013, INS-014
- **Build:** Add the ordered migration and repository/API slice for atomic Patient plus first Encounter creation, UUID reads and lookup, ETags, idempotency, provenance, and explicit legacy intake mapping.
- **Acceptance:** Patient and Encounter UUIDs are independent and immutable; patient codes remain aliases and never integration keys; collisions and unmappable legacy records fail closed.
- **Tests:** Fresh/upgrade migration, transaction rollback, alias collision, UUID, pagination, ETag, idempotency, auth/CSRF, and contract tests.

### INS-070 - Implement encounter-scoped Diagnosis v2 assessments

- **Type / owner:** AFK / Diagnosis
- **Contract predecessor:** INS-015
- **Blocked by:** INS-015, INS-069
- **Build:** Migrate one assessment slice to Patient, Encounter, and Assessment UUIDs with one server evaluator, explicit psychiatrist confirmation or bypass, versioned audit snapshots, ETags, and idempotency.
- **Acceptance:** Computed criteria remain evidence and never become the clinician decision; unresolved legacy identity is quarantined; no patient alias appears in v2 URLs.
- **Tests:** Migration/quarantine, criteria-authority, confirm/bypass, stale write, idempotency, auth/CSRF, audit ordering, contract, and legacy-adapter equivalence cases.

### INS-071 - Implement server-authoritative PANSS v2 assessments

- **Type / owner:** AFK / Severity
- **Contract predecessor:** INS-016
- **Blocked by:** INS-016, INS-069
- **Build:** Persist one complete PANSS v2 assessment lifecycle with exact 30-item server scoring, explicit incomplete, passed, and completed states, canonical UUIDs, ETags, idempotency, and provenance.
- **Acceptance:** Client totals cannot override server results; missing or passed items never become zero or normal; corrupt or unmapped legacy data remains visible and quarantined.
- **Tests:** Score vectors and item boundaries; missing/duplicate/unknown items; mismatch, pass, migration, ETag, idempotency, auth/CSRF, and contract cases.

### INS-072 - Implement Medical History v2 persistence and retrieval

- **Type / owner:** AFK / Medical History
- **Contract predecessor:** INS-017
- **Blocked by:** INS-009, INS-017, INS-069
- **Build:** Add one database-backed assessment create/read/latest slice preserving controlled validation, canonical UUIDs, explicit unknown states, distinct medication instances and original text, ETags, idempotency, and provenance.
- **Acceptance:** UI defaults do not become clinical facts; unresolved medication identity remains explicit; JSON corruption or an unmappable legacy alias cannot silently create an empty or linked record.
- **Tests:** Fresh/import/corrupt/quarantine migration, conditional validation, unknown states, duplicate medications, ETag, idempotency, auth/CSRF, and contract cases.

### INS-073 - Implement the approved structured suicide-risk slice

- **Type / owner:** Conditional HITL + AFK / Suicide Risk owner
- **Blocked by:** INS-004, INS-008, INS-012, INS-014, approved source and licensing handoff
- **Build:** Publish and implement only the approved minimum encounter-scoped assessment, storage, retrieval, and UI slice, including explicit unknown and unavailable states and source-backed urgent behavior.
- **Acceptance:** No question, score, threshold, or emergency instruction is invented; psychiatrist assertion remains explicit; absent required risk blocks dependent processing.
- **Tests:** Approved source-to-field traceability and golden cases; unknown, unavailable, conflicting, urgent, auth/CSRF, ETag, idempotency, accessibility, and no-PHI cases.

### INS-074 - Implement the server-owned DDI v1 service

- **Type / owner:** AFK / DDI
- **Contract predecessor:** INS-018
- **Blocked by:** INS-009, INS-018, INS-072
- **Build:** Put one medication-resolution and pairwise-check slice behind authenticated REST APIs and module-owned persistence, using immutable approved knowledge identity, complete pair coverage, typed unresolved states, and attributable override records.
- **Acceptance:** Ambiguous or unknown medication instances never yield definitive no-interaction output; only an approved active knowledge revision generates findings; retries are deterministic and browser storage is not authoritative.
- **Tests:** Provider schema, migration, duplicate-instance, pair coverage, ambiguous/unknown, inactive knowledge, idempotency, override rationale, auth/role/CSRF, and restart cases.

### INS-075 - Implement governed BN registry evaluation

- **Type / owner:** AFK / BN Manager
- **Contract predecessor:** INS-019
- **Blocked by:** INS-007, INS-009, INS-019
- **Build:** Implement one registry-only discovery and evaluation slice preserving stable model/version/hash identity, lifecycle and clinical-use gates, accepted and ignored evidence, warnings, posterior, evaluation UUID/time, and idempotency.
- **Acceptance:** Caller paths or model text cannot enter clinical evaluation; structural validity never implies clinical approval; blocked or placeholder models fail explicitly; prior evaluations retain exact provenance.
- **Tests:** Registry provider schema, four-model discovery, blocked clinical use, unknown evidence, invalid target/posterior, hash stability, arbitrary-path rejection, auth/role/CSRF, and idempotency cases.

### INS-076 - Implement the Treatment Plan orchestration lifecycle

- **Type / owner:** AFK / Treatment Plan
- **Contract predecessor:** INS-020
- **Blocked by:** INS-010, INS-020, INS-067, INS-069 through INS-075
- **Build:** Implement one backend lifecycle from immutable input snapshot and idempotent recommendation run through explainable Primary Plan, append-only edits, server safety/DDI revalidation, immutable finalization, and provenance using published provider contracts.
- **Acceptance:** Missing, stale, conflicting, unresolved, blocked, or unavailable inputs cannot appear complete; safety gates outrank Bayesian results; finalization is attributable, idempotent, and immutable.
- **Tests:** Provider/consumer contracts; complete and uncertainty scenarios; retry conflict, stale edit, revalidation, revocation, immutable finalization, provenance, and restart cases.

### INS-077 - Connect the psychiatrist Treatment Plan review workspace

- **Type / owner:** AFK / Treatment Plan UI
- **Blocked by:** INS-076
- **Build:** Replace synthetic review data for one end-to-end plan with authenticated API loading, original-versus-edit diff, evidence and limitation display, structured edits, safety refresh, attestation, and immutable final receipt.
- **Acceptance:** Recommendations remain advisory; original content and attributable changes stay visible; stale or failed writes never appear successful; hard blockers explain why finalization is unavailable.
- **Tests:** UI contract and real-backend flow; loading/partial/error, 401/403/412/428/5xx, diff, rationale, recheck, duplicate finalization, keyboard, focus, semantics, and no-PHI cases.

### INS-078 - Implement follow-up delta and plan supersession

- **Type / owner:** AFK / Add New Patient and Treatment Plan
- **Blocked by:** INS-004, INS-069, INS-076, INS-077
- **Build:** Implement one follow-up Encounter and Delta capture/retrieval slice and use it to create a successor recommendation and final plan linked to, but never modifying, the prior final plan.
- **Acceptance:** Changed, unchanged, unknown, not-assessed, and unavailable states remain explicit; no encounter is inferred from date or patient code; prior records remain immutable and readable.
- **Tests:** Initial/no-prior, no-change, changed medication/risk, missing data, mismatch, ETag, idempotency, supersession, history immutability, restart, and browser cases.

### INS-079 - Build the boundary-preserving unified deployment

- **Type / owner:** AFK / deployment
- **Blocked by:** INS-002, INS-067 through INS-076
- **Build:** Package the application from `/root/research/insight-research` as independently configured module processes behind one gateway, with internal-only ports, separate data directories, migration gates, readiness aggregation, TLS-edge configuration, and graceful shutdown.
- **Acceptance:** The required repository path is the build context; only the gateway is public; modules retain process, persistence, configuration, and health boundaries; a required-module failure makes readiness fail safely.
- **Tests:** Runtime-policy and image checks; process/port/data isolation, route smoke, migration failure, restart, SIGTERM, non-root, relative-browser-URL, Docker Desktop, and Ubuntu deployment cases.

### INS-080 - Implement protected administration and operations workflows

- **Type / owner:** AFK / Authentication, Dashboard, module owners, operations
- **Blocked by:** INS-005, INS-067, INS-068, INS-074, INS-075, INS-079
- **Build:** Connect one role-scoped administration workspace to owner APIs for account lifecycle, redacted audit/operational views, governed knowledge/model navigation, and module-aware backup and restore verification without transferring domain ownership.
- **Acceptance:** Dashboard stores no copied accounts, logs, knowledge, models, or clinical data; partial operations never report success; secrets, PHI, raw protected evidence, and internal paths are excluded.
- **Tests:** Provider/consumer, admin-versus-psychiatrist, revocation, CSRF, redaction, pagination, backup/restore integrity, partial failure, cross-module access prohibition, accessibility, and no-sensitive-data cases.

### INS-081 - Verify full capability and release-mode acceptance

- **Type / owner:** AFK + HITL / quality, product, clinical, security, privacy, operations
- **Blocked by:** INS-011, INS-066 through INS-080
- **Build:** Reconcile every applicable matrix row against one pinned clean installation, recording committed implementation, live contract, migration, automated proof, owner acceptance, limitations, rollback path, and exact build/policy/model/knowledge/matrix hashes.
- **Acceptance:** No required capability is placeholder, synthetic-only, or supported only by documentation; standalone, initial, follow-up, administration, failure, restore, and accessibility journeys pass for the claimed mode; controlled-clinical release remains blocked without INS-011 approvals.
- **Tests:** Matrix verifier; clean/restored install; all module and contract suites; gateway E2E, identity, failure/chaos, security/privacy, accessibility, backup/rollback, and no-placeholder scans.

### INS-082 - Implement an approved read-only assistant slice

- **Type / owner:** Conditional AFK / assistant owner
- **Blocked by:** INS-006, INS-077, superseding approved assistant policy
- **Build:** For one approved page only, implement server-side allowlisted context projection, structural identifier omission, defense-in-depth scrubbing, advisory provider response, bounded UI, access/retention controls, and a disabled/provider-failure state.
- **Acceptance:** No mutation, approval, signing, or finalization tool exists; patient identifiers never reach the provider fixture; output is visibly advisory; disabled or failed assistant behavior cannot block clinical work.
- **Tests:** Redaction corpus, allowlist snapshot, captured provider request, role/retention/deletion, prompt-injection/tool-absence, advisory labeling, accessibility, and disabled/failure cases.
