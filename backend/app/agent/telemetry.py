from __future__ import annotations

import asyncio
import json
from typing import Any, Protocol
from uuid import UUID, uuid4

import structlog

from app.core.logging import redact_payload
from app.db.session import SessionLocal
from app.models.agent import AgentStep, AgentStepStatus

logger = structlog.get_logger("medrisk.agent.telemetry")

_MAX_TEXT = 4000


def _bounded(value: Any) -> Any:
    if isinstance(value, str):
        return value if len(value) <= _MAX_TEXT else value[:_MAX_TEXT] + "…[truncated]"
    if isinstance(value, dict):
        return {str(key): _bounded(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_bounded(item) for item in value]
    return value


def safe_telemetry_payload(value: Any) -> Any:
    redacted = redact_payload(value)
    try:
        json.dumps(redacted, ensure_ascii=False)
    except TypeError:
        redacted = json.loads(json.dumps(redacted, ensure_ascii=False, default=str))
    return _bounded(redacted)


class StepRecorder(Protocol):
    async def start_step(
        self,
        *,
        node: str,
        tool_name: str | None = None,
        input: dict[str, Any] | None = None,
    ) -> UUID: ...

    async def finish_step(
        self,
        step_id: UUID,
        *,
        status: AgentStepStatus,
        output: dict[str, Any] | None,
        latency_ms: int | None,
    ) -> None: ...


class NullRecorder:
    async def start_step(
        self,
        *,
        node: str,
        tool_name: str | None = None,
        input: dict[str, Any] | None = None,
    ) -> UUID:
        return uuid4()

    async def finish_step(
        self,
        step_id: UUID,
        *,
        status: AgentStepStatus,
        output: dict[str, Any] | None,
        latency_ms: int | None,
    ) -> None:
        return None


class DbStepRecorder:
    """Persist redacted step telemetry without sharing the business session."""

    def __init__(self, run_id: UUID) -> None:
        self.run_id = run_id
        self._seq = 0
        self._lock = asyncio.Lock()

    async def _next_seq(self) -> int:
        async with self._lock:
            if self._seq == 0:
                async with SessionLocal() as session:
                    from sqlalchemy import func, select

                    current = await session.scalar(
                        select(func.max(AgentStep.seq)).where(AgentStep.run_id == self.run_id)
                    )
                    self._seq = int(current or 0)
            self._seq += 1
            return self._seq

    async def start_step(
        self,
        *,
        node: str,
        tool_name: str | None = None,
        input: dict[str, Any] | None = None,
    ) -> UUID:
        seq = await self._next_seq()
        step_id = uuid4()
        try:
            async with SessionLocal() as session:
                session.add(
                    AgentStep(
                        id=step_id,
                        run_id=self.run_id,
                        seq=seq,
                        node=node,
                        tool_name=tool_name,
                        input=safe_telemetry_payload(input) if input is not None else None,
                        status=AgentStepStatus.STARTED,
                    )
                )
                await session.commit()
        except Exception:
            logger.exception("agent_step_start_failed", run_id=str(self.run_id), seq=seq)
        return step_id

    async def finish_step(
        self,
        step_id: UUID,
        *,
        status: AgentStepStatus,
        output: dict[str, Any] | None,
        latency_ms: int | None,
    ) -> None:
        try:
            async with SessionLocal() as session:
                step = await session.get(AgentStep, step_id)
                if step is None:
                    return
                step.status = status
                step.output = safe_telemetry_payload(output) if output is not None else None
                step.latency_ms = latency_ms
                await session.commit()
        except Exception:
            logger.exception(
                "agent_step_finish_failed",
                run_id=str(self.run_id),
                step_id=str(step_id),
            )
