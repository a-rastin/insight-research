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

### INS-063 — Execute clinical and human-factors validation

- **Type / owner:** HITL / independent evaluators
- **Blocked by:** INS-061, INS-062
- **Build:** Run fixed build/model/KB/policy versions against the approved protocol; record observations, deviations, hazards, metrics, and report reference without repository PHI.
- **Acceptance:** Results are reproducible and bound to exact hashes; unsafe omissions/commissions or incomplete coverage open hazards and keep release blocked; no threshold is adjusted after seeing results without a new protocol version.
- **Tests:** TP-21 report validator; reproducibility rerun; version/hash binding; hazard-log linkage.
