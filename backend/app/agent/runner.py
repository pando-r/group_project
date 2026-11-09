from __future__ import annotations

import asyncio
import time
from typing import Any, cast
from uuid import UUID

import structlog
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.agent.graph import AgentContext, build_agent_graph
from app.agent.llm import ClinicalDraftModel, DeepSeekDraftModel, DraftModel
from app.agent.telemetry import DbStepRecorder, StepRecorder
from app.agent.tools import AgentTools
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.agent import AgentRun, AgentRunStatus
from app.services import agent_service, assessment_service
from app.services.evidence_service import build_rule_evidence

logger = structlog.get_logger("medrisk.agent.runner")


class AgentRuntime:
    def __init__(self) -> None:
        self._graph: Any = None
        self._checkpointer_cm: Any = None

    async def start(self) -> None:
        if self._graph is not None:
            return
        self._checkpointer_cm = AsyncSqliteSaver.from_conn_string(settings.agent_checkpoint_path)
        saver = await self._checkpointer_cm.__aenter__()
        await saver.setup()
        self._graph = build_agent_graph(saver)
        logger.info("agent_runtime_started", checkpoint_path=settings.agent_checkpoint_path)

    async def stop(self) -> None:
        if self._checkpointer_cm is not None:
            await self._checkpointer_cm.__aexit__(None, None, None)
        self._checkpointer_cm = None
        self._graph = None

    @property
    def graph(self) -> Any:
        if self._graph is None:
            raise RuntimeError("Agent runtime 尚未启动")
        return self._graph


agent_runtime = AgentRuntime()


def _status_from_snapshot(values: dict[str, Any], has_next: bool) -> str:
    if has_next:
        return AgentRunStatus.WAITING_HUMAN
    if values.get("failure_reason"):
        return AgentRunStatus.FAILED
    if values.get("decision") in {"APPROVE", "REJECT"}:
        return AgentRunStatus.DONE
    return AgentRunStatus.FAILED


def _output_from_values(values: dict[str, Any], status: str) -> dict[str, Any]:
    draft = values.get("final_draft") or values.get("draft")
    decision = values.get("decision")
    rejection = values.get("decision_note") if decision == "REJECT" else None
    if status == AgentRunStatus.WAITING_HUMAN:
        output_status = "waiting"
    elif status == AgentRunStatus.FAILED:
        output_status = "failed"
    elif decision == "APPROVE":
        output_status = "approved"
    else:
        output_status = "rejected"
    return {
        "status": output_status,
        "disease_id": values.get("disease_id"),
        "decision": decision,
        "draft": draft,
        "rejection_reason": rejection,
        "verification": values.get("verification"),
        "usage": {
            "tokens_in": int(values.get("tokens_in", 0)),
            "tokens_out": int(values.get("tokens_out", 0)),
        },
        "error": values.get("failure_reason") if status == AgentRunStatus.FAILED else None,
    }


