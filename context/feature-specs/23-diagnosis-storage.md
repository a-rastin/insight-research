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

### INS-023 — Migrate Diagnosis storage and routes to assessment UUIDs

- **Type / owner:** AFK / Diagnosis
- **Blocked by:** INS-015, INS-021
- **Build:** Add migration from code-keyed sessions to canonical references using an explicit resolver/quarantine path; implement v2 create/read/update/latest routes, ETags, idempotency, and versioned audit snapshots.
- **Acceptance:**  legacy routes delegate to one evaluator; stale writes return precondition failure; criteria and clinician decision remain distinct.
- **Tests:** Full Diagnosis suite plus migration/quarantine, v2 contract, authority, concurrency, auth/CSRF, request-ID, and legacy-equivalence tests.