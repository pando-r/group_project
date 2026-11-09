from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.schemas.assessment import AssessmentQueueItem


class MetricCard(BaseModel):
    key: str
    label: str
    value: int | float
    unit: str | None = None
    hint: str | None = None


class RiskSlice(BaseModel):
    tier: str
    label: str
    count: int
    percent: float
    tone: str


class ActivityItem(BaseModel):
    assessment_id: str
    patient_name: str
    action: str
    detail: str
    created_at: datetime


class ModelStatus(BaseModel):
    mode: str
    mode_label: str
    model: str
    prompt_version: str
    rule_version: str
    note: str


class DashboardResponse(BaseModel):
    metrics: list[MetricCard]
    pending_queue: list[AssessmentQueueItem]
    risk_distribution: list[RiskSlice]
    recent_activity: list[ActivityItem]
    model_status: ModelStatus
