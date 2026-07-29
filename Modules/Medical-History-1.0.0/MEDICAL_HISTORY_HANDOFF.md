# Medical History Handoff

## Architecture

This is a dependency-free standalone Node.js module. `server.js` owns activation, validation, JSON persistence, lookup, and static serving. `public/index.html`, `public/app.js`, and `public/styles.css` implement the browser flow. `data/medical_history_schema.json` is the integration contract. `test/server.test.js` runs the real HTTP server against a temporary data directory.

The stable boundary is `/api/internal/medical-history/*`. Another module should activate with a six-character code, open the returned `launchUrl`, and retrieve submissions using `GET /submissions?code={code}`. Codes are normalized to uppercase and stored on every submission.

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

## Conditional UI behavior

All four primary Yes/No questions default to No. Prior therapy = Yes reveals therapy success and antipsychotic selection. Clozapine contraindication = Yes reveals the checkbox list. Switching contraindication back to No clears checked contraindications. The Add drug control disables at 20 and re-enables after removal.

## Persistence and testing

Default runtime data is stored in `data/activation_sessions.json` and `data/medical_history_submissions.json`. `MEDICAL_HISTORY_DATA_DIR` overrides the directory so tests can run without touching real module data.

Verification:

```powershell
node --check server.js
node --check public/app.js
npm test
```

The v2 UUID resource is stored separately in
`medical_history_assessments_v2.json` (or the
`MEDICAL_HISTORY_V2_DATA_FILE` override). `test_v2_api.js` verifies canonical
UUIDs, actor attribution, explicit uncertainty, original medication text,
normalization state, idempotent create behavior, resource versions, and strong
ETag preconditions. The contract, Draft 2020-12 schema, and OpenAPI document are
in `contracts/`.

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

Do not rename the internal REST routes without coordinating every parent-module integration. Runtime JSON storage is suitable only for a prototype; production PHI requires hardened identity, access control, persistence, encryption, audit, and retention controls.
