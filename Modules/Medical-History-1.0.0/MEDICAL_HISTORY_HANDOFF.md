# Medical History Handoff

## Architecture

This is a dependency-free standalone Node.js 22.5+ module. `server.js` owns HTTP routing and authoritative validation, `repository.js` owns native SQLite persistence and ordered import, `auth.js` owns Authentication v2 session validation, and `csrf.js` owns signed double-submit tokens. `public/index.html`, `public/app.js`, and `public/styles.css` implement the bounded v2 embedded browser flow.

The canonical boundary is `/api/medical-history/v2/*`. The `/api/internal/medical-history/*` activation-code boundary remains a thin compatibility adapter; a code resolves to canonical Patient and Encounter UUIDs and never owns clinical state.

## Submission model (v2)

This section describes the legacy activation-code dataset whose existing
`datasetVersion` is 2.0.0. The canonical assessment REST interface is separately
versioned at interface/schema `2.0.0` under
`/api/medical-history/v2/assessments`.

- `pastMedicalHistory: string[]` — values must come from the options endpoint.
- `drugs: Drug[]` — at most 20; each included row requires `name`; dose, route, and frequency are optional.
- `substantialSuicideRisk: boolean` — UI default false.
- `priorAntipsychoticTherapy: boolean` — UI default false.
- `priorAntipsychoticTherapySuccessful: boolean | null` — required and boolean only when prior therapy is true.
- `antipsychotic: string | null` — controlled selection required only when prior therapy is true.
- `clozapineContraindication: boolean` — UI default false.
- `clozapineContraindications: string[]` — empty when false; at least one controlled option when true.
- `recurrentNonAdherenceDeterioration: boolean` — UI default false.

Exact clozapine contraindications:

1. Severe neutropenia
2. Clozapine-induced myocarditis
3. Unmanaged seizure disorder

`GET /api/internal/medical-history/options` returns disease, antipsychotic, and contraindication lists. Server validation is authoritative; do not rely only on conditional UI visibility.

## Embedded UI behavior

The host calls `window.InsightMedicalHistory.mount({ root, context })`, where context contains canonical Patient, Encounter, and authenticated Actor UUIDs plus an optional Assessment UUID. The module renders only under the supplied root, performs credentialed relative v2 requests, and aborts active requests and removes listeners on unmount. It does not read or mutate URLs, navigation, or browser storage.

All four primary questions initially display `Unanswered`; no answer is preselected. Yes reveals applicable conditional controls, and Unknown remains distinct from No. Unanswered values persist as `not-assessed`. Every medication row is retained as its own instance, including duplicates, and its server-supplied typed normalization state is shown without candidate selection or silent resolution. New rows begin as `not-assessed`. Failed saves remain visible in a focused alert until a later server save succeeds. The Add medication control disables at 20 and re-enables after removal.

## Persistence and testing

Default runtime data is stored in module-owned `data/medical-history.db`. The old activation, submission, and v2 JSON files are ordered one-time import sources. Imports are source-hash guarded; corrupt or post-import-modified sources fail startup, and records without canonical identity are retained in quarantine.

Verification:

```powershell
node --check server.js
node --check public/app.js
npm test
```

`test_repository.js` verifies fresh migration, JSON import, quarantine, corruption rollback, provenance, and transactional concurrency. `test_configuration.js` verifies production fail-closed startup. `test_v2_api.js` verifies Authentication role/revocation behavior, CSRF, restricted CORS, canonical identity, explicit uncertainty, idempotency, strong ETags, concurrent updates, latest reads, and readiness dependency failure. `test_ui.mjs` verifies host context, gateway-relative requests, duplicate and unresolved medication preservation, unanswered defaults, no browser PHI storage/navigation, CSRF headers, focus/error behavior, and the embedded lifecycle contract. The contract, Draft 2020-12 schema, and OpenAPI document are in `contracts/`.

The integration tests cover option lists, a fully populated conditional submission, all-default No answers, code normalization/retrieval, the 20-drug maximum, and invalid conditional combinations.

## Change guidance

When changing a collected field, keep these synchronized:

1. `public/index.html` markup and defaults.
2. `public/app.js` conditional behavior and payload mapping.
3. `server.js` controlled options, validation, and stored record mapping.
4. `data/medical_history_schema.json`.
5. `test/server.test.js`.
6. `README.md` and this handoff.
7. `graphify-out` via `graphify --update`.

Do not rename the internal compatibility routes without coordinating every parent-module integration. Do not restore JSON as an authoritative writer. Production PHI still requires approved encryption-at-rest, backup/restore, retention, and governance controls.
