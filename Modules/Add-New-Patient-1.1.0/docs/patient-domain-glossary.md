# Patient Domain Glossary

Runtime source of truth: `add_new_patient_backend/models.py`. Cross-module
identifier contract: `docs/api-contract.md` → `## Stable Patient Identifier
Contract`.

## Patient

Durable person record created by Add New Patient. Identified by server `id` and user-visible `patientCode`. Both identifiers are stable across every visit/intake for the lifetime of the patient — follow-up encounters resolve to the same row by either field.

Canonical fields:

- `id`: server UUID. Immutable, canonical cross-module key (Follow-up
  module, Treatment Plan, intake-history loaders all pin to `id`).
- `patientCode`: six-character generated code, unique, case-insensitive
  uppercased on comparison. User-visible. Stable per patient. DB
  storage layer enforces uniqueness via SQLite `UNIQUE` on
  `patients.patient_code`; duplicate POST returns HTTP 422.
- `firstName`: required demographic name.
- `lastName`: required demographic name.
- `sex`: required demographic value, `Male` or `Female`.
- `dob`: required date of birth. Must not be future-dated and must be at least 1 year ago. `age` is computed at read time and is not stored.
- `phoneNumber`: optional 10-digit phone, stored as digits.
- `createdByUserId`: authenticated psychiatrist user id that created the identity row.
- `createdAt`: server timestamp.
- `updatedAt`: server timestamp.

## IntakeRecord

Clinical intake attached to patient creation. Add New Patient stores it in `patient_intake_records` so later follow-up intakes can preserve history instead of overwriting patient identity.

Canonical fields:

- `id`: server UUID.
- `patientId`: parent `patients.id`.
- `encounterDate`: encounter timestamp.
- `presentingComplaint`: required free text, max 2000 chars.
- `provisionalDiagnosis`: required free text or v1 ICD-10-like four-character code pattern, max 240 chars. Full ICD-10 validation is out of scope for v1.
- `treatmentHistory`: optional treatment-history string list, defaults to `[]`.
- `allergies`: optional string list, defaults to `[]`.
- `currentMedications`: optional string list, defaults to `[]`.
- `riskFlags`: optional structured clinical flags, defaults safe.
- `createdByUserId`: authenticated psychiatrist user id that created the intake row.

## ClinicalFlag

Structured risk signal for downstream CDSS logic.

Canonical fields:

- `suicidality`: one of `suicidality_none`, `ideation`, `plan`, `attempt`; default `suicidality_none`.
- `substanceUse`: boolean; default `false`.

## TreatmentHistory

Prior treatment summary for treatment planning. Stored in C1.1 as `treatmentHistory: string[]` so intake can capture partial prior-care context without blocking patient creation.

String entries may include:

- prior medication trials.
- psychotherapy or program history.
- response, intolerance, adherence notes.
- relevant hospitalization or escalation events.

## Contract Notes

- `PatientIntake` Pydantic schema combines `Patient` demographics + first `IntakeRecord` clinical fields for `POST /api/patients`.
- `POST /api/patients` creates `patients` + `patient_intake_records` rows in one transaction.
- Optional clinical lists and flags must default to safe empty/negative values.
- Add New Patient accepts partial clinical context beyond required `presentingComplaint` and `provisionalDiagnosis`; treatment-plan v1 decides stricter generation requirements.
