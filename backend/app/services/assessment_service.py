from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.models.assessment import Assessment, AssessmentStatus
from app.models.patient import Patient
from app.models.rule_version import RuleVersion
from app.models.user import User
from app.rules import registry
from app.rules.base import RuleInputError, validate_fields
from app.rules.constants import RULE_VERSION_INFO
from app.schemas.assessment import AssessmentCreate, AssessmentRead, ConfirmAssessmentRequest
from app.services.audit_service import add_audit
from app.services.presenters import assessment_to_read


async def _fetch_readable(session: AsyncSession, assessment_id: UUID) -> Assessment | None:
    statement = (
        select(Assessment)
        .where(Assessment.id == assessment_id)
        .options(
            selectinload(Assessment.patient),
            selectinload(Assessment.confirmed_by_user),
        )
    )
    return await session.scalar(statement)


def evaluate_deterministic(disease_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
    """Pure wrapper around the rule registry, shared by the manual and Agent paths."""

    try:
        rule = registry.get_rule(disease_id)
    except KeyError as exc:
        raise ValidationAppError("未知病种，无法评估", data={"field": "disease_id"}) from exc
    try:
        cleaned = validate_fields(rule.definition, inputs)
        evaluation = rule.evaluator(cleaned)
    except RuleInputError as exc:
        raise ValidationAppError(exc.message, data={"field": exc.field, "message": exc.message}) from exc
    return {"inputs": cleaned, "result": evaluation.model_dump(mode="json")}


async def _ensure_rule_version(session: AsyncSession) -> RuleVersion:
    version = await session.scalar(
        select(RuleVersion).where(RuleVersion.version == registry.ACTIVE_RULE_VERSION)
    )
    if version is not None:
        return version
    version = RuleVersion(
        version=RULE_VERSION_INFO.version,
        changelog=RULE_VERSION_INFO.changelog,
    )
    session.add(version)
    await session.flush()
    return version


async def create_assessment(
    session: AsyncSession,
    *,
    payload: AssessmentCreate,
    actor: User,
    ip: str | None,
) -> AssessmentRead:
    try:
        rule = registry.get_rule(payload.disease_id)
    except KeyError as exc:
        raise ValidationAppError("未知病种，无法评估", data={"field": "disease_id"}) from exc

    patient = await session.get(Patient, payload.patient_id)
    if patient is None:
        raise NotFoundError("患者不存在")

    try:
        cleaned = validate_fields(rule.definition, payload.inputs)
        evaluation = rule.evaluator(cleaned)
    except RuleInputError as exc:
        raise ValidationAppError(exc.message, data={"field": exc.field, "message": exc.message}) from exc

    await _ensure_rule_version(session)
    assessment = Assessment(
        patient_id=patient.id,
        specialty=rule.definition.specialty,
        disease_id=rule.definition.id,
        inputs={
            "fields": cleaned,
            "context": {
                "source": "manual",
                "deidentified": True,
            },
        },
        result=evaluation.model_dump(mode="json"),
        status=AssessmentStatus.PENDING,
        model_version=registry.ACTIVE_RULE_VERSION,
    )
    assessment.patient = patient
    assessment.confirmed_by_user = None
    session.add(assessment)
    await session.flush()
    add_audit(
        session,
        assessment_id=assessment.id,
        actor_id=actor.id,
        action="ASSESSMENT_CREATED",
        detail={
            "disease_id": assessment.disease_id,
            "severity": evaluation.severity.grade,
            "risk_tier": evaluation.risk.tier,
            "rule_version": assessment.model_version,
        },
        ip=ip,
    )
    await session.commit()

    created = await _fetch_readable(session, assessment.id)
    if created is None:
        raise NotFoundError("评估创建失败")
    return assessment_to_read(created)


async def get_assessment(session: AsyncSession, assessment_id: UUID) -> AssessmentRead:
    assessment = await _fetch_readable(session, assessment_id)
    if assessment is None:
        raise NotFoundError("评估不存在")
    return assessment_to_read(assessment)


async def confirm_assessment(
    session: AsyncSession,
    *,
    assessment_id: UUID,
    payload: ConfirmAssessmentRequest,
    actor: User,
    ip: str | None,
) -> AssessmentRead:
    assessment = await _fetch_readable(session, assessment_id)
    if assessment is None:
        raise NotFoundError("评估不存在")
    if assessment.status == AssessmentStatus.CONFIRMED:
        raise ConflictError("该评估已确认，不能重复签字", code="ALREADY_CONFIRMED")

    assessment.status = AssessmentStatus.CONFIRMED
    assessment.decision = payload.decision
    assessment.note = payload.note
    assessment.confirmed_by = actor.id
    assessment.confirmed_by_user = actor
    assessment.confirmed_at = datetime.now(UTC)
    add_audit(
        session,
        assessment_id=assessment.id,
        actor_id=actor.id,
        action="ASSESSMENT_CONFIRMED",
        detail={
            "decision": payload.decision,
            "has_note": bool(payload.note),
            "previous_status": AssessmentStatus.PENDING.value,
            "rule_version": assessment.model_version,
        },
        ip=ip,
    )
    await session.commit()

    updated = await _fetch_readable(session, assessment.id)
    if updated is None:
        raise NotFoundError("评估不存在")
    return assessment_to_read(updated)