def _build_tools(
    session: Any,
    recorder: StepRecorder,
) -> AgentTools:
    async def get_context(assessment_id: str) -> dict[str, Any]:
        return await agent_service.get_assessment_context(session, UUID(assessment_id))

    async def evaluate(disease_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        return assessment_service.evaluate_deterministic(disease_id, inputs)

    async def get_evidence(result: dict[str, Any]) -> list[dict[str, Any]]:
        return build_rule_evidence(result)

    return AgentTools(
        recorder=recorder,
        get_context=get_context,
        evaluate=evaluate,
        get_evidence=get_evidence,
    )


def _model_for(run: AgentRun) -> DraftModel:
    if settings.llm_mock:
        return ClinicalDraftModel(model_name=run.model)
    return DeepSeekDraftModel(
        model_name=run.model,
        api_key=settings.llm_api_key,
        base_url=settings.llm_base_url,
        timeout=settings.llm_timeout,
        max_retries=settings.llm_max_retries,
        temperature=settings.llm_temperature,
        max_output_tokens=settings.llm_max_output_tokens,
        thinking=settings.llm_thinking,
        backoff_seconds=settings.llm_backoff_seconds,
    )


async def _load_run(session: Any, run_id: UUID) -> AgentRun | None:
    return cast(
        AgentRun | None,
        await session.scalar(
            select(AgentRun)
            .where(AgentRun.id == run_id)
            .options(selectinload(AgentRun.patient), selectinload(AgentRun.assessment))
        ),
    )


async def _mark_failed(run_id: UUID, message: str, latency_ms: int | None = None) -> None:
    async with SessionLocal() as session:
        run = await _load_run(session, run_id)
        if run is None:
            return
        run.status = AgentRunStatus.FAILED
        output = dict(run.output or {})
        output.update({"status": "failed", "error": message})
        run.output = output
        if latency_ms is not None:
            run.latency_ms = latency_ms
        await session.commit()


async def _execute(run_id: UUID) -> None:
    async with SessionLocal() as session:
        run = await _load_run(session, run_id)
        if run is None:
            logger.warning("agent_run_missing", run_id=str(run_id))
            return
        if run.status != AgentRunStatus.RUNNING:
            return
        if run.assessment_id is None:
            raise RuntimeError("AI 运行缺少关联评估")

        run_input = run.input if isinstance(run.input, dict) else {}
        recorder = DbStepRecorder(run.id)
        tools = _build_tools(session, recorder)
        model = _model_for(run)
        context = AgentContext(tools=tools, model=model, recorder=recorder, narrative=None)
        config = {
            "configurable": {"thread_id": run.thread_id},
            "recursion_limit": 40,
        }
        initial_state = {
            "run_id": str(run.id),
            "assessment_id": str(run.assessment_id),
            "patient_token": str(run_input.get("patient_token", "")),
            "disease_id": str(run_input.get("disease_id", "")),
            "rewrite_rounds": 0,
            "tokens_in": 0,
            "tokens_out": 0,
        }

        started = time.perf_counter()
        async for _chunk in agent_runtime.graph.astream(
            initial_state,
            config,
            context=context,
            stream_mode="updates",
        ):
            pass
        snapshot = await agent_runtime.graph.aget_state(config)
        values = dict(snapshot.values)
        status = _status_from_snapshot(values, bool(snapshot.next))
        run.status = status
        run.output = _output_from_values(values, status)
        run.tokens_in = int(values.get("tokens_in", 0)) or None
        run.tokens_out = int(values.get("tokens_out", 0)) or None
        run.latency_ms = int((time.perf_counter() - started) * 1000)
        await session.commit()
        logger.info(
            "agent_run_finished",
            run_id=str(run.id),
            status=status,
            tool_calls=tools.calls,
        )


async def execute_agent_run(run_id: UUID) -> None:
    try:
        await asyncio.wait_for(_execute(run_id), timeout=settings.agent_run_timeout_seconds)
    except TimeoutError:
        await _mark_failed(run_id, "运行超过 90 秒上限，已终止")
    except Exception as exc:
        logger.exception("agent_run_failed", run_id=str(run_id))
        await _mark_failed(run_id, f"运行失败：{exc}")


async def resume_agent_run(
    run_id: UUID,
    *,
    decision: str,
    note: str | None,
    edited_draft: dict[str, Any] | None,
) -> None:
    try:
        await asyncio.wait_for(
            _resume(run_id, decision=decision, note=note, edited_draft=edited_draft),
            timeout=settings.agent_run_timeout_seconds,
        )
    except TimeoutError:
        await _mark_failed(run_id, "审批恢复超过 90 秒上限，已终止")
    except Exception as exc:
        logger.exception("agent_resume_failed", run_id=str(run_id))
        await _mark_failed(run_id, f"审批恢复失败：{exc}")


async def _resume(
    run_id: UUID,
    *,
    decision: str,
    note: str | None,
    edited_draft: dict[str, Any] | None,
) -> None:
    async with SessionLocal() as session:
        run = await _load_run(session, run_id)
        if run is None:
            raise RuntimeError("AI 运行不存在")
        if run.status != AgentRunStatus.WAITING_HUMAN:
            raise RuntimeError("AI 运行不在等待审批状态")

        recorder = DbStepRecorder(run.id)
        tools = _build_tools(session, recorder)
        model = _model_for(run)
        context = AgentContext(tools=tools, model=model, recorder=recorder, narrative=None)
        config = {
            "configurable": {"thread_id": run.thread_id},
            "recursion_limit": 40,
        }
        resume_payload = {
            "decision": decision,
            "note": note,
            "edited_draft": edited_draft,
        }
        started = time.perf_counter()
        async for _chunk in agent_runtime.graph.astream(
            Command(resume=resume_payload),
            config,
            context=context,
            stream_mode="updates",
        ):
            pass
        snapshot = await agent_runtime.graph.aget_state(config)
        values = dict(snapshot.values)
        status = _status_from_snapshot(values, bool(snapshot.next))
        run.status = status
        run.output = _output_from_values(values, status)
        run.tokens_in = int(values.get("tokens_in", 0)) or None
        run.tokens_out = int(values.get("tokens_out", 0)) or None
        run.latency_ms = int(run.latency_ms or 0) + int((time.perf_counter() - started) * 1000)
        await session.commit()
        logger.info("agent_run_resumed", run_id=str(run.id), status=status, decision=decision)
