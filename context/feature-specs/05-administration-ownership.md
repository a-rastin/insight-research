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

### INS-005 — Decide administration, logs, backup, and restore ownership

- **Type / owner:** HITL / architecture, security, operations
- **Blocked by:** INS-001
- **Build:** Define how Dashboard routes to account administration, security audit, clinical provenance, operational logs, per-module backup, aggregate backup manifests, restore verification, and retention. Do not move domain data into Dashboard.
- **Acceptance:** Authentication owns account/security-audit data; clinical provenance stays with owning clinical modules; backup artifacts name module/schema versions without exposing PHI in filenames; restore cannot cross-write another module's DB.
- **Tests:** Ownership/permission matrix; admin-versus-psychiatrist authorization tests; backup manifest schema and cross-module isolation tests.