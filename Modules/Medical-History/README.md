# Medical History Module

Standalone Node.js module that collects a patient's medical history and saves each submission under a six-character activation/sample code.

## Run and test

```powershell
npm start
npm test
```

Open `http://localhost:4173`, activate with a six-character alphanumeric code, complete the form, and submit. Node.js 18 or newer is required.

## Collected information

- Patient drug list: zero to 20 entries; each drug has name, dose, route, and frequency.
- Past medical history: multi-select list of relevant diseases.
- Substantial suicide risk: Yes/No, default No.
- Prior antipsychotic therapy: Yes/No, default No. When Yes, therapy success and an antipsychotic selection are required.
- Contraindication to clozapine: Yes/No, default No. When Yes, one or more of Severe neutropenia, Clozapine-induced myocarditis, or Unmanaged seizure disorder is required.
- Recurrent non-adherence-related deterioration: Yes/No, default No.

Conditional questions are hidden until applicable. The server independently validates all rules, including the 20-drug maximum and controlled option lists.

## Correlation and persistence

A parent module activates this module with `POST /api/internal/medical-history/activate`. Codes are normalized to uppercase. Submissions are appended to `data/medical_history_submissions.json` and can be retrieved by code:

```http
GET /api/internal/medical-history/submissions?code=A1B2C3
```

Runtime files remain JSON arrays:

- `data/activation_sessions.json`
- `data/medical_history_submissions.json`

Set `MEDICAL_HISTORY_DATA_DIR` to use another runtime data directory (used by the isolated test suite).

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
- `POST /api/medical-history/v2/assessments`
- `GET /api/medical-history/v2/assessments/{assessmentId}`
- `PUT /api/medical-history/v2/assessments/{assessmentId}`

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

## Production note

This is prototype storage, not production-ready PHI infrastructure. Production deployment needs authentication, authorization, restricted CORS, encrypted/database persistence, audit logging, concurrency-safe writes, and appropriate clinical governance.
