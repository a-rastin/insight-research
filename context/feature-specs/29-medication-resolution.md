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

### INS-029 — Connect Medical History UI and medication-resolution feedback

- **Type / owner:** AFK / Medical History
- **Blocked by:** INS-017, INS-022, INS-028
- **Build:** Embed UI with host UUID context; preserve original medication instances and any server-supplied typed identity status without silently selecting candidates; remove activation-code navigation. Live DDI resolution remains owned by INS-031.
- **Acceptance:** Unresolved medication identity remains visible for later DDI review; form defaults are labeled as unanswered until submitted; failed save remains visible; no PHI enters URL/storage/logs.
- **Tests:** Conditional UI suite; duplicate and unresolved medication rows; no-PHI scan; auth/CSRF HTTP integration; keyboard/focus/error tests.