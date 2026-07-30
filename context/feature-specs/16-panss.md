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

### INS-016 — Publish PANSS Severity assessment v2 contract and scoring rules

- **Type / owner:** AFK / Severity
- **Blocked by:** INS-012, INS-013, INS-014
- **Build:** Define 30 item inputs, allowed scores, assessment status, explicit pass/skip semantics, server-derived subscales/total, scale/rule version, Patient/Encounter/Assessment UUIDs, ETag, idempotency, and provenance.
