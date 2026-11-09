from __future__ import annotations

from pydantic import BaseModel


class TrendPoint(BaseModel):
    date: str
    total: int
    confirmed: int
    pending: int
    high_risk: int


class DiseaseCount(BaseModel):
    disease_id: str
    disease_name: str
    count: int
    average_risk: float
    confirmed_rate: float


class SpecialtyCount(BaseModel):
    specialty: str
    specialty_label: str
    count: int


class AnalyticsOverview(BaseModel):
    total_assessments: int
    confirmed_assessments: int
    pending_assessments: int
    high_risk_assessments: int
    confirmation_rate: float
    average_risk: float
    trend: list[TrendPoint]
    by_disease: list[DiseaseCount]
    by_specialty: list[SpecialtyCount]
