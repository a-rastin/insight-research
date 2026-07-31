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

### INS-070 — Add attributable clinician medication-resolution review

- **Type / owner:** AFK / DDI with Medical History consumer
- **Blocked by:** INS-009, INS-018, INS-029, INS-031, INS-032
- **Build:** Add protected candidate-resolution and confirmation APIs plus a focused review UI for ambiguous and unknown medication instances. Preserve original text and instance details, show source and confidence metadata, require explicit clinician selection or unresolved status, record actor/time/terminology version, and trigger a new DDI check after any resolution change.
- **Acceptance:** No candidate is auto-selected; duplicate medication instances remain distinct; unresolved items cannot produce definitive pair coverage or no-interaction language; resolution history is append-only and attributable; stale terminology or changed candidates require review again.
- **Tests:** Exact, ambiguous, unknown, duplicate, stale-candidate, changed-selection, concurrent-review, auth/role/CSRF/idempotency, DDI recheck, browser accessibility, and no-PHI tests.
