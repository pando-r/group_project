from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.agent.llm import PROMPT_VERSION
from app.agent.validators import validate_draft
from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.models.agent import AgentFeedback, AgentRun, AgentRunStatus
from app.models.assessment import Assessment
from app.models.user import User
from app.rules import registry
from app.schemas.agent import (
    AgentDecisionRequest,
    AgentDraft,
    AgentFeedbackRead,
    AgentFeedbackRequest,
    AgentRunCreate,
    AgentRunQueueItem,
    AgentRunRead,
    AgentStepRead,
    VerificationResult,
)
from app.services.audit_service import add_audit
from app.services.deid_service import DeidentificationSession
from app.services.evidence_service import build_rule_evidence


def _disease_name(disease_id: str) -> str:
    try:
        return registry.get_rule(disease_id).definition.name
    except KeyError:
        return disease_id


def _run_output(run: AgentRun) -> dict[str, Any]:
    return run.output if isinstance(run.output, dict) else {}


def run_to_read(run: AgentRun, *, include_steps: bool = False) -> AgentRunRead:
    output = _run_output(run)
    disease_id = str(output.get("disease_id") or "")
    if not disease_id and run.assessment is not None:
        disease_id = run.assessment.disease_id
    draft: AgentDraft | None = None
    raw_draft = output.get("draft")
    if isinstance(raw_draft, dict):
        try:
            draft = AgentDraft.model_validate(raw_draft)
        except Exception:
            draft = None
    verification: VerificationResult | None = None
    raw_verification = output.get("verification")
    if isinstance(raw_verification, dict):
        try:
            verification = VerificationResult.model_validate(raw_verification)
        except Exception:
            verification = None

    steps: list[AgentStepRead] = []
    if include_steps:
        steps = [AgentStepRead.model_validate(step) for step in run.steps]

    return AgentRunRead(
        id=run.id,
        patient_id=run.patient_id,
        patient_name=run.patient.name,
        assessment_id=run.assessment_id,
        disease_id=disease_id,
        disease_name=_disease_name(disease_id),
        status=run.status,
        model=run.model,
        prompt_version=run.prompt_version,
        tokens_in=run.tokens_in,
        tokens_out=run.tokens_out,
        latency_ms=run.latency_ms,
        draft=draft,
        verification=verification,
        decision=output.get("decision"),
        rejection_reason=output.get("rejection_reason"),
        error=output.get("error"),
        created_at=run.created_at,
        updated_at=run.updated_at,
        steps=steps,
    )


async def get_assessment_context(session: AsyncSession, assessment_id: UUID) -> dict[str, Any]:
    statement = (
        select(Assessment).where(Assessment.id == assessment_id).options(selectinload(Assessment.patient))
    )
    assessment = await session.scalar(statement)
    if assessment is None:
        raise NotFoundError("评估不存在")
    patient = assessment.patient
    deid = DeidentificationSession(
        patient_name=patient.name,
        mrn=patient.mrn,
        patient_id=patient.id,
    )
    fields = assessment.inputs.get("fields") if isinstance(assessment.inputs, dict) else {}
    return {
        "assessment_id": str(assessment.id),
        "patient_token": deid.patient_token,
        "age": patient.age,
        "gender": patient.gender,
        "disease_id": assessment.disease_id,
        "disease_name": _disease_name(assessment.disease_id),
        "specialty": assessment.specialty,
        "status": assessment.status,
        "rule_version": assessment.model_version,
        "inputs": fields if isinstance(fields, dict) else {},
        "result": assessment.result,
    }


async def create_run(
    session: AsyncSession,
    *,
    payload: AgentRunCreate,
    actor: User,
    ip: str | None,
) -> AgentRunRead:
    assessment = await session.scalar(
        select(Assessment)
        .where(Assessment.id == payload.assessment_id)
        .options(selectinload(Assessment.patient))
    )
    if assessment is None:
        raise NotFoundError("评估不存在")

    if not settings.llm_mock and not settings.llm_api_key.strip():
        raise ValidationAppError(
            "未配置 LLM_API_KEY，无法调用 DeepSeek；请配置后重启服务，或设置 LLM_MOCK=1",
            data={"field": "llm_api_key"},
        )

    active = await session.scalar(
        select(AgentRun).where(
            AgentRun.assessment_id == assessment.id,
            AgentRun.status.in_([AgentRunStatus.RUNNING, AgentRunStatus.WAITING_HUMAN]),
        )
    )
    if active is not None:
        raise ConflictError("该评估已有进行中的 AI 运行", code="AGENT_RUN_ACTIVE")

    deid = DeidentificationSession(
        patient_name=assessment.patient.name,
        mrn=assessment.patient.mrn,
        patient_id=assessment.patient.id,
    )
    model_name = "mock-clinical-v1" if settings.llm_mock else settings.llm_model
    run = AgentRun(
        patient_id=assessment.patient_id,
        assessment_id=assessment.id,
        thread_id=uuid4().hex,
        status=AgentRunStatus.RUNNING,
        model=model_name,
        prompt_version=PROMPT_VERSION,
        input={
            "assessment_id": str(assessment.id),
            "patient_token": deid.patient_token,
            "disease_id": assessment.disease_id,
            "focus": deid.redact(payload.focus),
            "context": {"deidentified": True, "narrative_present": False},
        },
        created_by=actor.id,
    )
    session.add(run)
    await session.flush()
    add_audit(
        session,
        assessment_id=assessment.id,
        actor_id=actor.id,
        action="AGENT_RUN_CREATED",
        detail={
            "run_id": str(run.id),
            "model": model_name,
            "prompt_version": PROMPT_VERSION,
            "rule_version": assessment.model_version,
        },
        ip=ip,
    )
    await session.commit()

    created = await get_run(session, run.id)
    return created


