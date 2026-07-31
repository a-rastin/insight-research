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

### INS-062 — Author the approved clinical-validation protocol and cases

- **Type / owner:** HITL / psychiatrist and Clinical Safety Officer
- **Blocked by:** INS-008 through INS-011, admitted model packets, INS-058
- **Build:** Replace empty validation artifacts with an approved evidence-referenced protocol, representative synthetic/reference cases, predefined safety/human-factors metrics and thresholds, adjudication, independence, and stop rules. Do not invent cases or thresholds.
- **Acceptance:** Cases are authored/approved by accountable humans; coverage maps to supported scope and every open hazard; protocol hash is fixed before execution.
- **Tests:** TP-21 schema/coverage checker; case uniqueness/traceability; unsafe-result gate; protocol-hash binding.
