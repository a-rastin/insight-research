# Add New Patient API Contract

Last updated: 2026-07-29

Canonical contract for Add New Patient module boundaries and internal REST
handoffs. Runtime validation source: `add_new_patient_backend/models.py`.

## Patient and Encounter v2

Interface/schema version `2.0.0` is published in
`schema/patient-encounter-v2.openapi.json` and
`schema/patient-encounter-v2.schema.json`. V2 keeps Patient, patient-code alias,
Encounter, and intake snapshot as separate resources with independent immutable
UUIDs, resource versions, strong ETags, and owner provenance.

- Resource paths accept canonical UUIDs only. Invalid UUID syntax is `400`;
  unknown UUIDs are `404`.
- Patient-code lookup uses `POST
  /api/add-new-patient/v2/patient-code-aliases/resolve`; codes never appear in
  integration URLs or foreign keys. Resolution is exact and case-insensitive.
- `POST /api/add-new-patient/v2/patients` atomically creates Patient, alias,
  first Encounter, and intake snapshot. `Idempotency-Key` is required and scoped
  to actor plus operation. Same key and exact body replays the original result;
  changed body returns `COMMON_IDEMPOTENCY_KEY_REUSED`.
- `GET /api/add-new-patient/v2/patients` paginates without search data in URLs.
  `POST /api/add-new-patient/v2/patients/search` carries search text in its body.
- `PATCH /api/add-new-patient/v2/patients/{patientId}` requires a strong
  `If-Match`; missing and stale preconditions return `428` and `412`.
- All exchanged timestamps use RFC 3339 UTC `Z`. Every JSON response advertises
  `X-Schema-Version: 2.0.0`.

Existing `patient_intake_records.id` values become v2 intake snapshot IDs.
Migration creates one separately generated Encounter UUID per intake row and
stores the source `legacyIntakeId` explicitly. It never groups or infers
encounters from `encounter_date`. Invalid UUID identities or case-insensitive
patient-code collisions stop migration without partial writes.

## Future Seam: Recorded-Acceptance Feedback

Deferred. No endpoint added now. When implemented, lives in Treatment Plan
module or shared `intake_records` writer seam — decide at follow-up module
design time.

Contract (future):

```text
Treatment Plan -> Add New Patient: GET /api/patients/{idOrCode}/recorded-acceptance
```

Read-only from Treatment Plan's side. Add New Patient remains source of
record for recorded-acceptance metadata that Treatment Plan emits after
psychiatrist "accept or modify" of a plan. Add New Patient does not own the
plan mutation itself — Treatment Plan owns plan state. Add New Patient only
mirrors the recorded acceptance event for audit/replay purposes.

Accept/modify mutation: Treatment Plan writes to its own store. Add New
Patient exposes no write API for this. Do not pre-build.

Post-creation read-only stance: from Treatment Plan's perspective, Add New
Patient is read-only. All mutations to plan state by psychiatrist (accept,
modify, reject) are Treatment Plan operations. Add New Patient stays passive
after intake creation.

## Boundary

Add New Patient owns patient identity + intake records only. Treatment-plan
generation, acceptance, modification belong to Treatment Plan module.

Modules must stay separate. Cross-module communication is internal REST only.
No module may import another module's backend code, read another module's
database, or share private persistence files.

## Handoff Direction

Treatment Plan fetches patient context from Add New Patient:

```text
Treatment Plan -> Add New Patient: GET /api/patients/{idOrCode}
Treatment Plan -> Auth: verify caller/session before treatment-plan work
Add New Patient -> Auth: verify caller/session for patient endpoints
```

Add New Patient does not call Treatment Plan. It remains the read source for
patient identity and intake data. Treatment Plan owns all treatment-plan
generation state and decisions after it reads patient context.

## Auth Contract

Patient endpoints require verified upstream auth. Read endpoints accept any
authenticated session; write endpoints require a psychiatrist session. Add New
Patient does not decode JWTs and does not read Auth storage. It verifies
identity only through Auth REST:

```text
GET /api/auth/v2/session
```

Forwarded auth headers accepted by Add New Patient's Auth client:

- `Authorization`
- `Cookie`
- `X-Auth-Session`
- `X-Auth-Session-Id`

The response must declare interface major 2 in `interfaceVersion` and schema
major 2 in `X-Schema-Version`. It must be authenticated and authorized, have
active unexpired UUID session and user IDs, satisfied password/disclaimer
gates, and a canonical lowercase `admin` or `psychiatrist` role. Read endpoints
accept either canonical role. Write endpoints require `psychiatrist`.

Rejected or missing sessions return:

```json
{ "error": "authentication_session_required" }
```

Auth upstream failures return:

```json
{ "error": "authentication_session_unavailable" }
```

`GET /api/auth/v2/session` exists inside Add New Patient only for standalone mock
auth when mock mode is enabled. Integrated deployments use the Auth module.

## CSRF Contract

Write endpoints require CSRF token + signed cookie.

