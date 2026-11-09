from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Gender(StrEnum):
    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class PatientCreate(BaseModel):
    mrn: str = Field(min_length=3, max_length=32, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=100)
    gender: Gender = Gender.UNKNOWN
    birth_date: date

    @field_validator("birth_date")
    @classmethod
    def _birth_date_not_future(cls, value: date) -> date:
        if value > date.today():
            raise ValueError("出生日期不能晚于今天")
        return value

    @field_validator("name")
    @classmethod
    def _trim_name(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("姓名不能为空")
        return trimmed

    @field_validator("mrn")
    @classmethod
    def _normalise_mrn(cls, value: str) -> str:
        return value.strip().upper()


class PatientSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    mrn: str
    name: str
    gender: str
    birth_date: date
    age: int
    created_at: datetime


class AssessmentBrief(BaseModel):
    id: UUID
    disease_id: str
    disease_name: str
    specialty: str
    specialty_label: str
    status: str
    severity_grade: str
    severity_level: int
    severity_tone: str
    risk_percent: float
    risk_tier: str
    risk_tone: str
    created_at: datetime
    confirmed_at: datetime | None = None


class RiskPoint(BaseModel):
    assessment_id: UUID
    disease_name: str
    created_at: datetime
    risk_percent: float
    severity_level: int


class PatientListItem(PatientSummary):
    last_assessment: AssessmentBrief | None = None


class PatientDetail(PatientSummary):
    assessments: list[AssessmentBrief]
    risk_trend: list[RiskPoint]
