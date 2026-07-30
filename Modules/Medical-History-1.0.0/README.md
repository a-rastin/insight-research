# Medical History Module

Standalone Node.js module that stores versioned medical-history assessments under canonical Patient, Encounter, and Assessment UUIDs. Six-character activation codes are compatibility aliases only.

## Run and test

```powershell
npm start
npm test
```

Open `http://localhost:4173`, activate with a six-character code plus canonical Patient and Encounter UUID context, complete the form, and submit. Node.js 22.5 or newer is required for native SQLite.

## Collected information

- Patient drug list: zero to 20 entries; each drug has name, dose, route, and frequency.
- Past medical history: multi-select list of relevant diseases.
- Substantial suicide risk: Yes/No, default No.
- Prior antipsychotic therapy: Yes/No, default No. When Yes, therapy success and an antipsychotic selection are required.
- Contraindication to clozapine: Yes/No, default No. When Yes, one or more of Severe neutropenia, Clozapine-induced myocarditis, or Unmanaged seizure disorder is required.
- Recurrent non-adherence-related deterioration: Yes/No, default No.

Conditional questions are hidden until applicable. The server independently validates all rules, including the 20-drug maximum and controlled option lists.

## Correlation and persistence

A parent module may activate the compatibility UI with `POST /api/internal/medical-history/activate`. Codes are normalized to uppercase and resolve to canonical Patient and Encounter UUIDs. They are never clinical storage keys.

```http
GET /api/internal/medical-history/submissions?code=A1B2C3
```

The authoritative store is module-owned SQLite at `data/medical-history.db`, configurable with `MEDICAL_HISTORY_DB_PATH`. Ordered migrations create current assessments, immutable attributed versions, actor-scoped idempotency records, aliases, import metadata, and quarantine records.

The previous JSON arrays are one-time import sources only:

- `data/activation_sessions.json`
- `data/medical_history_submissions.json`

Corrupt JSON aborts startup and cannot replace visible database state with an empty store. Canonical records import once by source hash; unmapped records are quarantined rather than assigned guessed UUIDs. A source that changes after import fails closed.

## Internal REST API

- `GET /api/internal/medical-history/health`
- `POST /api/internal/medical-history/activate`
- `GET /api/internal/medical-history/activation/{code}`
- `GET /api/internal/medical-history/options`
- `POST /api/internal/medical-history/submissions`
- `GET /api/internal/medical-history/submissions[?code=...]`
- `GET /api/internal/medical-history/schema`

Example submission:

```json
{
  "code": "A1B2C3",
  "pastMedicalHistory": ["Hypertension"],
  "drugs": [{ "name": "Lithium", "dose": "300 mg", "route": "Oral", "frequency": "Daily" }],
  "substantialSuicideRisk": false,
  "priorAntipsychoticTherapy": true,
  "priorAntipsychoticTherapySuccessful": false,
  "antipsychotic": "Risperidone",
  "clozapineContraindication": true,
  "clozapineContraindications": ["Severe neutropenia"],
  "recurrentNonAdherenceDeterioration": false
}
```

The canonical dataset contract is `data/medical_history_schema.json`.

## Medical History assessment v2

The UUID-based v2 interface is additive; the activation-code routes above
remain the legacy standalone adapter.

- `GET /api/medical-history/v1/contract`
- `GET /api/medical-history/v2/contract/{document|schema|openapi}`
- `GET /api/medical-history/v2/csrf`
- `POST /api/medical-history/v2/assessments`
- `GET /api/medical-history/v2/assessments/{assessmentId}`
- `PUT /api/medical-history/v2/assessments/{assessmentId}`
- `GET /api/medical-history/v2/encounters/{encounterId}/assessments/latest`

V2 requires canonical Patient, Encounter, Assessment, and psychiatrist Actor
UUIDs. Clinical yes/no fields use the controlled values `yes`, `no`, `unknown`,
and `not-assessed`; missing information is never converted to `no`. Medication
entries preserve required `originalText` and carry an optional normalized
identity with an explicit `matched`, `unresolved`, `ambiguous`, or
`not-assessed` state.

Create requests require `X-Schema-Version: 2.0.0` and an `Idempotency-Key`.
Mutable resources return a strong `ETag`; updates require the current value in
`If-Match`. Responses include timestamps, actor attribution, provenance, and an
incrementing `resourceVersion`. Published artifacts are under `contracts/`.

Every clinical read and write revalidates the opaque cookie through Authentication `GET /api/auth/v2/session`; only a current psychiatrist session is accepted. Writes additionally require the signed, session-bound double-submit token from the CSRF endpoint. Credentialed CORS is emitted only for exact origins configured in `MEDICAL_HISTORY_ALLOWED_ORIGINS`. Production requires `MEDICAL_HISTORY_CSRF_SECRET` with at least 32 characters. `MEDICAL_HISTORY_AUTH_BASE_URL` and `MEDICAL_HISTORY_AUTH_TIMEOUT_MS` configure Authentication.

## Production note

Database-at-rest encryption, backup/restore operations, retention policy, and clinical governance approval remain deployment gates outside this packet.
