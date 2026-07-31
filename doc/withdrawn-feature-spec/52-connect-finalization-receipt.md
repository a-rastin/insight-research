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

## 🩺 Phase 4 — Treatment Plan workflow completion

### INS-052 — Connect finalization UI and immutable plan receipt

- **Type / owner:** AFK / Treatment Plan
- **Blocked by:** INS-051
- **Build:** Add attestation, pre-finalization safety/DDI refresh, exact override rationale, idempotency, immutable final receipt, provenance view, and disabled-state explanations.
- **Acceptance:** Finalize cannot use stale preview/session/source; duplicate submit returns same final plan; finalized UI becomes read-only; hard non-overridable blockers remain blocked.
- **Tests:** Real browser/backend finalization; changed edit during recheck; revoked session; stale ETag; duplicate submit; override authorization/rationale; DB update/delete rejection.
