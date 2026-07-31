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

### INS-028 — Replace Medical History JSON with v2 repository and security

- **Type / owner:** AFK / Medical History
- **Blocked by:** INS-013, INS-017, INS-021
- **Build:** Add repository seam and ordered DB migrations/import; implement v2 create/read/latest routes, canonical IDs, ETag/idempotency, auth/CSRF, restricted CORS, readiness, versioned provenance, and explicit storage failure.
- **Acceptance:** Existing controlled-option and conditional validation remains authoritative; JSON corruption cannot erase visible state; old activation codes become compatibility aliases only; concurrent writes are protected.
- **Tests:** Existing suite plus fresh/import/corrupt/quarantine migration, repository, contract, auth/role/revocation/CSRF, ETag/idempotency, and readiness tests.