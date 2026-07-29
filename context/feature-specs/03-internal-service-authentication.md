# INSIGHT application

## 🎯 Destination and planning rules

Destination: deliver the INSIGHT psychiatrist-facing schizophrenia clinical decision-support application defined in `context/project-overview.md`, while preserving module independence, REST-only integration, canonical UUID identity, explicit uncertainty, psychiatrist authority, immutable final plans, PHI controls, and fail-closed clinical/model release gates.

This plan is not a clinical-release claim. Treatment Plan governance currently says `BLOCKED FOR CLINICAL RELEASE`, all eight decision gates are unresolved, accountable owners are unnamed, clinical validation has not been executed, and no approvals are recorded.

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
- `HITL`: requires an attributable human decision, review, approval, or source handoff. An agent must not supply the human side.
- `Conditional`: enters the active roadmap only if an approved scope decision includes that capability or model.

No issue may invent clinical data, probabilities, utilities, terminology mappings, approvals, stakeholder identities, patient fixtures, or source citations.

## 📋 Phase 0 — baseline and binding decisions

### INS-003 — Define internal service authentication and attribution

- **Type / owner:** HITL / security architecture
- **Blocked by:** INS-001
- **Build:** Version the contract for user-attributed internal REST calls and non-browser/background calls. Define allowed cookie forwarding, service identity, CSRF boundary, request/correlation/causation propagation, SSRF allowlists, revocation behavior, and audit separation.
- **Acceptance:** No module decodes Authentication JWTs or trusts request-body identity; background calls cannot impersonate a psychiatrist; finalization remains bound to a current user session; secrets and PHI are excluded from headers/logs.
- **Tests:** Contract examples for browser, server-to-server, revoked session, disabled account, role change, background job, and untrusted destination.