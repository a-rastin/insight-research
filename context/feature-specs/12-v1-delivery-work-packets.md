# INSIGHT v1 delivery work packets

These packets were exposed while freezing the INS-066 capability matrix. Each
packet is one implementation session and follows the planning rules in
`11-capability-matrix.md`. Clinical deployment remains blocked by the approved
research-only scope and named release gates.

## Phase 0 completion gate

### INS-011 - Define release modes, evidence, and accountable sign-off

- **Type / owner:** AFK / product, clinical, privacy, security, quality
- **Blocked by:** INS-004 through INS-010
- **Build:** Define research-build and controlled-clinical release modes, required evidence classes, named sign-off roles, and fail-closed behavior for absent approval.
- **Acceptance:** Technical completion is distinct from deployment authorization; absent approval cannot become approval; every capability-matrix row uses the same release vocabulary.
- **Tests:** Contract vocabulary, missing-approval, and mode-applicability checks.

## Module delivery packets

### INS-067 - Align Authentication session consumers

- **Type / owner:** AFK / Authentication, Dashboard, Add New Patient
- **Blocked by:** INS-003
- **Build:** Version one Authentication session response and align the two consumer adapters without decoding JWTs.
- **Acceptance:** Revoked, disabled, wrong-role, disclaimer-blocked, and password-change-gated sessions fail closed through real REST calls.
- **Tests:** Provider contract plus both consumer contract suites.

### INS-068 - Connect Dashboard module discovery

- **Type / owner:** AFK / Dashboard
- **Blocked by:** INS-002, INS-067
- **Build:** Replace synthetic availability with configured gateway-relative module discovery and typed unavailable states.
- **Acceptance:** Dashboard remains navigation-only and never hides a failed required module.
- **Tests:** Dashboard focused and full suites; gateway route contract checks.

### INS-069 - Version Patient and Encounter APIs

- **Type / owner:** AFK / Add New Patient
- **Blocked by:** INS-004, INS-067
- **Build:** Publish and implement versioned Patient, Encounter, intake, alias-resolution, and Follow-up Delta contracts over module-owned persistence.
- **Acceptance:** Canonical UUIDs are authoritative; patient codes remain aliases; writes are authenticated, CSRF-protected, idempotent, and concurrency-safe where mutable.
- **Tests:** Migration, API, identity-collision, auth, CSRF, and contract tests.

### INS-070 - Version clinician-controlled Diagnosis

- **Type / owner:** AFK / Diagnosis
- **Blocked by:** INS-067, INS-069
- **Build:** Move Diagnosis to Patient and Encounter UUID contracts while preserving separate computed criteria and psychiatrist decision state.
- **Acceptance:** Server evaluates criteria; no result auto-confirms diagnosis; history and bypass remain attributable.
- **Tests:** Migration, criteria, authority, auth, CSRF, concurrency, and contract tests.

### INS-071 - Make PANSS server-authoritative

- **Type / owner:** AFK / Severity
- **Blocked by:** INS-067, INS-069
- **Build:** Add versioned UUID-based PANSS API and module-owned database persistence with server recomputation of all 30 items and totals.
- **Acceptance:** Client totals are never authoritative; incomplete or invalid items remain explicit; browser PHI storage is removed.
- **Tests:** Migration, scoring, mismatch, auth, CSRF, concurrency, and contract tests.

### INS-072 - Version Medical History persistence

- **Type / owner:** AFK / Medical History
- **Blocked by:** INS-067, INS-069, INS-009
- **Build:** Replace JSON persistence with a versioned UUID-based API and module-owned database for history, medications, prior response, adherence, contraindications, and risk factors.
- **Acceptance:** Original and normalized medication values remain distinct; missing and conflicting facts remain explicit.
- **Tests:** Migration, validation, auth, CSRF, concurrency, and contract tests.

### INS-073 - Implement approved suicide-risk seam

- **Type / owner:** conditional / Suicide Risk, clinical, licensing
- **Blocked by:** INS-004 and approved C-SSRS source/licensing contract
- **Build:** Create the independently runnable owner API only after approved instrument content and scoring rules exist.
- **Acceptance:** Until approval, risk is `unknown` or `unavailable` and risk-dependent processing fails closed.
- **Tests:** Instrument-license gate, schema, scoring, auth, CSRF, and contract tests.

### INS-074 - Serve governed DDI checks

