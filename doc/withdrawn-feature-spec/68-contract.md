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

## 🧩 Phase 2 — owning-module vertical slices

### INS-068 — Publish the Follow-up Delta and longitudinal-history contract

- **Build:** Define a versioned Follow-up Delta resource and retrieval contract tied to a new Encounter, prior Encounter, and prior Final Plan. Include actor, status, timestamps, resource version, source references, and explicit changed, unchanged, unknown, not-assessed, and unavailable states only where approved sources define the fields. Define patient history projection without transferring ownership of upstream records.
- 
