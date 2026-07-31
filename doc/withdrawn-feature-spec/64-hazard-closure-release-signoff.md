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

## 📦 Phase 5 — unified integration, operations, and release

### INS-064 — Close hazards and obtain independent release approvals

- **Type / owner:** HITL / required accountable roles
- **Blocked by:** INS-011, INS-063
- **Build:** Resolve or explicitly accept every hazard under the approved process; obtain distinct external human approvals bound to scope, validation report, build, policy, BN, and DDI hashes.
- **Acceptance:** Open critical/major hazards block release; approvers are distinct where required; protected signature evidence is referenced, not committed; any changed artifact invalidates approval.
- **Tests:** Release-gate script; approval/report/hash binding; changed-artifact negative case; independence rule.
