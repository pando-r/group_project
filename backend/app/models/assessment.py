from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import (
    JSON,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    Text,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UTCDateTime, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.agent import AgentRun
    from app.models.audit import AuditLog
    from app.models.patient import Patient
    from app.models.rule_version import RuleVersion
    from app.models.user import User


class AssessmentStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"


def json_type() -> JSON:
    return JSON().with_variant(JSONB(), "postgresql")


class Assessment(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "assessments"
    __table_args__ = (
        CheckConstraint("status IN ('PENDING', 'CONFIRMED')", name="status_allowed"),
        CheckConstraint(
            "status = 'PENDING' OR (confirmed_by IS NOT NULL AND confirmed_at IS NOT NULL)",
            name="confirmed_fields_required",
        ),
        Index("ix_assessments_patient_created", "patient_id", "created_at"),
        Index("ix_assessments_status_created", "status", "created_at"),
        Index("ix_assessments_disease_created", "disease_id", "created_at"),
    )

    patient_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("patients.id", ondelete="RESTRICT"),
        nullable=False,
    )
    specialty: Mapped[str] = mapped_column(String(32), nullable=False)
    disease_id: Mapped[str] = mapped_column(String(64), nullable=False)
    inputs: Mapped[dict[str, Any]] = mapped_column(json_type(), nullable=False)
    result: Mapped[dict[str, Any]] = mapped_column(json_type(), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=AssessmentStatus.PENDING, index=True
    )
    decision: Mapped[str | None] = mapped_column(String(64))
    note: Mapped[str | None] = mapped_column(Text)
    confirmed_by: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT")
    )
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    model_version: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("rule_versions.version", ondelete="RESTRICT"),
        nullable=False,
    )

    patient: Mapped[Patient] = relationship(back_populates="assessments")
    confirmed_by_user: Mapped[User | None] = relationship(
        back_populates="confirmed_assessments",
        foreign_keys=[confirmed_by],
    )
    rule_version: Mapped[RuleVersion] = relationship(back_populates="assessments")
    audit_logs: Mapped[list[AuditLog]] = relationship(
        back_populates="assessment",
        order_by="AuditLog.created_at",
    )
    agent_runs: Mapped[list[AgentRun]] = relationship(back_populates="assessment")

    @property
    def is_confirmed(self) -> bool:
        return self.status == AssessmentStatus.CONFIRMED
