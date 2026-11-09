from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError
from app.models.patient import Patient
from app.schemas.common import PageResponse
from app.schemas.patient import (
    PatientCreate,
    PatientDetail,
    PatientListItem,
    RiskPoint,
)
from app.services.presenters import assessment_to_brief, patient_summary


def _latest(patient: Patient):
    return patient.assessments[0] if patient.assessments else None


def _matches(
    patient: Patient,
    *,
    query: str | None,
    specialty: str | None,
    status: str | None,
    risk: str | None,
) -> bool:
    if query:
        needle = query.strip().lower()
        if needle and needle not in patient.name.lower() and needle not in patient.mrn.lower():
            return False
    latest = _latest(patient)
    if specialty and (latest is None or latest.specialty != specialty):
        return False
    if status and (latest is None or latest.status != status):
        return False
    if risk:
        tiers = {part.strip() for part in risk.split(",") if part.strip()}
        latest_risk = (latest.result or {}).get("risk", {}) if latest else {}
        if not tiers or latest is None or latest_risk.get("tier") not in tiers:
            return False
    return True


async def _all_patients(session: AsyncSession) -> list[Patient]:
    statement = select(Patient).options(selectinload(Patient.assessments)).order_by(Patient.created_at.desc())
    return list((await session.scalars(statement)).all())


async def list_patients(
    session: AsyncSession,
    *,
    page: int,
    size: int,
    query: str | None = None,
    specialty: str | None = None,
    status: str | None = None,
    risk: str | None = None,
) -> PageResponse[PatientListItem]:
    patients = [
        patient
        for patient in await _all_patients(session)
        if _matches(patient, query=query, specialty=specialty, status=status, risk=risk)
    ]
    patients.sort(
        key=lambda patient: _latest(patient).created_at if _latest(patient) else patient.created_at,
        reverse=True,
    )
    total = len(patients)
    start = (page - 1) * size
    records = [
        PatientListItem(
            **patient_summary(patient).model_dump(),
            last_assessment=(assessment_to_brief(_latest(patient)) if _latest(patient) else None),
        )
        for patient in patients[start : start + size]
    ]
    return PageResponse[PatientListItem](page=page, size=size, total=total, records=records)


async def get_patient_detail(session: AsyncSession, patient_id: UUID) -> PatientDetail:
    statement = select(Patient).where(Patient.id == patient_id).options(selectinload(Patient.assessments))
    patient = await session.scalar(statement)
    if patient is None:
        raise NotFoundError("患者不存在")

    ordered = sorted(patient.assessments, key=lambda item: item.created_at)
    trend = [
        RiskPoint(
            assessment_id=assessment.id,
            disease_name=assessment_to_brief(assessment).disease_name,
            created_at=assessment.created_at,
            risk_percent=assessment_to_brief(assessment).risk_percent,
            severity_level=assessment_to_brief(assessment).severity_level,
        )
        for assessment in ordered
    ]
    return PatientDetail(
        **patient_summary(patient).model_dump(),
        assessments=[assessment_to_brief(assessment) for assessment in reversed(ordered)],
        risk_trend=trend,
    )


async def create_patient(session: AsyncSession, payload: PatientCreate) -> Patient:
    existing = await session.scalar(select(Patient).where(Patient.mrn == payload.mrn))
    if existing is not None:
        raise ConflictError("病历号已存在", code="MRN_EXISTS")

    patient = Patient(
        mrn=payload.mrn,
        name=payload.name,
        gender=payload.gender.value,
        birth_date=payload.birth_date,
    )
    session.add(patient)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise ConflictError("病历号已存在", code="MRN_EXISTS") from exc
    await session.refresh(patient)
    return patient


def _filtered_for_export(
    patients: Iterable[Patient],
    *,
    query: str | None,
    specialty: str | None,
    status: str | None,
    risk: str | None,
) -> list[Patient]:
    return [
        patient
        for patient in patients
        if _matches(patient, query=query, specialty=specialty, status=status, risk=risk)
    ]


async def export_csv(
    session: AsyncSession,
    *,
    query: str | None = None,
    specialty: str | None = None,
    status: str | None = None,
    risk: str | None = None,
) -> str:
    patients = _filtered_for_export(
        await _all_patients(session),
        query=query,
        specialty=specialty,
        status=status,
        risk=risk,
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "病历号",
            "姓名",
            "性别",
            "出生日期",
            "年龄",
            "最近评估病种",
            "严重程度",
            "风险百分比",
            "状态",
            "评估时间",
        ]
    )
    for patient in patients:
        latest = _latest(patient)
        brief = assessment_to_brief(latest) if latest else None
        writer.writerow(
            [
                patient.mrn,
                patient.name,
                patient.gender,
                patient.birth_date.isoformat(),
                patient.age,
                brief.disease_name if brief else "",
                brief.severity_grade if brief else "",
                f"{brief.risk_percent:.1f}" if brief else "",
                brief.status if brief else "未评估",
                brief.created_at.isoformat() if brief else "",
            ]
        )
    return buffer.getvalue()
