from __future__ import annotations

from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from app.agent.graph import AgentContext, build_agent_graph
from app.agent.llm import ClinicalDraftModel
from app.agent.telemetry import NullRecorder
from app.agent.tools import AgentTools
from app.services.assessment_service import evaluate_deterministic
from app.services.evidence_service import build_rule_evidence


def _tools(context: dict[str, Any], recorder: NullRecorder) -> AgentTools:
    async def get_context(_: str) -> dict[str, Any]:
        return context

    async def evaluate(disease_id: str, inputs: dict[str, Any]) -> dict[str, Any]:
        return evaluate_deterministic(disease_id, inputs)

    async def get_evidence(result: dict[str, Any]) -> list[dict[str, Any]]:
        return build_rule_evidence(result)

    return AgentTools(
        recorder=recorder,
        get_context=get_context,
        evaluate=evaluate,
        get_evidence=get_evidence,
    )


def _context(
    hip_context: dict[str, Any],
    *,
    model: ClinicalDraftModel | None = None,
) -> tuple[AgentContext, AgentTools, NullRecorder]:
    recorder = NullRecorder()
    tools = _tools(hip_context, recorder)
    return (
        AgentContext(
            tools=tools,
            model=model or ClinicalDraftModel(),
            recorder=recorder,
        ),
        tools,
        recorder,
    )


def _initial_state(hip_context: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": "run-test",
        "assessment_id": hip_context["assessment_id"],
        "patient_token": hip_context["patient_token"],
        "disease_id": hip_context["disease_id"],
        "rewrite_rounds": 0,
        "tokens_in": 0,
        "tokens_out": 0,
    }


async def test_mock_graph_waits_for_approve_then_signs(hip_context: dict[str, Any]) -> None:
    graph = build_agent_graph(InMemorySaver())
    context, tools, _ = _context(hip_context)
    config = {"configurable": {"thread_id": "approve-thread"}}

    async for _ in graph.astream(
        _initial_state(hip_context),
        config,
        context=context,
        stream_mode="updates",
    ):
        pass

    snapshot = await graph.aget_state(config)
    assert snapshot.next == ("review",)
    assert snapshot.interrupts
    assert snapshot.values["verification"]["numeric_passed"] is True
    assert snapshot.values["verification"]["citation_passed"] is True
    assert tools.calls == 3

    final = await graph.ainvoke(
        Command(resume={"decision": "APPROVE", "note": "已复核"}),
        config,
        context=context,
    )
    assert final["approved"] is True
    assert final["decision"] == "APPROVE"
    assert final["final_draft"]["disclaimer"] == "演示模型，未经校准"


async def test_mock_graph_reject_keeps_trace_and_draft(hip_context: dict[str, Any]) -> None:
    graph = build_agent_graph(InMemorySaver())
    context, _, _ = _context(hip_context)
    config = {"configurable": {"thread_id": "reject-thread"}}

    async for _ in graph.astream(
        _initial_state(hip_context),
        config,
        context=context,
        stream_mode="updates",
    ):
        pass

    final = await graph.ainvoke(
        Command(resume={"decision": "REJECT", "note": "解释不够充分"}),
        config,
        context=context,
    )
    assert final["approved"] is False
    assert final["decision"] == "REJECT"
    assert final["decision_note"] == "解释不够充分"
    assert final["final_draft"]["title"]


async def test_numeric_tampering_fails_after_two_rewrites(hip_context: dict[str, Any]) -> None:
    graph = build_agent_graph(InMemorySaver())
    model = ClinicalDraftModel(fail_first_n=10)
    context, _, _ = _context(hip_context, model=model)
    config = {"configurable": {"thread_id": "tamper-thread"}}

    async for _ in graph.astream(
        _initial_state(hip_context),
        config,
        context=context,
        stream_mode="updates",
    ):
        pass

    snapshot = await graph.aget_state(config)
    assert snapshot.next == ()
    assert model.calls == 3
    assert snapshot.values["rewrite_rounds"] == 2
    assert snapshot.values["verification"]["numeric_passed"] is False
    assert "未通过校验" in snapshot.values["failure_reason"]
