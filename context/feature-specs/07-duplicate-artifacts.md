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

## 📋 Phase 0 — baseline and binding decisions

### INS-007 — Resolve model-source ownership and duplicate artifacts

- **Type / owner:** BN owner and clinical model owner
- **Blocked by:** INS-001
- **Build:** Create a model manifest mapping every `BNs/` topic, model-only `Modules/` copy, and BN Manager registry file to source status, canonical owner, format, hash, approval state, and allowed runtime use. Record exact-copy hashes already observed; decide how derivative copies are regenerated or retired.
- **Acceptance:** One runtime owner exists; `.net` and non-registry XML assets remain non-runtime unless admitted through governance; protected source/model files are not modified in this packet.
- **Tests:** Manifest schema; hash reconciliation.