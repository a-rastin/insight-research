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

### INS-010 — Resolve plan breadth, scheduling, emergency, and override gates

- **Type / owner:** psychiatrist, product
- **Blocked by:** INS-001
- **Build:** Resolve DG-04, DG-05, and DG-06: supported plan sections, appointment/availability/timezone ownership, emergency behavior, missing-data policy, contraindication/allergy/suicide-risk gates, high-severity DDI override policy, and non-pharmacological scope.
- **Acceptance:** Emergency behavior never implies an unimplemented emergency-services integration; hard and overridable blockers are distinct; required rationale and attribution are explicit; uncertainty behavior is testable.
- **Tests:** Scope-matrix validation; policy decision tables; emergency/missing/conflicting/high-DDI scenarios; finalization gate tests.