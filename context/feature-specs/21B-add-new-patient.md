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

# INS-022 — Connect Add New Patient UI to Encounter v2

- **Type / owner:** AFK / Add New Patient
- **Blocked by:** INS-021
- **Build:** Use gateway-relative v2 APIs and host-supplied context; implement the documented intake steps without duplicating diagnosis/severity logic; remove alias-bearing navigation; preserve form state and visible async failure.
- **Acceptance:** Psychiatrist creates Patient and first Encounter; downstream steps receive UUID context; embedded mode owns no host chrome/history; keyboard/error/focus behavior follows UI context.
- **Tests:** Frontend unit/DOM tests; real HTTP UI-to-backend test; no-PHI URL/storage assertion; keyboard/focus/accessibility smoke.