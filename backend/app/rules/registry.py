from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.rules.base import DiseaseDefinition, EvaluationResult
from app.rules.constants import ACTIVE_RULE_VERSION, RULE_VERSION_INFO, SOURCES
from app.rules.hpb import (
    CHOLECYSTITIS_DEFINITION,
    HCC_DEFINITION,
    evaluate_acute_cholecystitis,
    evaluate_hcc,
)
from app.rules.ortho import (
    HIP_DEFINITION,
    KNEE_DEFINITION,
    evaluate_hip_fracture,
    evaluate_knee_oa,
)
from app.rules.thoracic import (
    LUNG_CANCER_DEFINITION,
    NODULE_DEFINITION,
    evaluate_lung_cancer_preop,
    evaluate_pulmonary_nodule,
)
from app.rules.urology import (
    PROSTATE_DEFINITION,
    STONE_DEFINITION,
    evaluate_prostate_cancer,
    evaluate_upper_urinary_stone,
)

Evaluator = Callable[[dict[str, Any]], EvaluationResult]


@dataclass(frozen=True)
class RegisteredRule:
    definition: DiseaseDefinition
    evaluator: Evaluator

    @property
    def disease_id(self) -> str:
        return self.definition.id


_RULES: tuple[RegisteredRule, ...] = (
    RegisteredRule(HIP_DEFINITION, evaluate_hip_fracture),
    RegisteredRule(KNEE_DEFINITION, evaluate_knee_oa),
    RegisteredRule(NODULE_DEFINITION, evaluate_pulmonary_nodule),
    RegisteredRule(LUNG_CANCER_DEFINITION, evaluate_lung_cancer_preop),
    RegisteredRule(HCC_DEFINITION, evaluate_hcc),
    RegisteredRule(CHOLECYSTITIS_DEFINITION, evaluate_acute_cholecystitis),
    RegisteredRule(PROSTATE_DEFINITION, evaluate_prostate_cancer),
    RegisteredRule(STONE_DEFINITION, evaluate_upper_urinary_stone),
)

_RULES_BY_ID = {rule.disease_id: rule for rule in _RULES}


def list_rules() -> list[RegisteredRule]:
    return list(_RULES)


def get_rule(disease_id: str) -> RegisteredRule:
    try:
        return _RULES_BY_ID[disease_id]
    except KeyError as exc:
        raise KeyError(f"未知病种：{disease_id}") from exc


def evaluate(disease_id: str, fields: dict[str, Any]) -> EvaluationResult:
    return get_rule(disease_id).evaluator(fields)


def public_disease(rule: RegisteredRule) -> dict[str, Any]:
    definition = rule.definition
    return {
        "id": definition.id,
        "name": definition.name,
        "short_name": definition.short_name,
        "specialty": definition.specialty,
        "specialty_label": definition.specialty_label,
        "summary": definition.summary,
        "sources": definition.sources,
        "fields": [field.model_dump() for field in definition.fields],
    }


def public_registry() -> dict[str, Any]:
    specialties: dict[str, str] = {}
    for rule in _RULES:
        specialties.setdefault(rule.definition.specialty, rule.definition.specialty_label)
    return {
        "ruleVersion": ACTIVE_RULE_VERSION,
        "version": {
            "version": RULE_VERSION_INFO.version,
            "changelog": RULE_VERSION_INFO.changelog,
        },
        "specialties": [{"id": specialty_id, "label": label} for specialty_id, label in specialties.items()],
        "diseases": [public_disease(rule) for rule in _RULES],
        "sources": SOURCES,
    }


__all__ = [
    "ACTIVE_RULE_VERSION",
    "evaluate",
    "get_rule",
    "list_rules",
    "public_registry",
]