async def get_run(session: AsyncSession, run_id: UUID) -> AgentRunRead:
    statement = (
        select(AgentRun)
        .where(AgentRun.id == run_id)
        .options(
            selectinload(AgentRun.patient),
            selectinload(AgentRun.assessment),
            selectinload(AgentRun.steps),
        )
    )
    run = await session.scalar(statement)
    if run is None:
        raise NotFoundError("AI 运行不存在")
    return run_to_read(run, include_steps=True)


async def list_runs(
    session: AsyncSession,
    *,
    assessment_id: UUID | None = None,
    limit: int = 20,
) -> list[AgentRunQueueItem]:
    statement = (
        select(AgentRun)
        .order_by(AgentRun.created_at.desc())
        .options(selectinload(AgentRun.assessment))
        .limit(limit)
    )
    if assessment_id is not None:
        statement = statement.where(AgentRun.assessment_id == assessment_id)
    runs = (await session.scalars(statement)).all()
    result: list[AgentRunQueueItem] = []
    for run in runs:
        disease_id = (
            run.assessment.disease_id
            if run.assessment is not None
            else str((run.output or {}).get("disease_id") or "")
        )
        result.append(
            AgentRunQueueItem(
                id=run.id,
                assessment_id=run.assessment_id,
                disease_id=disease_id,
                disease_name=_disease_name(disease_id),
                status=run.status,
                model=run.model,
                created_at=run.created_at,
            )
        )
    return result


async def approve_run(
    session: AsyncSession,
    *,
    run_id: UUID,
    payload: AgentDecisionRequest,
    actor: User,
    ip: str | None,
) -> AgentRunRead:
    statement = (
        select(AgentRun)
        .where(AgentRun.id == run_id)
        .options(selectinload(AgentRun.assessment), selectinload(AgentRun.patient))
    )
    run = await session.scalar(statement)
    if run is None:
        raise NotFoundError("AI 运行不存在")
    if run.status != AgentRunStatus.WAITING_HUMAN:
        raise ConflictError("该 AI 运行当前不等待医生审批", code="AGENT_NOT_WAITING")
    assessment = run.assessment
    if assessment is None:
        raise ConflictError("AI 运行缺少关联评估", code="AGENT_ASSESSMENT_MISSING")

    if payload.decision == "APPROVE" and payload.edited_draft is not None:
        evidence = build_rule_evidence(assessment.result)
        _, verification = validate_draft(
            payload.edited_draft,
            result=assessment.result,
            evidence=evidence,
            rewrite_rounds=0,
        )
        if verification.get("errors"):
            raise ValidationAppError(
                "编辑后的草稿未通过校验",
                data={"errors": verification["errors"]},
            )

    from app.agent.runner import resume_agent_run

    assessment_id = assessment.id
    current_run_id = run.id
    actor_id = actor.id
    await resume_agent_run(
        current_run_id,
        decision=payload.decision,
        note=payload.note,
        edited_draft=payload.edited_draft,
    )

    await session.rollback()
    refreshed = await get_run(session, current_run_id)
    if refreshed.status == AgentRunStatus.DONE:
        add_audit(
            session,
            assessment_id=assessment_id,
            actor_id=actor_id,
            action="AGENT_RUN_APPROVED" if payload.decision == "APPROVE" else "AGENT_RUN_REJECTED",
            detail={
                "run_id": str(current_run_id),
                "decision": payload.decision,
                "has_note": bool(payload.note),
                "has_edited_draft": payload.edited_draft is not None,
            },
            ip=ip,
        )
        await session.commit()
    return await get_run(session, current_run_id)


async def add_feedback(
    session: AsyncSession,
    *,
    run_id: UUID,
    payload: AgentFeedbackRequest,
    actor: User,
) -> AgentFeedbackRead:
    run = await session.get(AgentRun, run_id)
    if run is None:
        raise NotFoundError("AI 运行不存在")
    if run.status not in {AgentRunStatus.DONE, AgentRunStatus.FAILED}:
        raise ConflictError("运行尚未结束，暂不能评价", code="AGENT_NOT_FINISHED")

    feedback = await session.scalar(
        select(AgentFeedback).where(
            AgentFeedback.run_id == run_id,
            AgentFeedback.doctor_id == actor.id,
        )
    )
    if feedback is None:
        feedback = AgentFeedback(
            run_id=run_id,
            doctor_id=actor.id,
            rating=payload.rating,
            comment=payload.comment,
        )
        session.add(feedback)
    else:
        feedback.rating = payload.rating
        feedback.comment = payload.comment
        feedback.created_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(feedback)
    return AgentFeedbackRead(
        id=feedback.id,
        run_id=feedback.run_id,
        doctor_id=feedback.doctor_id,
        rating=feedback.rating,
        comment=feedback.comment,
        created_at=feedback.created_at,
    )
