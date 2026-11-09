from __future__ import annotations

from typing import Any, TypedDict


class AgentState(TypedDict, total=False):
    run_id: str
    assessment_id: str
    patient_token: str
    disease_id: str
    disease_name: str
    patient_context: dict[str, Any]
    cleaned_inputs: dict[str, Any]
    result: dict[str, Any]
    evidence: list[dict[str, Any]]
    draft: dict[str, Any] | None
    verification: dict[str, Any]
    validation_errors: list[str]
    rewrite_rounds: int
    tokens_in: int
    tokens_out: int
    decision: str | None
    decision_note: str | None
    edited_draft: dict[str, Any] | None
    final_draft: dict[str, Any] | None
    approved: bool
    failure_reason: str | None
