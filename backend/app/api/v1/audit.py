from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.audit import AuditLogRead
from app.services import audit_service

router = APIRouter()


@router.get("", response_model=list[AuditLogRead])
async def list_audit(
    session: DbSession,
    _: CurrentUser,
    assessment_id: UUID = Query(...),
) -> list[AuditLogRead]:
    return await audit_service.list_for_assessment(session, assessment_id)
