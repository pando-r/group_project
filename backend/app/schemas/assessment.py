from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.schemas.patient import PatientSummary


class AssessmentCreate(BaseModel):
    patient_id: UUID
    disease_id: str = Field(min_length=1, max_length=64)
    inputs: dict[str, Any] = Field(min_length=1)

    @field_validator("inputs")
    @classmethod
    def _inputs_not_empty(cls, value: dict[str, Any]) -> dict[str, Any]:
        if not value:
            raise ValueError("评估字段不能为空")
        return value


class ConfirmAssessmentRequest(BaseModel):
    decision: str = Field(default="同意评估结论", min_length=1, max_length=64)
    note: str | None = Field(default=None, max_length=2000)


class AssessmentRead(BaseModel):
    id: UUID
    patient: PatientSummary
    specialty: str
    specialty_label: str
    disease_id: str
    disease_name: str
    inputs: dict[str, Any]
    result: dict[str, Any]
    status: str
    decision: str | None
    note: str | None
    confirmed_by: UUID | None
    confirmed_by_name: str | None
    confirmed_at: datetime | None
    model_version: str
    created_at: datetime
    updated_at: datetime


class AssessmentQueueItem(BaseModel):
    id: UUID
    patient_id: UUID
    patient_name: str
    mrn: str
    disease_id: str
    disease_name: str
    specialty: str
    severity_grade: str
    severity_level: int
    risk_percent: float
    risk_tier: str
    created_at: datetime
