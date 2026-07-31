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

## 📦 Phase 5 — unified integration, operations, and release

### INS-060 — Implement module-aware backup, restore, migration, and rollback

- **Type / owner:** AFK / operations
- **Blocked by:** INS-005, INS-056
- **Build:** Add per-module consistent backup commands, aggregate versioned manifest, encryption/key-handling integration, restore into isolated paths, integrity/readiness validation, retention, and image rollback that never auto-down-migrates.
- 
- **Tests:** Representative synthetic backup/restore for every DB/registry; corruption/missing-module/wrong-version/wrong-key; restart and rollback rehearsal.
