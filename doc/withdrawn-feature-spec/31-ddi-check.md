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

## 🧠 Phase 3 — DDI and BN decision services

### INS-031 — Build server-owned DDI clinical-check API

- **Build:** Wrap the existing deterministic engine in an independently runnable authenticated service; add module-owned repository/migrations for immutable KB revisions, checks, findings, resolution coverage, overrides, and audit/provenance.
- **Acceptance:** Exact medication instances and all intended pairs are checked; unresolved coverage is explicit; only one active approved KB is used per check; retries are idempotent; browser storage is not authoritative.
- **Tests:** Existing engine/ingest/validation suite plus repository, migration, REST contract, auth/CSRF/role, idempotency, pair coverage, unknown/ambiguous, and restart tests.
