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

## 🧩 Phase 2 — owning-module vertical slices

### INS-021 — Implement Patient and Encounter v2 persistence and APIs

- **Type / owner:**AFK / Add New Patient
- **Blocked by:** INS-013, INS-014
- **Build:** Add ordered migration and repository methods for Encounter; expose authenticated v2 create/read/list/search routes; add idempotency, ETag, problem details, request IDs, and compatibility mapping from existing intakes. Keep legacy intake routes as thin adapters only.
- **Acceptance:** Fresh and upgraded DBs preserve patients/intakes; atomic patient-plus-encounter create returns canonical UUIDs; no patient alias appears in new URLs or logs; Treatment Plan can fetch versioned encounter-bound records.
- **Tests:** Full module suite plus fresh/upgrade migration, transaction rollback, collision, pagination, idempotency, ETag, auth/CSRF, contract, and legacy adapter equivalence.