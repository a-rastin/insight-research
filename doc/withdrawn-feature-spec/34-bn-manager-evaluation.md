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

## 🧠 Phase 3 — DDI and BN decision services

### INS-034 — Align Treatment Plan and BN Manager evaluation over real HTTP

- **Type / owner:** AFK / BN Manager and Treatment Plan
- **Blocked by:** INS-019, INS-033
- **Build:** Implement the selected evaluation endpoint and update Treatment Plan's `BnManagerHttpEvaluator`; forward allowed auth/request context; validate request/response schemas; preserve accepted/ignored evidence, warnings, version, hash, and evaluation UUID.
- **Acceptance:** No current `/evaluations` versus caller-specific route mismatch remains; unsupported model/evidence fails typed; Treatment Plan stores the exact canonical bundle.
- **Tests:** Provider contract; Treatment Plan consumer contract; real HTTP success/error/timeout; unknown evidence; response tamper/hash/version mismatch.