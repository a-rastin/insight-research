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

## 🌐 Phase 1 — versioned contracts and canonical identity

### INS-015 — Publish Diagnosis assessment v2 contract

- **Type / owner:** AFK / Diagnosis
- **Blocked by:** INS-012, INS-013, INS-014
- **Build:** Define assessment UUID, Patient UUID, Encounter UUID, checked criteria, server evaluation, explicit clinician decision/bypass, rule/schema version, actor, status, timestamps, ETag, and audit/provenance representation. Keep legacy code routes as thin adapters only.
- **Acceptance:**  bypass remains explicit; no patient alias appears in new URLs; Treatment Plan can fetch a versioned encounter-bound snapshot.
- **Tests:** Contract/live-route parity; authority cases; stale write; idempotent init; unknown patient/encounter; audit ordering; legacy adapter equivalence.