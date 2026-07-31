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

### INS-032 — Move DDI review, activation, rollback, and audit behind admin APIs

- **Build:** Replace local revision writes with protected draft/review/activate/retire/rollback endpoints and UI; enforce reviewer attribution, source evidence, immutable revisions, conflict handling, and production activation gate.
- **Acceptance:** Zero-approved, low-confidence, unresolved-identity, conflicting-pair, or unlicensed revisions cannot activate; rollback creates an auditable active-state change; review failures never show success.
- **Tests:** Lifecycle state table; permission/CSRF; two-reviewer policy if approved; conflict/rebase; activation/rollback; storage-failure rollback; audit separation.