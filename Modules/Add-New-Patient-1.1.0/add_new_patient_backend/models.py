from __future__ import annotations

import re
from datetime import UTC, date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
TEXT_LIMIT = 2000
DIAGNOSIS_LIMIT = 240
LIST_ITEM_LIMIT = 160
ICD10_V1_PATTERN = re.compile(r"^[A-TV-Z][0-9][0-9A-Z](?:\.?[0-9A-Z])?$", re.IGNORECASE)


class ClinicalFlag(BaseModel):
    suicidality: Literal["suicidality_none", "ideation", "plan", "attempt"] = "suicidality_none"
    substanceUse: bool = False

    @field_validator("suicidality", mode="before")
    @classmethod
    def normalize_suicidality(cls, value: Any) -> Any:
        if value == "none":
            return "suicidality_none"
        return value


class PatientDemographics(BaseModel):
    patientCode: str | None = None
    firstName: str
    lastName: str
    sex: str
    dob: date
    phoneNumber: str | None = None

    @field_validator("dob")
    @classmethod
    def check_dob(cls, value: date) -> date:
        today = datetime.now(UTC).date()
        if value > today:
            raise ValueError("Date of birth cannot be in the future.")
        age = today.year - value.year - ((today.month, today.day) < (value.month, value.day))
        if age < 1:
            raise ValueError("Date of birth must be at least 1 year ago.")
        return value

    @field_validator("sex")
    @classmethod
    def normalize_sex(cls, value: str) -> str:
        value = value.strip()
        if value not in ("Male", "Female"):
            raise ValueError("Sex must be Male or Female.")
        return value

    @field_validator("firstName", "lastName")
    @classmethod
    def trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name is required.")
        if len(value) > 80:
            raise ValueError("Name must be 80 characters or fewer.")
        return value

    @field_validator("patientCode")
    @classmethod
    def normalize_code(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip().upper()
        if value and not re.fullmatch(r"[A-Z0-9]{6}", value):
            raise ValueError("Patient code must be 6 uppercase letters or numbers.")
        return value or None

    @field_validator("phoneNumber")
    @classmethod
    def strip_phone(cls, value: str | None) -> str | None:
        if value is None:
            return value
        digits = re.sub(r"\D", "", value)
        if digits and len(digits) != 10:
            raise ValueError("Phone number must contain exactly 10 digits.")
        return digits or None


class ClinicalSection(BaseModel):
    encounterDate: str | None = None
    presentingComplaint: str
    provisionalDiagnosis: str
    treatmentHistory: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    currentMedications: list[str] = Field(default_factory=list)
    riskFlags: ClinicalFlag = Field(default_factory=ClinicalFlag)

    @field_validator("encounterDate")
    @classmethod
    def validate_encounter_date(cls, value: str | None) -> str | None:
        return normalize_utc_timestamp(value) if value is not None else None

    @field_validator("presentingComplaint")
    @classmethod
    def trim_presenting_complaint(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Presenting complaint is required.")
        if len(value) > TEXT_LIMIT:
            raise ValueError(f"Presenting complaint must be {TEXT_LIMIT} characters or fewer.")
        return value

    @field_validator("provisionalDiagnosis")
    @classmethod
    def trim_provisional_diagnosis(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Provisional diagnosis is required.")
        if len(value) > DIAGNOSIS_LIMIT:
            raise ValueError(f"Provisional diagnosis must be {DIAGNOSIS_LIMIT} characters or fewer.")
        compact = value.replace(".", "")
        if " " not in value and any(char.isdigit() for char in value) and len(compact) <= 4 and not ICD10_V1_PATTERN.fullmatch(value):
            raise ValueError("Provisional diagnosis must be free text or a v1 ICD-10 code pattern.")
        return value

    @field_validator("treatmentHistory", "allergies", "currentMedications", mode="before")
    @classmethod
    def default_optional_lists(cls, value: Any) -> list[str]:
        if value is None:
            return []
        return value

    @field_validator("riskFlags", mode="before")
    @classmethod
    def default_risk_flags(cls, value: Any) -> Any:
        return {} if value is None else value

    @field_validator("treatmentHistory", "allergies", "currentMedications")
    @classmethod
    def normalize_optional_lists(cls, value: list[Any]) -> list[str]:
        normalized: list[str] = []
        for item in value:
            text = str(item).strip()
            if not text:
                continue
            if len(text) > LIST_ITEM_LIMIT:
                raise ValueError(f"List items must be {LIST_ITEM_LIMIT} characters or fewer.")
            normalized.append(text)
        return normalized


DEMOGRAPHICS_FIELDS = frozenset(PatientDemographics.model_fields)
CLINICAL_FIELDS = frozenset(ClinicalSection.model_fields)


class PatientIntake(BaseModel):
    demographics: PatientDemographics
    clinical: ClinicalSection

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_flat_payload(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        if "demographics" in value or "clinical" in value:
            return value
        return {
            "demographics": {field: value[field] for field in DEMOGRAPHICS_FIELDS if field in value},
            "clinical": {field: value[field] for field in CLINICAL_FIELDS if field in value},
        }

    def to_patient_record(self) -> dict[str, Any]:
        return {**self.demographics.model_dump(mode="json"), **self.clinical.model_dump(mode="json")}


PatientCreate = PatientIntake


def normalize_utc_timestamp(value: str) -> str:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("Timestamp must be RFC 3339 UTC with a Z suffix.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError("Timestamp must be a valid RFC 3339 UTC value.") from error
    if parsed.utcoffset() != UTC.utcoffset(parsed):
        raise ValueError("Timestamp must use UTC.")
    return value


class V2Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PatientInputV2(PatientDemographics):
    model_config = ConfigDict(extra="forbid")


class EncounterInputV2(V2Model):
    encounterType: Literal["initial"]
    occurredAt: str

    _utc_occurred_at = field_validator("occurredAt")(normalize_utc_timestamp)


class IntakeSnapshotInputV2(V2Model):
    presentingComplaint: str
    provisionalDiagnosis: str
    treatmentHistory: list[str] = Field(default_factory=list)
    allergies: list[str] = Field(default_factory=list)
    currentMedications: list[str] = Field(default_factory=list)
    riskFlags: ClinicalFlag = Field(default_factory=ClinicalFlag)

    _presenting_complaint = field_validator("presentingComplaint")(ClinicalSection.trim_presenting_complaint.__func__)
    _provisional_diagnosis = field_validator("provisionalDiagnosis")(ClinicalSection.trim_provisional_diagnosis.__func__)
    _default_lists = field_validator("treatmentHistory", "allergies", "currentMedications", mode="before")(
        ClinicalSection.default_optional_lists.__func__
    )
    _default_risk_flags = field_validator("riskFlags", mode="before")(ClinicalSection.default_risk_flags.__func__)
    _normalize_lists = field_validator("treatmentHistory", "allergies", "currentMedications")(
        ClinicalSection.normalize_optional_lists.__func__
    )


class PatientEncounterCreateV2(V2Model):
    patient: PatientInputV2
    encounter: EncounterInputV2
    intakeSnapshot: IntakeSnapshotInputV2


class PatientPatchV2(V2Model):
    firstName: str | None = None
    lastName: str | None = None
    sex: str | None = None
    dob: date | None = None
    phoneNumber: str | None = None

    _dob = field_validator("dob")(PatientDemographics.check_dob.__func__)
    _sex = field_validator("sex")(PatientDemographics.normalize_sex.__func__)
    _names = field_validator("firstName", "lastName")(PatientDemographics.trim_name.__func__)
    _phone = field_validator("phoneNumber")(PatientDemographics.strip_phone.__func__)

    @model_validator(mode="after")
    def require_change(self) -> "PatientPatchV2":
        if not self.model_fields_set:
            raise ValueError("At least one patient field is required.")
        return self


class PatientSearchV2(V2Model):
    query: str = Field(min_length=1, max_length=80)
    pageSize: int = Field(default=50, ge=1, le=100)
    pageToken: str | None = None

    @field_validator("query")
    @classmethod
    def trim_query(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Search query is required.")
        return value


class PatientCodeResolveV2(V2Model):
    patientCode: str

    _code = field_validator("patientCode")(PatientDemographics.normalize_code.__func__)


class FollowUpChangeV1(V2Model):
    domain: Literal["diagnosis", "severity", "medical-history", "medication", "encounter"]
    summary: str = Field(min_length=1, max_length=500)
    sourceResourceId: str = Field(min_length=1, max_length=128)

    @field_validator("summary", "sourceResourceId")
    @classmethod
    def trim_follow_up_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Follow-up change fields cannot be blank.")
        return value


class FollowUpCreateV1(V2Model):
    priorEncounterId: str
    occurredAt: str
    priorFinalPlanId: str
    changes: list[FollowUpChangeV1] = Field(min_length=1, max_length=50)

    _occurred_at = field_validator("occurredAt")(normalize_utc_timestamp)

    @field_validator("priorEncounterId", "priorFinalPlanId")
    @classmethod
    def canonical_uuid(cls, value: str) -> str:
        from uuid import UUID

        try:
            canonical = str(UUID(value))
        except ValueError as error:
            raise ValueError("Identifier must be a canonical UUID.") from error
        if canonical != value:
            raise ValueError("Identifier must be a canonical UUID.")
        return canonical


def generate_patient_code() -> str:
    import secrets

    return "".join(secrets.choice(CODE_ALPHABET) for _ in range(6))
