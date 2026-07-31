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

### INS-030 — Implement the approved structured suicide-risk module

- **Type / owner:** AFK 
- **Blocked by:** INS-004, INS-008, approved source/licensing handoff, INS-012 through INS-014
- **Build:** Implement one source-backed assess-and-retrieve slice: publish its assessment contract, scaffold independent service/storage/UI, and implement only the approved minimum scoring/interpretation needed by that slice. Additional clinical rules require new issues.
- **Acceptance:** No question, score, threshold, or emergency instruction is invented; psychiatrist assertion remains explicit; urgent behavior follows INS-010; Treatment Plan can consume a versioned encounter snapshot.
- **Tests:** Source-to-field traceability; scoring golden cases supplied/approved by owner; missing/conflicting/urgent states; auth/CSRF/ETag/idempotency; accessibility and no-PHI tests.