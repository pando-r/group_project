from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, Date, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, CreatedAtMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.agent import AgentRun
    from app.models.assessment import Assessment


class Patient(UUIDPrimaryKeyMixin, CreatedAtMixin, Base):
    __tablename__ = "patients"
    __table_args__ = (
        CheckConstraint(
            "gender IN ('MALE', 'FEMALE', 'OTHER', 'UNKNOWN')",
            name="gender_allowed",
        ),
    )

    mrn: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    gender: Mapped[str] = mapped_column(String(16), nullable=False, default="UNKNOWN")
    birth_date: Mapped[date] = mapped_column(Date, nullable=False)

    assessments: Mapped[list[Assessment]] = relationship(
        back_populates="patient",
        order_by="Assessment.created_at.desc()",
        lazy="selectin",
    )
    agent_runs: Mapped[list[AgentRun]] = relationship(back_populates="patient")

    @property
    def age(self) -> int:
        today = date.today()
        return (
            today.year
            - self.birth_date.year
            - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
        )
