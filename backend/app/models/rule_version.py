from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UTCDateTime, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.assessment import Assessment


class RuleVersion(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "rule_versions"

    version: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    changelog: Mapped[str] = mapped_column(Text, nullable=False)
    published_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False, server_default=func.now())

    assessments: Mapped[list[Assessment]] = relationship(back_populates="rule_version")