```text
GET /api/add-new-patient/csrf
```

Success response:

```json
{ "csrfToken": "token" }
```

Client sends token on writes:

```text
Cookie: add_new_patient_csrf=<signed-token>
X-CSRF-Token: <token>
```

Invalid or missing CSRF returns HTTP 403:

```json
{ "error": "csrf_token_invalid" }
```

## Future Seam: Follow-up module

Deferred. No endpoint added now. When implemented, Follow-up module MUST
resolve patients via the same stable identifier contract documented in
`## Stable Patient Identifier Contract` below. The Follow-up module's
modified-treatment-plan intake write will reference `patient.id` (UUID)
pinned at intake creation — never re-derive from `patientCode`.

## Stable Patient Identifier Contract

Patient endpoints resolve a single patient across modules using either of
two stable identifiers:

- `id`: server UUID assigned at intake creation. Immutable, opaque, no
  human-readable meaning.
- `patientCode`: six-character user-visible code (`^[A-Z0-9]{6}$`).
  Stable across visits on the same patient. Case-insensitive uppercase
  comparison.

All lookup endpoints under `/api/patients/{identifier}` accept EITHER
`id` or `patientCode` as the path parameter. Resolution order:

1. UUID match against `patients.id`.
2. Case-insensitive uppercase match against `patients.patient_code`.

If UUID form is supplied, the lookup MUST NOT fall through to a
`patientCode` substring match — exact equality only. The repository
helper `_find_patient_id_row` is the authoritative resolver; new
read endpoints MUST route through it.

### Identifier Stability Invariants

- `id` is generated server-side once per `POST /api/patients` and never
  changes for the lifetime of the patient. Cross-module references
  (Follow-up module, Treatment Plan, modules reading intake history)
  MUST pin to `id`.
- `patientCode` is generated server-side once per `POST /api/patients`
  (when not supplied) and MUST NOT change for the lifetime of the
  patient. Cross-module references that surface a human-readable
  identifier MAY use `patientCode`, but the canonical link remains
  `id`.
- `patientCode` collisions are forbidden. The SQLite schema enforces
  this at the storage layer via `UNIQUE` on `patients.patient_code`
  (`db.py` `SCHEMA`). Pydantic additions alone are not sufficient —
  the DB constraint is the authoritative backstop, exercised by:
  - `POST /api/patients` with duplicate code → HTTP 422
    `errors.demographics.patientCode`.
  - `existing_codes()` returns the persisted set; the create flow
    rejects any code in that set.
- v1 does NOT derive `patientCode` from `id`. Deterministic generation
  from the UUID lands only if a downstream module requires it; for v1
  the random `secrets.choice` alphabet
  (`ABCDEFGHJKLMNPQRSTUVWXYZ23456789`) plus UNIQUE backstop is the
  contract.

### Endpoints Covered

The contract above applies to:

```text
GET /api/patients/{identifier}
GET /api/patients/{identifier}/intake
```

Future Follow-up module endpoints that resolve a patient MUST follow
the same `{identifier}` shape and resolution order.

## Add New Patient Owned Endpoints

These endpoints are owned by Add New Patient only.

```text
GET  /internal/dashboard/module-routes/add-new-patient
GET  /api/health
GET  /api/auth/v2/session         standalone mock auth only
GET  /api/add-new-patient/csrf
GET  /api/patients
POST /api/patients
GET  /api/patients/{idOrCode}
GET  /api/patients/{idOrCode}/intake
GET  /                             standalone shell (same HTML as module mount)
GET  /modules/add-new-patient      Dashboard launch target, serves index.html shell
GET  /modules/add-new-patient/     trailing-slash alias for the launch target
GET  /modules/{path:path}          static asset alias served from repo root
GET  /{path:path}                  static allowlist gate (catch-all)
```

`PATCH` is reserved for future write methods; current write surface is `POST`
only. The CSRF middleware enforces `POST` + `PATCH` against the same
token/cookie pair, so adding a `PATCH` endpoint later inherits the contract
without middleware changes.

No Treatment Plan endpoints belong in this module.

## Dashboard Launch Contract

Dashboard route discovery for the `add-new-patient` workspace button resolves
to this module-owned route metadata:

```json
{
  "moduleId": "add-new-patient",
  "title": "Add New Patient",
  "href": "/modules/add-new-patient"
}
```

`GET /modules/add-new-patient` serves the static `index.html` shell for
embedded launch. Standalone development still serves the same shell at `/`.

## GET /api/health

Public health check.

Success response:

```json
{
  "module": "Add New Patient",
  "status": "ok"
}
```

## GET /api/patients

Returns all persisted patient identity rows with latest intake snapshot.
Requires a verified authenticated session.

Success response:

```json
{
  "patients": []
}
```

## POST /api/patients

Creates patient identity + first intake record in one transaction. Requires
verified psychiatrist session and valid CSRF.

Preferred request shape:

