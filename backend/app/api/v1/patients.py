from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Query, Response

from app.api.deps import CurrentUser, DbSession, DoctorUser
from app.schemas.common import PageResponse
from app.schemas.patient import (
    PatientCreate,
    PatientDetail,
    PatientListItem,
    PatientSummary,
)
from app.services import patient_service
from app.services.presenters import patient_summary

router = APIRouter()


@router.get("", response_model=PageResponse[PatientListItem])
async def list_patients(
    session: DbSession,
    _: CurrentUser,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    q: str | None = Query(default=None, max_length=100),
    specialty: str | None = Query(default=None, max_length=32),
    status: str | None = Query(default=None, pattern="^(PENDING|CONFIRMED)$"),
    risk: str | None = Query(default=None, max_length=64),
) -> PageResponse[PatientListItem]:
    return await patient_service.list_patients(
        session,
        page=page,
        size=size,
        query=q,
        specialty=specialty,
        status=status,
        risk=risk,
    )


@router.get("/export.csv")
async def export_patients_csv(
    session: DbSession,
    _: CurrentUser,
    q: str | None = Query(default=None, max_length=100),
    specialty: str | None = Query(default=None, max_length=32),
    status: str | None = Query(default=None, pattern="^(PENDING|CONFIRMED)$"),
    risk: str | None = Query(default=None, max_length=64),
) -> Response:
    content = await patient_service.export_csv(
        session, query=q, specialty=specialty, status=status, risk=risk
    )
    return Response(
        content="﻿" + content,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="medrisk-patients.csv"'},
    )


@router.post("", response_model=PatientSummary, status_code=201)
async def create_patient(payload: PatientCreate, session: DbSession, _: DoctorUser) -> PatientSummary:
    patient = await patient_service.create_patient(session, payload)
    return patient_summary(patient)


@router.get("/{patient_id}", response_model=PatientDetail)
async def get_patient(patient_id: UUID, session: DbSession, _: CurrentUser) -> PatientDetail:
    return await patient_service.get_patient_detail(session, patient_id)
