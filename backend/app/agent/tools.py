from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any, TypeVar

from app.agent.telemetry import StepRecorder
from app.core.config import settings
from app.models.agent import AgentStepStatus

MAX_TOOL_CALLS_PER_RUN = settings.agent_max_tool_calls
TOOL_TIMEOUT_SECONDS = settings.agent_tool_timeout_seconds
TOOL_RETRIES = 1

T = TypeVar("T")


class ToolBudgetExceeded(RuntimeError):
    pass


class ToolExecutionError(RuntimeError):
    pass


@dataclass
class AgentTools:
    """Thin tool adapters. Services are injected; no database session lives here."""

    recorder: StepRecorder
    get_context: Callable[[str], Awaitable[dict[str, Any]]]
    evaluate: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]]
    get_evidence: Callable[[dict[str, Any]], Awaitable[list[dict[str, Any]]]]
    calls: int = 0

    async def get_assessment_context(self, assessment_id: str) -> dict[str, Any]:
        return await self._call(
            "get_assessment_context",
            {"assessment_id": assessment_id},
            lambda: self.get_context(assessment_id),
        )

    async def evaluate_risk(self, disease_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        return await self._call(
            "evaluate_risk",
            {"disease_id": disease_id, "field_count": len(inputs)},
            lambda: self.evaluate(disease_id, inputs),
        )

    async def fetch_evidence(self, result: dict[str, Any]) -> list[dict[str, Any]]:
        summary = {
            "disease_id": result.get("meta", {}).get("disease_id"),
            "rule_version": result.get("meta", {}).get("rule_version"),
        }
        return await self._call(
            "fetch_rule_evidence",
            summary,
            lambda: self.get_evidence(result),
        )

    async def _call(
        self,
        name: str,
        payload: dict[str, Any],
        call: Callable[[], Awaitable[Any]],
    ) -> Any:
        if self.calls >= MAX_TOOL_CALLS_PER_RUN:
            raise ToolBudgetExceeded(f"单次运行工具调用超过 {MAX_TOOL_CALLS_PER_RUN} 次")
        self.calls += 1
        step_id = await self.recorder.start_step(node="tool", tool_name=name, input=payload)
        started = time.perf_counter()
        last_error: Exception | None = None
        for attempt in range(TOOL_RETRIES + 1):
            try:
                result = await asyncio.wait_for(call(), timeout=TOOL_TIMEOUT_SECONDS)
                latency = round((time.perf_counter() - started) * 1000, 1)
                await self.recorder.finish_step(
                    step_id,
                    status=AgentStepStatus.OK,
                    output={"ok": True, "attempt": attempt + 1, "result": result},
                    latency_ms=int(latency),
                )
                return result
            except TimeoutError as exc:
                last_error = exc
            except Exception as exc:
                last_error = exc
        latency = round((time.perf_counter() - started) * 1000, 1)
        message = str(last_error) if last_error else "工具调用失败"
        await self.recorder.finish_step(
            step_id,
            status=AgentStepStatus.ERROR,
            output={"ok": False, "error": message},
            latency_ms=int(latency),
        )
        raise ToolExecutionError(f"{name} 调用失败：{message}") from last_error
