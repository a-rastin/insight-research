# INSIGHT application

## 🎯 Destination and planning rules

Destination: deliver the INSIGHT psychiatrist-facing schizophrenia clinical decision-support application defined in `context/project-overview.md`, while preserving module independence, REST-only integration, canonical UUID identity, explicit uncertainty, psychiatrist authority, immutable final plans and PHI controls.

Every issue below is one work packet for one implementation session. Each packet must:

- start with `git status --short` in the affected nested repository and preserve pre-existing changes;
- read the named module contract, adapter, schema, handoff, and focused tests;
- update the authoritative contract before changing a public interface;
- implement one bounded vertical slice, including migrations, API/domain behavior, UI behavior when applicable, and tests;
- run focused tests, the owning module's full suite, and affected provider/consumer contract tests;
- update `context/progress-tracker.md` with commands, results, remaining risks, and next work;
- create one informative commit in each affected nested repository;
- avoid editing protected clinical sources, model files, applied migrations, runtime data, or generated `graphify-out/` artifacts by hand.

Issue types:

- `AFK`: implementable without a live product or clinical decision.

## 🌐 Phase 1 — versioned contracts and canonical identity

### INS-012 — Publish the common internal REST profile

- **Type / owner:** AFK / architecture
- **Blocked by:** INS-002, INS-003
- **Build:** Create canonical versioned schemas for problem details, health, readiness, contract discovery, UUIDs, UTC timestamps, `X-Schema-Version`, `X-Request-ID`, correlation/causation IDs, ETags, `If-Match`, and idempotency behavior. Define compatibility and deprecation rules.
- **Acceptance:** Every module can copy/package the artifacts unchanged; unsupported majors fail explicitly; errors exclude paths, stack traces, secrets, and PHI.
- **Tests:** Schema examples; OpenAPI lint; provider/consumer compatibility; invalid UUID/time/header/error fixtures.