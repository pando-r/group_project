from __future__ import annotations

import re
from collections.abc import Iterator
from typing import Any

from pydantic import ValidationError

from app.schemas.agent import AgentDraft, DraftFactKey

_PERCENT = re.compile(r"(?<![\d.])(\d+(?:\.\d+)?)\s*%")
_REQUIRED_FACT_KEYS: tuple[DraftFactKey, ...] = (
    "severity_grade",
    "severity_level",
    "risk_percent",
    "risk_tier",
    "prognosis_tier",
)


def _collect_text(draft: AgentDraft) -> list[str]:
    texts = [draft.summary, draft.risk_explanation, *draft.key_points]
    texts.extend(section.body for section in draft.sections)
    return texts


def _as_fact_map(draft: AgentDraft) -> tuple[dict[str, str] | None, list[str]]:
    values: dict[str, str] = {}
    errors: list[str] = []
    for fact in draft.facts:
        if fact.key in values:
            errors.append(f"事实字段重复：{fact.key}")
            continue
        values[fact.key] = fact.value.strip()
    missing = [key for key in _REQUIRED_FACT_KEYS if key not in values]
    if missing:
        errors.append(f"缺少规则事实字段：{', '.join(missing)}")
    return values or None, errors


def expected_facts(result: dict[str, Any]) -> dict[str, str]:
    severity = result.get("severity", {})
    risk = result.get("risk", {})
    prognosis = result.get("prognosis", {})
    return {
        "severity_grade": str(severity.get("grade", "")),
        "severity_level": str(severity.get("level", "")),
        "risk_percent": f"{float(risk.get('percent', 0.0)):.1f}",
        "risk_tier": str(risk.get("tier", "")),
        "prognosis_tier": str(prognosis.get("tier", "")),
    }


def _iter_strings(value: Any) -> Iterator[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from _iter_strings(item)
    elif isinstance(value, list | tuple):
        for item in value:
            yield from _iter_strings(item)


def allowed_percents(result: dict[str, Any]) -> set[float]:
    """Percentages the draft may quote: risk percent plus anything in the rule output.

    Rules surface clinically relevant percentages (for example ppoFEV1), so the
    prose is allowed to copy them verbatim. Numbers absent from the rule output
    remain unauthorised.
    """

    values = {float(expected_facts(result)["risk_percent"])}
    for text in _iter_strings(result):
        for match in _PERCENT.finditer(text):
            try:
                values.add(float(match.group(1)))
            except ValueError:
                continue
    return values


def validate_numeric(draft: AgentDraft, result: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    actual, fact_errors = _as_fact_map(draft)
    errors.extend(fact_errors)
    if actual is None:
        return errors

    expected = expected_facts(result)
    for key, expected_value in expected.items():
        actual_value = actual.get(key)
        if actual_value is None:
            continue
        if key == "risk_percent":
            try:
                actual_number = float(actual_value.replace("%", "").strip())
                if abs(actual_number - float(expected_value)) > 0.0001:
                    errors.append(f"风险百分比被改写：{actual_value}（规则值 {expected_value}）")
            except ValueError:
                errors.append(f"风险百分比格式非法：{actual_value}")
        elif actual_value != expected_value:
            errors.append(f"{key} 被改写：{actual_value}（规则值 {expected_value}）")

    allowed_percent_set = allowed_percents(result)
    for text in _collect_text(draft):
        for match in _PERCENT.finditer(text):
            try:
                value = float(match.group(1))
            except ValueError:
                errors.append(f"无法解析百分比：{match.group(0)}")
                continue
            if not any(abs(value - allowed) <= 0.0001 for allowed in allowed_percent_set):
                errors.append(f"正文出现未授权的百分比：{match.group(0)}")
    return errors


def validate_citations(
    draft: AgentDraft,
    *,
    result: dict[str, Any],
    evidence: list[dict[str, Any]],
) -> list[str]:
    errors: list[str] = []
    evidence_ids = {str(item.get("id")) for item in evidence if item.get("id")}
    allowed_recommendations = {
        str(item.get("id"))
        for item in result.get("recommendations", [])
        if isinstance(item, dict) and item.get("id")
    }

    for citation_id in draft.evidence_ids:
        if citation_id not in evidence_ids:
            errors.append(f"引用不在证据白名单：{citation_id}")
    for section in draft.sections:
        for citation_id in section.evidence_ids:
            if citation_id not in evidence_ids:
                errors.append(f"章节“{section.heading}”引用不在证据白名单：{citation_id}")
    for recommendation_id in draft.recommendation_ids:
        if recommendation_id not in allowed_recommendations:
            errors.append(f"建议不在规则输出中：{recommendation_id}")

    if evidence_ids and not draft.evidence_ids:
        errors.append("草稿未引用任何已提供证据")
    if allowed_recommendations and not draft.recommendation_ids:
        errors.append("草稿未关联任何规则建议")
    return errors


def validate_draft(
    raw: dict[str, Any] | None,
    *,
    result: dict[str, Any],
    evidence: list[dict[str, Any]],
    rewrite_rounds: int,
) -> tuple[AgentDraft | None, dict[str, Any]]:
    schema_errors: list[str] = []
    draft: AgentDraft | None = None
    if not isinstance(raw, dict):
        schema_errors.append("模型输出不是 JSON 对象")
    else:
        try:
            draft = AgentDraft.model_validate(raw)
        except ValidationError as exc:
            for error in exc.errors():
                location = ".".join(str(part) for part in error.get("loc", ())) or "root"
                schema_errors.append(f"结构校验失败 {location}: {error.get('msg', '')}")

    numeric_errors: list[str] = []
    citation_errors: list[str] = []
    if draft is not None:
        numeric_errors = validate_numeric(draft, result)
        citation_errors = validate_citations(draft, result=result, evidence=evidence)

    errors = [*schema_errors, *numeric_errors, *citation_errors]
    verification = {
        "schema_passed": not schema_errors,
        "numeric_passed": not numeric_errors,
        "citation_passed": not citation_errors,
        "rewrite_rounds": rewrite_rounds,
        "errors": errors,
    }
    return draft, verification
