from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

AgentDecision = Literal["APPROVE", "REJECT"]
DraftFactKey = Literal[
    "severity_grade",
    "severity_level",
    "risk_percent",
    "risk_tier",
    "prognosis_tier",
]


class DraftFact(BaseModel):
    key: DraftFactKey
    value: str


class DraftSection(BaseModel):
    heading: str = Field(min_length=1, max_length=80)
    body: str = Field(min_length=1, max_length=2000)
    evidence_ids: list[str] = Field(default_factory=list, max_length=20)


class AgentDraft(BaseModel):
    """Structured LLM draft. Numbers are copied from rule output, never invented."""

    title: str = Field(min_length=1, max_length=120)
    summary: str = Field(min_length=1, max_length=1200)
    risk_explanation: str = Field(min_length=1, max_length=1200)
    key_points: list[str] = Field(default_factory=list, max_length=10)
    sections: list[DraftSection] = Field(default_factory=list, max_length=8)
    recommendation_ids: list[str] = Field(default_factory=list, max_length=12)
    evidence_ids: list[str] = Field(default_factory=list, max_length=30)
    facts: list[DraftFact] = Field(min_length=1, max_length=8)
    disclaimer: str = Field(default="演示模型，未经校准", max_length=80)


class VerificationResult(BaseModel):
    schema_passed: bool
    numeric_passed: bool
    citation_passed: bool
    rewrite_rounds: int = 0
    errors: list[str] = Field(default_factory=list)


class AgentRunCreate(BaseModel):
    assessment_id: UUID
    focus: str | None = Field(default=None, max_length=200)


class AgentDecisionRequest(BaseModel):
    decision: AgentDecision
    note: str | None = Field(default=None, max_length=2000)
    edited_draft: dict[str, Any] | None = None

    @field_validator("note")
    @classmethod
    def _trim_note(cls, value: str | None) -> str | None:
        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None


class AgentFeedbackRequest(BaseModel):
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class AgentStepRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    seq: int
    node: str
    tool_name: str | None
    input: dict[str, Any] | None
    output: dict[str, Any] | None
    status: str
    latency_ms: int | None
    created_at: datetime


class AgentRunRead(BaseModel):
    id: UUID
    patient_id: UUID
    patient_name: str
    assessment_id: UUID | None
    disease_id: str
    disease_name: str
    status: str
    model: str
    prompt_version: str
    tokens_in: int | None
    tokens_out: int | None
    latency_ms: int | None
    draft: AgentDraft | None = None
    verification: VerificationResult | None = None
    decision: str | None = None
    rejection_reason: str | None = None
    error: str | None = None
    created_at: datetime
    updated_at: datetime
    steps: list[AgentStepRead] = Field(default_factory=list)


class AgentRunQueueItem(BaseModel):
    id: UUID
    assessment_id: UUID | None
    disease_id: str
    disease_name: str
    status: str
    model: str
    created_at: datetime


class AgentFeedbackRead(BaseModel):
    id: UUID
    run_id: UUID
    doctor_id: UUID
    rating: int
    comment: str | None
    created_at: datetime
