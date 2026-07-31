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

### INS-020 — Reconcile Treatment Plan OpenAPI with live routes

- **Type / owner:** AFK / Treatment Plan
- **Blocked by:** INS-012 through INS-019
- **Build:** Version the OpenAPI and schemas to reference real provider contracts and live security/idempotency/concurrency behavior. Remove undocumented route drift. Do not wire new behavior in this contract-only packet.
- **Acceptance:** Every live public route appears in OpenAPI; every OpenAPI operation has an implementation issue; response schemas match exact runtime envelopes; compatibility impact is documented.
- **Tests:** Existing TP-05 lint/compatibility checks plus live-router/OpenAPI parity and external-reference resolution.