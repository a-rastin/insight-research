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

## 🩺 Phase 4 — Treatment Plan workflow completion

### INS-072 — Bind approved eligibility, safety, and synthesis policy bundles

- **Type / owner:** Conditional HITL + AFK / Treatment Plan and Clinical Safety Officer
- **Blocked by:** INS-010, INS-011, INS-048, INS-049
- **Build:** Map approved policy decisions and controlled-source references into the existing Eligibility, SafetyPolicy, and synthesis seams. Version and hash each policy bundle, define compatibility between bundles, preserve rule-level provenance and precedence, and keep the research policy explicitly non-clinical when approvals are absent. Do not add medical rules from memory.
- **Acceptance:** Every executable deterministic rule traces to an approved source and scope decision; unknown or conflicting facts cannot satisfy a gate; urgent and hard-block rules outrank Bayesian output; unapproved or incompatible policy bundles block completion; old plans retain exact policy identities.
- **Tests:** Source-to-rule traceability; policy schema/hash/compatibility; missing, unknown, conflicting, urgent, allergy, contraindication, DDI, override, unsupported-scope, and changed-policy fixtures; independent clinical review record.