- **Type / owner:** AFK / DDI
- **Blocked by:** INS-009, INS-067
- **Build:** Add protected REST APIs for medication resolution, complete pair checking, immutable knowledge revisions, review, activation, rollback, and attributable overrides.
- **Acceptance:** Unknown or ambiguous identities never produce complete coverage; browser authority and PHI storage are removed.
- **Tests:** Ingestion, activation, resolution, pair coverage, auth, CSRF, persistence, and contract tests.

### INS-075 - Enforce BN registry governance

- **Type / owner:** AFK / BN Manager
- **Blocked by:** INS-007, INS-009
- **Build:** Bind evaluation to approved registry IDs and return exact model version, hash, evidence disposition, warnings, posterior, and evaluation identity.
- **Acceptance:** Unapproved, placeholder, incompatible, or caller-path models fail closed without modifying protected artifacts.
- **Tests:** Registry, XSD, semantic, provenance, auth, and contract tests.

### INS-076 - Connect Treatment Plan orchestration

- **Type / owner:** AFK / Treatment Plan
- **Blocked by:** INS-008 through INS-010, INS-067, INS-069 through INS-075
- **Build:** Connect owner REST adapters to immutable snapshots, idempotent recommendation runs, safety-first draft generation, edit ledger, revalidation, immutable finalization, and supersession.
- **Acceptance:** Dependency and uncertainty states are explicit; deterministic gates outrank models; psychiatrist actions remain attributable.
- **Tests:** Focused domain, repository, migration, provider/consumer, failure-mode, concurrency, idempotency, and full backend suites.

### INS-077 - Connect Treatment Plan review UI

- **Type / owner:** AFK / Treatment Plan
- **Blocked by:** INS-076
- **Build:** Replace synthetic review data with gateway-relative backend routes for evidence, edits, safety rechecks, finalization, and supersession history.
- **Acceptance:** Original recommendation and clinician diff remain visible; no client-computed safety result is authoritative; accessibility contract passes.
- **Tests:** Frontend unit, API integration, keyboard, focus, semantic, contrast, and reduced-motion checks.

### INS-078 - Complete follow-up orchestration

- **Type / owner:** AFK / Add New Patient, assessment owners, Treatment Plan
- **Blocked by:** INS-069 through INS-077
- **Build:** Orchestrate a new Encounter and Follow-up Delta, encounter-scoped reassessments, comparison, and prospective plan supersession through REST only.
- **Acceptance:** Prior assessments and Final Plans remain immutable; each owner remains sole writer.
- **Tests:** Cross-module contract and integrated initial-to-follow-up scenario.

## Platform and release packets

### INS-079 - Build unified private-module runtime

- **Type / owner:** AFK / deployment
- **Blocked by:** INS-002 and runnable module packets
- **Build:** Implement the selected nginx, supervisord, non-root, loopback-port, separate-data-directory, graceful-shutdown, and readiness policy.
- **Acceptance:** Only gateway is public; every module remains independently runnable and health-addressable.
- **Tests:** Image build, startup, liveness/readiness, shutdown, restart, Docker Desktop, and Ubuntu checks.

### INS-080 - Implement governed operations

- **Type / owner:** AFK / operations, owning modules
- **Blocked by:** INS-005, INS-079
- **Build:** Add owner-local backup, restore verification, retention, migration, and PHI-safe aggregate metadata orchestration.
- **Acceptance:** Restore never cross-writes; protected immutable records are retained; secrets and PHI stay out of artifacts and logs.
- **Tests:** Backup/restore, migration, retention, authorization, isolation, and rollback checks.

### INS-081 - Verify integrated v1 release evidence

- **Type / owner:** AFK / quality, security, clinical governance
- **Blocked by:** INS-011, INS-067 through INS-080
- **Build:** Run capability-matrix-driven contract, integration, security, privacy, accessibility, clinical-safety, recovery, and deployment verification.
- **Acceptance:** Every required row has passing evidence; conditional rows show satisfied gates or explicit unavailability; controlled-clinical release remains blocked without named approvals.
- **Tests:** Matrix completeness and full release suite through gateway.

### INS-082 - Reconsider assistant scope

- **Type / owner:** conditional / privacy, security, product
- **Blocked by:** Superseding approved assistant policy
- **Build:** Enable provider, scrubbed page context, retention, and read-only tools only if a later approved policy replaces the v1 disabled decision.
- **Acceptance:** No identifiers reach provider; no tool mutates clinical data; assistant failure cannot block clinical workflow.
- **Tests:** Identifier omission, scrubber, provider, retention, authorization, mutation absence, and disabled-state tests.
