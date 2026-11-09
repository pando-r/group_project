from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

Tone = Literal["neutral", "success", "warning", "danger"]
Priority = Literal["routine", "consider", "urgent"]
FieldType = Literal["number", "integer", "select", "boolean"]

DISCLAIMER = "演示模型，未经校准，不替代医生决策"


class RuleInputError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


class FieldOption(BaseModel):
    value: str
    label: str


class FieldSpec(BaseModel):
    key: str
    label: str
    type: FieldType
    unit: str | None = None
    required: bool = True
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    default: Any = None
    options: list[FieldOption] = Field(default_factory=list)
    help: str | None = None


class DiseaseDefinition(BaseModel):
    id: str
    name: str
    short_name: str
    specialty: str
    specialty_label: str
    summary: str
    fields: list[FieldSpec]
    sources: list[str]
    accent: str = "default"


class Citation(BaseModel):
    type: Literal["rule", "guideline"] = "rule"
    id: str
    label: str


class BasisItem(BaseModel):
    id: str
    label: str
    value: str
    source: str


class Scale(BaseModel):
    min: int
    max: int
    labels: list[str]


class SeverityResult(BaseModel):
    grade: str
    level: int
    tone: Tone
    scale: Scale
    basis: list[BasisItem]
    summary: str


class RiskCut(BaseModel):
    min: float
    max: float
    label: str


class RiskDriver(BaseModel):
    label: str
    direction: Literal["increase", "decrease"]
    detail: str


class RiskResult(BaseModel):
    label: str
    percent: float
    tier: Literal["low", "moderate", "high", "critical"]
    tone: Tone
    cuts: list[RiskCut]
    drivers: list[RiskDriver]
    summary: str


class PrognosisMetric(BaseModel):
    label: str
    value: str
    note: str | None = None


class PrognosisResult(BaseModel):
    tier: str
    summary: str
    metrics: list[PrognosisMetric]


class Recommendation(BaseModel):
    id: str
    text: str
    priority: Priority = "routine"
    citations: list[Citation]


class RedFlag(BaseModel):
    code: str
    text: str
    severity: Literal["warning", "critical"]


class ResultMeta(BaseModel):
    disease_id: str
    disease_name: str
    specialty: str
    rule_version: str
    disclaimer: str = DISCLAIMER


class EvaluationResult(BaseModel):
    severity: SeverityResult
    risk: RiskResult
    prognosis: PrognosisResult
    recommendations: list[Recommendation]
    red_flags: list[RedFlag]
    meta: ResultMeta


class RuleModule(Protocol):
    definition: DiseaseDefinition

    def evaluate(self, fields: dict[str, Any]) -> EvaluationResult: ...


# ---------------------------------------------------------------------------
# Input validation and coercion used by both the API and tests.
# ---------------------------------------------------------------------------


def _coerce_number(spec: FieldSpec, raw: Any) -> float:
    if isinstance(raw, bool) or raw is None:
        raise RuleInputError(spec.key, f"{spec.label}必须是数字")
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise RuleInputError(spec.key, f"{spec.label}必须是数字") from exc
    if spec.minimum is not None and value < spec.minimum:
        raise RuleInputError(spec.key, f"{spec.label}不能小于 {spec.minimum:g}")
    if spec.maximum is not None and value > spec.maximum:
        raise RuleInputError(spec.key, f"{spec.label}不能大于 {spec.maximum:g}")
    return value


def validate_fields(definition: DiseaseDefinition, raw_fields: dict[str, Any]) -> dict[str, Any]:
    """Validate and coerce inputs against a disease definition.

    Unrecognised keys are dropped; extra data must never silently alter a rule.
    """

    cleaned: dict[str, Any] = {}
    for spec in definition.fields:
        raw = raw_fields.get(spec.key)
        if raw is None or raw == "":
            if spec.required:
                raise RuleInputError(spec.key, f"缺少必填字段：{spec.label}")
            if spec.default is not None:
                cleaned[spec.key] = spec.default
            continue

        if spec.type in {"number", "integer"}:
            value = _coerce_number(spec, raw)
            if spec.type == "integer":
                if not value.is_integer():
                    raise RuleInputError(spec.key, f"{spec.label}必须是整数")
                cleaned[spec.key] = int(value)
            else:
                cleaned[spec.key] = value
        elif spec.type == "boolean":
            if isinstance(raw, bool):
                cleaned[spec.key] = raw
            elif isinstance(raw, str) and raw.lower() in {"true", "false"}:
                cleaned[spec.key] = raw.lower() == "true"
            else:
                raise RuleInputError(spec.key, f"{spec.label}必须是布尔值")
        else:
            allowed = {option.value for option in spec.options}
            text = str(raw)
            if text not in allowed:
                raise RuleInputError(spec.key, f"{spec.label}取值不在允许范围内")
            cleaned[spec.key] = text
    return cleaned


# ---------------------------------------------------------------------------
# Result construction helpers.
# ---------------------------------------------------------------------------


def make_scale(labels: list[str]) -> Scale:
    return Scale(min=1, max=len(labels), labels=labels)


def tone_for_level(level: int) -> Tone:
    if level <= 1:
        return "success"
    if level == 2:
        return "warning"
    return "danger"


def make_risk_cuts(bands: list[tuple[float, float, str]]) -> list[RiskCut]:
    return [RiskCut(min=low, max=high, label=label) for low, high, label in bands]


DEFAULT_RISK_CUTS = [
    (0.0, 10.0, "低"),
    (10.0, 20.0, "中"),
    (20.0, 35.0, "高"),
    (35.0, 100.0, "极高"),
]


def tier_for_percent(percent: float) -> Literal["low", "moderate", "high", "critical"]:
    if percent < 10:
        return "low"
    if percent < 20:
        return "moderate"
    if percent < 35:
        return "high"
    return "critical"


def tone_for_tier(tier: str) -> Tone:
    return {
        "low": "success",
        "moderate": "warning",
        "high": "danger",
        "critical": "danger",
    }.get(tier, "neutral")


def rule_citation(rule_id: str, label: str) -> Citation:
    return Citation(type="rule", id=rule_id, label=label)


def guideline_citation(citation_id: str, label: str) -> Citation:
    return Citation(type="guideline", id=citation_id, label=label)


@dataclass(frozen=True)
class RuleVersionInfo:
    version: str
    changelog: str
