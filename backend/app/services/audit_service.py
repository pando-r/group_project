from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.models.audit import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogRead


def add_audit(
    session: AsyncSession,
    *,
    assessment_id: UUID,
    actor_id: UUID,
    action: str,
    detail: dict[str, Any],
    ip: str | None,
) -> None:
    session.add(
        AuditLog(
            assessment_id=assessment_id,
            actor_id=actor_id,
            action=action,
            detail=detail,
            ip=ip,
        )
    )


async def list_for_assessment(session: AsyncSession, assessment_id: UUID) -> list[AuditLogRead]:
    statement = (
        select(AuditLog)
        .where(AuditLog.assessment_id == assessment_id)
        .options(joinedload(AuditLog.actor))
        .order_by(AuditLog.created_at.asc())
    )
    rows = (await session.scalars(statement)).all()
    return [
        AuditLogRead(
            id=row.id,
            assessment_id=row.assessment_id,
            actor_id=row.actor_id,
            actor_name=row.actor.display_name if isinstance(row.actor, User) else "未知用户",
            action=row.action,
            detail=row.detail,
            created_at=row.created_at,
        )
        for row in rows
    ]
