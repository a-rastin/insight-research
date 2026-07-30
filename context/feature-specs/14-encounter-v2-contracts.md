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

### INS-014 — Publish Patient and Encounter v2 contracts

- **Type / owner:** AFK / Add New Patient
- **Blocked by:** INS-004, INS-012, INS-013
- **Build:** Define Patient, patient-code alias, Encounter, and intake snapshot resources with UUIDs, schema/resource versions, provenance, list/search pagination, idempotent creates, ETags, and exact lookup semantics. Define mapping from existing `intakeId` rows without inferring encounters from dates.
- **Acceptance:** `patientCode` is never a foreign key or integration URL key; Patient and Encounter have independent immutable UUIDs; patient plus first encounter creation is atomic; collisions fail closed.
- **Tests:** JSON Schema/OpenAPI; migration fixtures; alias collision; invalid UUID; changed idempotency payload; stale ETag; pagination; UTC validation.