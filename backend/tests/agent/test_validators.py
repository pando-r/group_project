from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.agent.llm import ClinicalDraftModel, build_draft_prompt
from app.agent.validators import validate_draft
from app.services.assessment_service import evaluate_deterministic
from app.services.evidence_service import build_rule_evidence


async def _generated_draft(context: dict[str, Any]) -> dict[str, Any]:
    evidence = build_rule_evidence(context["result"])
    prompt = build_draft_prompt(
        result=context["result"],
        evidence=evidence,
        patient_context=context,
    )
    generated = await ClinicalDraftModel().generate(
        prompt,
        result=context["result"],
        evidence=evidence,
    )
    return generated.draft


async def test_valid_draft_passes_all_validators(hip_context: dict[str, Any]) -> None:
    draft = await _generated_draft(hip_context)
    _, verification = validate_draft(
        draft,
        result=hip_context["result"],
        evidence=build_rule_evidence(hip_context["result"]),
        rewrite_rounds=0,
    )
    assert verification["schema_passed"] is True
    assert verification["numeric_passed"] is True
    assert verification["citation_passed"] is True
    assert verification["errors"] == []


async def test_modified_rule_number_is_rejected(hip_context: dict[str, Any]) -> None:
    draft = deepcopy(await _generated_draft(hip_context))
    for fact in draft["facts"]:
        if fact["key"] == "risk_percent":
            fact["value"] = "42.0"
    draft["summary"] = draft["summary"].replace("18.5%", "42.0%")

    _, verification = validate_draft(
        draft,
        result=hip_context["result"],
        evidence=build_rule_evidence(hip_context["result"]),
        rewrite_rounds=1,
    )
    assert verification["numeric_passed"] is False
    assert any("风险百分比被改写" in error for error in verification["errors"])


async def test_percentages_present_in_rule_output_are_allowed() -> None:
    evaluation = evaluate_deterministic(
        "lung_cancer_preop",
        {"tnm_stage": "IIIA", "ppo_fev1": 45, "ppo_dlco": 40, "rcri": 2},
    )
    context = {
        "patient_token": "PATIENT-TEST0001",
        "age": 66,
        "gender": "MALE",
        "disease_id": "lung_cancer_preop",
        "disease_name": "肺癌术前风险评估",
        "result": evaluation["result"],
    }
    draft = await _generated_draft(context)
    _, verification = validate_draft(
        draft,
        result=context["result"],
        evidence=build_rule_evidence(context["result"]),
        rewrite_rounds=0,
    )
    assert verification["numeric_passed"] is True
    assert "45%" in draft["sections"][0]["body"]


async def test_unauthorised_percentage_in_prose_is_rejected(hip_context: dict[str, Any]) -> None:
    draft = deepcopy(await _generated_draft(hip_context))
    draft["risk_explanation"] += " 也可表述为 42.0%。"

    _, verification = validate_draft(
        draft,
        result=hip_context["result"],
        evidence=build_rule_evidence(hip_context["result"]),
        rewrite_rounds=0,
    )
    assert verification["numeric_passed"] is False
    assert any("未授权的百分比" in error for error in verification["errors"])


async def test_unknown_citation_is_rejected(hip_context: dict[str, Any]) -> None:
    draft = deepcopy(await _generated_draft(hip_context))
    draft["evidence_ids"].append("made-up-guideline-2099")

    _, verification = validate_draft(
        draft,
        result=hip_context["result"],
        evidence=build_rule_evidence(hip_context["result"]),
        rewrite_rounds=0,
    )
    assert verification["citation_passed"] is False
    assert any("证据白名单" in error for error in verification["errors"])


async def test_schema_failure_is_reported(hip_context: dict[str, Any]) -> None:
    draft = deepcopy(await _generated_draft(hip_context))
    draft.pop("summary")

    _, verification = validate_draft(
        draft,
        result=hip_context["result"],
        evidence=build_rule_evidence(hip_context["result"]),
        rewrite_rounds=0,
    )
    assert verification["schema_passed"] is False
    assert verification["errors"]
