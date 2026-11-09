from __future__ import annotations

import asyncio
import json
import time
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.agent.runner import execute_agent_run
from app.api.deps import CurrentUser, DbSession, DoctorUser, request_ip
from app.db.session import SessionLocal
from app.models.agent import AgentRun, AgentRunStatus, AgentStep, AgentStepStatus
from app.schemas.agent import (
    AgentDecisionRequest,
    AgentFeedbackRead,
    AgentFeedbackRequest,
    AgentRunCreate,
    AgentRunQueueItem,
    AgentRunRead,
)
from app.services import agent_service

router = APIRouter()

_SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",
}


def _event(event: str, data: dict[str, Any], event_id: int | None = None) -> str:
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event}")
    lines.append(f"data: {json.dumps(data, ensure_ascii=False)}")
    return "\n".join(lines) + "\n\n"


def _step_payload(step: AgentStep) -> dict[str, Any]:
    return {
        "seq": step.seq,
        "node": step.node,
        "tool": step.tool_name,
        "status": step.status,
        "latency_ms": step.latency_ms,
        "input": step.input,
        "output": step.output,
    }


async def _run_events(run_id: UUID) -> AsyncIterator[str]:
    last_seq = 0
    waiting_sent = False
    event_id = 0
    started = time.monotonic()
    last_ping = time.monotonic()

    while True:
        async with SessionLocal() as session:
            run = await session.get(AgentRun, run_id)
            if run is None:
                yield _event("error", {"message": "AI 运行不存在"}, event_id + 1)
                return
            steps = (
                await session.scalars(
                    select(AgentStep)
                    .where(
                        AgentStep.run_id == run_id,
                        AgentStep.seq > last_seq,
                        AgentStep.status != AgentStepStatus.STARTED,
                    )
                    .order_by(AgentStep.seq.asc())
                )
            ).all()
            status = run.status
            output = dict(run.output or {})

        for step in steps:
            last_seq = step.seq
            event_id = max(event_id, step.seq)
            name = "tool" if step.tool_name else "node"
            yield _event(name, _step_payload(step), event_id)

        if status == AgentRunStatus.WAITING_HUMAN and not waiting_sent:
            waiting_sent = True
            event_id += 1
            yield _event(
                "draft",
                {"draft": output.get("draft"), "verification": output.get("verification")},
                event_id,
            )
            yield _event(
                "waiting",
                {
                    "draft": output.get("draft"),
                    "verification": output.get("verification"),
                    "instructions": "请医生复核后批准或拒绝；批准不会自动完成报告签核。",
                },
                event_id,
            )

        if status == AgentRunStatus.DONE:
            event_id += 1
            yield _event(
                "done",
                {
                    "status": output.get("status"),
                    "decision": output.get("decision"),
                    "rejection_reason": output.get("rejection_reason"),
                },
                event_id,
            )
            return

        if status == AgentRunStatus.FAILED:
            event_id += 1
            yield _event(
                "error",
                {"message": output.get("error") or "AI 运行失败"},
                event_id,
            )
            return

        now = time.monotonic()
        if now - last_ping >= 15:
            last_ping = now
            yield ": ping\n\n"
        if now - started > 600:
            yield _event("error", {"message": "SSE 订阅超时，请刷新运行状态"}, event_id + 1)
            return
        await asyncio.sleep(0.4)


@router.post("/runs", response_model=AgentRunRead, status_code=202)
async def create_run(
    payload: AgentRunCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    session: DbSession,
    user: DoctorUser,
) -> AgentRunRead:
    run = await agent_service.create_run(
        session,
        payload=payload,
        actor=user,
        ip=request_ip(request),
    )
    background_tasks.add_task(execute_agent_run, run.id)
    return run


@router.get("/runs", response_model=list[AgentRunQueueItem])
async def list_runs(
    session: DbSession,
    _: CurrentUser,
    assessment_id: UUID | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
) -> list[AgentRunQueueItem]:
    return await agent_service.list_runs(session, assessment_id=assessment_id, limit=limit)


@router.get("/runs/{run_id}", response_model=AgentRunRead)
async def get_run(run_id: UUID, session: DbSession, _: CurrentUser) -> AgentRunRead:
    return await agent_service.get_run(session, run_id)


@router.get("/runs/{run_id}/stream")
async def stream_run(run_id: UUID, session: DbSession, _: CurrentUser) -> StreamingResponse:
    await agent_service.get_run(session, run_id)
    return StreamingResponse(
        _run_events(run_id),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.post("/runs/{run_id}/approve", response_model=AgentRunRead)
async def approve_run(
    run_id: UUID,
    payload: AgentDecisionRequest,
    request: Request,
    session: DbSession,
    user: DoctorUser,
) -> AgentRunRead:
    return await agent_service.approve_run(
        session,
        run_id=run_id,
        payload=payload,
        actor=user,
        ip=request_ip(request),
    )


@router.post("/runs/{run_id}/feedback", response_model=AgentFeedbackRead)
async def add_feedback(
    run_id: UUID,
    payload: AgentFeedbackRequest,
    session: DbSession,
    user: DoctorUser,
) -> AgentFeedbackRead:
    return await agent_service.add_feedback(session, run_id=run_id, payload=payload, actor=user)
