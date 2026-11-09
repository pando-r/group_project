from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.assessment import Assessment
    from app.models.patient import Patient
    from app.models.user import User


class AgentRunStatus(StrEnum):
    RUNNING = "RUNNING"
    WAITING_HUMAN = "WAITING_HUMAN"
    DONE = "DONE"
    FAILED = "FAILED"


class AgentStepStatus(StrEnum):
    STARTED = "STARTED"
    OK = "OK"
    ERROR = "ERROR"


def json_type() -> JSON:
    return JSON().with_variant(JSONB(), "postgresql")


class AgentRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "agent_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('RUNNING', 'WAITING_HUMAN', 'DONE', 'FAILED')",
            name="status_allowed",
        ),
        Index("ix_agent_runs_patient_created", "patient_id", "created_at"),
        Index("ix_agent_runs_status", "status"),
    )

    patient_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("patients.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assessment_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("assessments.id", ondelete="RESTRICT")
    )
    thread_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=AgentRunStatus.RUNNING)
    model: Mapped[str] = mapped_column(String(100), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(64), nullable=False)
    input: Mapped[dict[str, Any]] = mapped_column(json_type(), nullable=False)
    output: Mapped[dict[str, Any] | None] = mapped_column(json_type())
    tokens_in: Mapped[int | None] = mapped_column(BigInteger)
    tokens_out: Mapped[int | None] = mapped_column(BigInteger)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    created_by: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    patient: Mapped[Patient] = relationship(back_populates="agent_runs")
    assessment: Mapped[Assessment | None] = relationship(back_populates="agent_runs")
    created_by_user: Mapped[User] = relationship(
        back_populates="agent_runs",
        foreign_keys=[created_by],
    )
    steps: Mapped[list[AgentStep]] = relationship(
        back_populates="run",
        order_by="AgentStep.seq",
        cascade="all, delete-orphan",
    )
    feedback: Mapped[list[AgentFeedback]] = relationship(back_populates="run", cascade="all, delete-orphan")


class AgentStep(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "agent_steps"
    __table_args__ = (
        UniqueConstraint("run_id", "seq", name="uq_agent_steps_run_seq"),
        CheckConstraint("status IN ('STARTED', 'OK', 'ERROR')", name="status_allowed"),
    )

    run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    node: Mapped[str] = mapped_column(String(64), nullable=False)
    tool_name: Mapped[str | None] = mapped_column(String(64))
    input: Mapped[dict[str, Any] | None] = mapped_column(json_type())
    output: Mapped[dict[str, Any] | None] = mapped_column(json_type())
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=AgentStepStatus.STARTED)
    latency_ms: Mapped[int | None] = mapped_column(Integer)

    run: Mapped[AgentRun] = relationship(back_populates="steps")


class AgentFeedback(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "agent_feedback"
    __table_args__ = (
        UniqueConstraint("run_id", "doctor_id", name="uq_agent_feedback_run_doctor"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="rating_range"),
    )

    run_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("agent_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    doctor_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    comment: Mapped[str | None] = mapped_column(Text)

    run: Mapped[AgentRun] = relationship(back_populates="feedback")
    doctor: Mapped[User] = relationship(back_populates="agent_feedback", foreign_keys=[doctor_id])
