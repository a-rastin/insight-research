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

### INS-002 — Decide gateway, process supervision, ports, and runtime matrix

- **Type / owner:** HITL / architecture and operations
- **Blocked by:** INS-001
- **Build:** Write an ADR selecting the internal gateway/router, in-container process supervisor, module port/base-path map, compatible Python and Node runtime matrix, health aggregation policy, and shutdown behavior. Preserve one process and one data directory per module.
- **Acceptance:** Decision names alternatives and trade-offs; only gateway is public; liveness/readiness remain per module; browser routes are relative; Windows Docker Desktop and Ubuntu VPS paths are covered.
- **Tests:** ADR schema/link check; static deployment-policy test rejects public module ports, duplicate ports, root execution, and missing health entries.