# Suicide Risk Handoff

`server.js` owns HTTP validation and INS-010 disposition derivation. `repository.js` owns the module-local SQLite schema, immutable versions, ETag concurrency transaction, and actor-scoped idempotency. `auth.js` and `csrf.js` implement Authentication v2 session verification and signed double-submit protection. `public/` contains the bounded dependency-free UI.

The runtime source of truth is `contracts/suicide-risk-assessment-v1.contract.json` with its Draft 2020-12 schema and OpenAPI document. The source trace is intentionally limited to accepted ownership and Treatment Plan safety-policy fields. Do not add C-SSRS content or a favorable risk state until a superseding approved source/licensing and clinical-governance packet updates the contract first.

Run `npm test` for source traceability, forbidden-field, repository, missing/conflicting/urgent, auth, CSRF, idempotency, ETag, snapshot, accessibility, and no-PHI browser checks.
