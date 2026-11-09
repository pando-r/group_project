from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Request

from app.api.deps import CurrentUser, DbSession, DoctorUser, request_ip
from app.schemas.assessment import (
    AssessmentCreate,
    AssessmentRead,
    ConfirmAssessmentRequest,
)
from app.services import assessment_service

router = APIRouter()


@router.post("", response_model=AssessmentRead, status_code=201)
async def create_assessment(
    payload: AssessmentCreate,
    request: Request,
    session: DbSession,
    user: DoctorUser,
) -> AssessmentRead:
    return await assessment_service.create_assessment(
        session, payload=payload, actor=user, ip=request_ip(request)
    )


@router.get("/{assessment_id}", response_model=AssessmentRead)
async def get_assessment(assessment_id: UUID, session: DbSession, _: CurrentUser) -> AssessmentRead:
    return await assessment_service.get_assessment(session, assessment_id)


@router.post("/{assessment_id}/confirm", response_model=AssessmentRead)
async def confirm_assessment(
    assessment_id: UUID,
    payload: ConfirmAssessmentRequest,
    request: Request,
    session: DbSession,
    user: DoctorUser,
) -> AssessmentRead:
    return await assessment_service.confirm_assessment(
        session,
        assessment_id=assessment_id,
        payload=payload,
        actor=user,
        ip=request_ip(request),
    )
