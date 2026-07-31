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

## 🧠 Phase 3 — DDI and BN decision services

### INS-033 — Add BN registry lifecycle, hashes, and clinical-use gates

- **Build:** Persist or deterministically expose model hash, source/provenance, lifecycle, calibration label, approval references, version history, and rollback. Change current qualitative models from ambiguous `active` status to an explicit structurally available but clinically blocked state unless evidence says otherwise.
- **Acceptance:** Structural validity never implies clinical approval; old evaluations retain exact version/hash; new activation is role-protected and approval-gated; registry paths stay module-controlled.
- **Tests:** Registry migration/serialization; hash stability; status transitions; downgrade/rollback; old-evaluation provenance; blocked-clinical-evaluation; auth/CSRF/role.