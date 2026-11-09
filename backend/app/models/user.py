from __future__ import annotations

from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.agent import AgentFeedback, AgentRun
    from app.models.assessment import Assessment
    from app.models.audit import AuditLog


class UserRole(StrEnum):
    DOCTOR = "DOCTOR"
    ADMIN = "ADMIN"


class User(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('DOCTOR', 'ADMIN')", name="role_allowed"),)

    username: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default=UserRole.DOCTOR)

    confirmed_assessments: Mapped[list[Assessment]] = relationship(
        back_populates="confirmed_by_user",
        foreign_keys="Assessment.confirmed_by",
    )
    audit_logs: Mapped[list[AuditLog]] = relationship(back_populates="actor")
    agent_runs: Mapped[list[AgentRun]] = relationship(
        back_populates="created_by_user",
        foreign_keys="AgentRun.created_by",
    )
    agent_feedback: Mapped[list[AgentFeedback]] = relationship(
        back_populates="doctor",
        foreign_keys="AgentFeedback.doctor_id",
    )

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN
