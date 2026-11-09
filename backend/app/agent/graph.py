from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, cast

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.errors import GraphInterrupt
from langgraph.graph import END, START, StateGraph
from langgraph.runtime import Runtime
from langgraph.types import interrupt

from app.agent.llm import DraftModel, build_draft_prompt
from app.agent.state import AgentState
from app.agent.telemetry import StepRecorder
from app.agent.tools import AgentTools
from app.agent.validators import validate_draft
from app.models.agent import AgentStepStatus

MAX_REWRITES = 2


@dataclass
class AgentContext:
    tools: AgentTools
    model: DraftModel
    recorder: StepRecorder
    narrative: str | None = None


def _state_snapshot(state: AgentState) -> dict[str, Any]:
    return {
        key: state.get(key)
        for key in (
            "assessment_id",
            "disease_id",
            "rewrite_rounds",
            "validation_errors",
            "decision",
            "failure_reason",
        )
        if state.get(key) is not None
    }


def _instrument(name: str, node):  # type: ignore[no-untyped-def]
    async def wrapped(state: AgentState, runtime: Runtime[AgentContext]) -> dict[str, Any]:
        recorder = runtime.context.recorder
        step_id = await recorder.start_step(node=name, input=_state_snapshot(state))
        started = time.perf_counter()
        try:
            update = await node(state, runtime)
        except GraphInterrupt:
            await recorder.finish_step(
                step_id,
                status=AgentStepStatus.OK,
                output={"waiting": True},
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
            raise
        except Exception as exc:
            await recorder.finish_step(
                step_id,
                status=AgentStepStatus.ERROR,
                output={"error": str(exc)},
                latency_ms=int((time.perf_counter() - started) * 1000),
            )
            raise
        await recorder.finish_step(
            step_id,
            status=AgentStepStatus.OK,
            output=update,
            latency_ms=int((time.perf_counter() - started) * 1000),
        )
        return cast(dict[str, Any], update)

    return wrapped


async def intake(state: AgentState, runtime: Runtime[AgentContext]) -> dict[str, Any]:
    context = await runtime.context.tools.get_assessment_context(state["assessment_id"])
    if not context.get("result") or not context.get("patient_token"):
        raise ValueError("评估上下文不完整，无法启动 AI 解读")
    return {
        "patient_context": context,
        "patient_token": str(context["patient_token"]),
        "disease_id": str(context["disease_id"]),
        "disease_name": str(context.get("disease_name", "")),
    }


async def collect(state: AgentState, _: Runtime[AgentContext]) -> dict[str, Any]:
    context = state.get("patient_context", {})
    inputs = context.get("inputs") or {}
    if not isinstance(inputs, dict) or not inputs:
        raise ValueError("评估缺少结构化输入字段")
    return {"cleaned_inputs": inputs}


async def compute(state: AgentState, runtime: Runtime[AgentContext]) -> dict[str, Any]:
    context = state.get("patient_context", {})
    inputs = state.get("cleaned_inputs") or {}
    evaluation = await runtime.context.tools.evaluate_risk(state["disease_id"], inputs)
    recomputed = evaluation.get("result")
    stored = context.get("result")
    if not isinstance(recomputed, dict):
        raise ValueError("规则引擎未返回有效结果")
    if isinstance(stored, dict) and recomputed != stored:
        raise ValueError("确定性规则结果与已保存评估不一致，已终止 AI 解读")
    return {
        "cleaned_inputs": evaluation.get("inputs", inputs),
        "result": recomputed,
    }


async def evidence(state: AgentState, runtime: Runtime[AgentContext]) -> dict[str, Any]:
    items = await runtime.context.tools.fetch_evidence(state["result"])
    return {"evidence": items}


async def draft(state: AgentState, runtime: Runtime[AgentContext]) -> dict[str, Any]:
    existing = state.get("draft")
    rounds = int(state.get("rewrite_rounds", 0)) + (1 if existing is not None else 0)
    prompt = build_draft_prompt(
        result=state["result"],
        evidence=state.get("evidence", []),
        patient_context=state.get("patient_context", {}),
        validation_errors=state.get("validation_errors"),
        narrative=runtime.context.narrative,
    )
    generated = await runtime.context.model.generate(
        prompt,
        result=state["result"],
        evidence=state.get("evidence", []),
    )
    return {
        "draft": generated.draft,
        "rewrite_rounds": rounds,
        "tokens_in": int(state.get("tokens_in", 0)) + generated.tokens_in,
        "tokens_out": int(state.get("tokens_out", 0)) + generated.tokens_out,
    }


async def verify(state: AgentState, _: Runtime[AgentContext]) -> dict[str, Any]:
    rounds = int(state.get("rewrite_rounds", 0))
    _draft, verification = validate_draft(
        state.get("draft"),
        result=state["result"],
        evidence=state.get("evidence", []),
        rewrite_rounds=rounds,
    )
    return {
        "verification": verification,
        "validation_errors": list(verification.get("errors", [])),
    }


def route_after_verify(state: AgentState) -> str:
    if not state.get("validation_errors"):
        return "review"
    if int(state.get("rewrite_rounds", 0)) < MAX_REWRITES:
        return "draft"
    return "failed"


async def review(state: AgentState, _: Runtime[AgentContext]) -> dict[str, Any]:
    decision = interrupt(
        {
            "draft": state.get("draft"),
            "verification": state.get("verification"),
            "instructions": "医生可批准、拒绝或提交编辑后的草稿。批准不会自动完成报告签核。",
        }
    )
    if not isinstance(decision, dict):
        raise ValueError("审批决定格式无效")
    return {
        "decision": str(decision.get("decision", "")),
        "decision_note": decision.get("note"),
        "edited_draft": decision.get("edited_draft"),
    }


async def sign(state: AgentState, _: Runtime[AgentContext]) -> dict[str, Any]:
    decision = state.get("decision")
    if decision == "REJECT":
        return {
            "approved": False,
            "final_draft": state.get("draft"),
            "failure_reason": None,
        }
    if decision != "APPROVE":
        raise ValueError("未知审批决定")

    candidate = state.get("edited_draft") or state.get("draft")
    if isinstance(candidate, dict) and candidate != state.get("draft"):
        _draft, verification = validate_draft(
            candidate,
            result=state["result"],
            evidence=state.get("evidence", []),
            rewrite_rounds=int(state.get("rewrite_rounds", 0)),
        )
        if verification.get("errors"):
            raise ValueError("编辑后的草稿未通过校验，不能批准")
    return {
        "approved": True,
        "final_draft": candidate,
        "failure_reason": None,
    }


async def failed(state: AgentState, _: Runtime[AgentContext]) -> dict[str, Any]:
    errors = state.get("validation_errors") or []
    reason = f"草稿连续 {MAX_REWRITES + 1} 次未通过校验"
    if errors:
        reason = f"{reason}：{'；'.join(errors[:3])}"
    return {"failure_reason": reason, "approved": False}


def build_agent_graph(checkpointer: BaseCheckpointSaver[Any] | None = None):  # type: ignore[no-untyped-def]
    builder = StateGraph(AgentState, context_schema=AgentContext)
    builder.add_node("intake", _instrument("intake", intake))
    builder.add_node("collect", _instrument("collect", collect))
    builder.add_node("compute", _instrument("compute", compute))
    builder.add_node("evidence", _instrument("evidence", evidence))
    builder.add_node("draft", _instrument("draft", draft))
    builder.add_node("verify", _instrument("verify", verify))
    builder.add_node("review", _instrument("review", review))
    builder.add_node("sign", _instrument("sign", sign))
    builder.add_node("failed", _instrument("failed", failed))

    builder.add_edge(START, "intake")
    builder.add_edge("intake", "collect")
    builder.add_edge("collect", "compute")
    builder.add_edge("compute", "evidence")
    builder.add_edge("evidence", "draft")
    builder.add_edge("draft", "verify")
    builder.add_conditional_edges(
        "verify",
        route_after_verify,
        {"draft": "draft", "review": "review", "failed": "failed"},
    )
    builder.add_edge("review", "sign")
    builder.add_edge("sign", END)
    builder.add_edge("failed", END)
    return builder.compile(checkpointer=checkpointer)