```json
{
  "demographics": {
    "patientCode": "ABC123",
    "firstName": "Jane",
    "lastName": "Doe",
    "sex": "Female",
    "dob": "1986-07-07",
    "phoneNumber": "5551234567"
  },
  "clinical": {
    "encounterDate": "2026-07-07T10:00:00Z",
    "presentingComplaint": "Depressed mood and insomnia.",
    "provisionalDiagnosis": "Major depressive disorder",
    "treatmentHistory": ["Sertraline trial stopped due to nausea."],
    "allergies": ["Penicillin"],
    "currentMedications": ["Melatonin"],
    "riskFlags": {
      "suicidality": "suicidality_none",
      "substanceUse": false
    }
  }
}
```

Legacy flat payloads with same field names are still accepted for compatibility.

Success response, HTTP 201:

```json
{
  "patient": {
    "id": "uuid",
    "patientCode": "ABC123",
    "firstName": "Jane",
    "lastName": "Doe",
    "sex": "Female",
    "dob": "1986-07-07",
    "age": 40,
    "phoneNumber": "5551234567",
    "createdByUserId": "psy-1",
    "createdAt": "2026-07-07T10:00:00Z",
    "updatedAt": "2026-07-07T10:00:00Z",
    "intakeId": "uuid",
    "encounterDate": "2026-07-07T10:00:00Z",
    "presentingComplaint": "Depressed mood and insomnia.",
    "provisionalDiagnosis": "Major depressive disorder",
    "treatmentHistory": ["Sertraline trial stopped due to nausea."],
    "allergies": ["Penicillin"],
    "currentMedications": ["Melatonin"],
    "riskFlags": {
      "suicidality": "suicidality_none",
      "substanceUse": false
    }
  }
}
```

Validation failure, HTTP 422:

```json
{
  "message": "Patient data failed validation.",
  "errors": {
    "demographics.firstName": "Name is required."
  }
}
```

Duplicate patient code, HTTP 422:

```json
{
  "message": "Patient data failed validation.",
  "errors": {
    "demographics.patientCode": "Patient code already exists. Generate a new code and submit again."
  }
}
```

## GET /api/patients/{idOrCode}

Reads one patient by server `id` or user-visible `patientCode`. This is the
handoff endpoint Treatment Plan uses to fetch patient context. Requires a
verified authenticated session.

Lookup rules (full contract in `## Stable Patient Identifier Contract`):

- `id`: exact UUID match
- `patientCode`: case-insensitive uppercase match

Missing patient, HTTP 404:

```json
{ "message": "Patient was not found." }
```

## GET /api/patients/{idOrCode}/intake

Returns the patient record plus every persisted `IntakeRecord` for that
patient, ordered newest encounter-first then newest created-first. Used by
Follow-up module to load intake history across visits without mutating
patient identity, and by Treatment Plan to inspect prior encounters.

Identifier resolution follows `## Stable Patient Identifier Contract` —
the path parameter accepts either server `id` (UUID) or user-visible
`patientCode` (case-insensitive uppercase).

Requires a verified psychiatrist or admin session (read of clinical
intake history is privileged content, not a public lookup).

Success response:

```json
{
  "patient": {
    "id": "uuid",
    "patientCode": "ABC123",
    "firstName": "Jane",
    "lastName": "Doe"
  },
  "intakeRecords": [
    {
      "id": "uuid",
      "patientId": "uuid",
      "encounterDate": "2026-07-07T10:00:00Z",
      "presentingComplaint": "Depressed mood and insomnia.",
      "provisionalDiagnosis": "Major depressive disorder",
      "treatmentHistory": [],
      "allergies": [],
      "currentMedications": [],
      "riskFlags": { "suicidality": "suicidality_none", "substanceUse": false },
      "createdByUserId": "psy-1",
      "createdAt": "2026-07-07T10:00:00Z",
      "updatedAt": "2026-07-07T10:00:00Z"
    }
  ]
}
```

Missing patient, HTTP 404:

```json
{ "message": "Patient was not found." }
```

## Patient Context Fields For Treatment Plan

Treatment Plan may read these fields from Add New Patient:

- Patient identity: `id`, `patientCode`, `firstName`, `lastName`, `sex`, `dob`,
  `age`, `phoneNumber`
- Intake context: `intakeId`, `encounterDate`, `presentingComplaint`,
  `provisionalDiagnosis`, `treatmentHistory`, `allergies`,
  `currentMedications`, `riskFlags`
- Audit fields: `createdByUserId`, `createdAt`, `updatedAt`

Treatment Plan must store treatment-plan outputs in its own module storage.
It must not write treatment-plan decisions back into Add New Patient.

## Non-Owned Behavior

Add New Patient does not own:

- treatment-plan generation
- treatment-plan acceptance or rejection
- treatment-plan modification
- treatment-plan status workflow
- medication recommendation logic
- clinical decision support scoring
- Auth policy beyond verifying sessions through Auth REST
