from __future__ import annotations

from typing import Any

from app.models.assessment import Assessment
from app.models.patient import Patient
from app.rules import registry
from app.schemas.assessment import AssessmentQueueItem, AssessmentRead
from app.schemas.patient import AssessmentBrief, PatientSummary


def patient_summary(patient: Patient) -> PatientSummary:
    return PatientSummary(
        id=patient.id,
        mrn=patient.mrn,
        name=patient.name,
        gender=patient.gender,
        birth_date=patient.birth_date,
        age=patient.age,
        created_at=patient.created_at,
    )


def _result_parts(assessment: Assessment) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    result = assessment.result or {}
    severity = result.get("severity") if isinstance(result, dict) else {}
    risk = result.get("risk") if isinstance(result, dict) else {}
    meta = result.get("meta") if isinstance(result, dict) else {}
    return (
        severity if isinstance(severity, dict) else {},
        risk if isinstance(risk, dict) else {},
        meta if isinstance(meta, dict) else {},
    )


def disease_identity(assessment: Assessment) -> tuple[str, str, str]:
    _, _, meta = _result_parts(assessment)
    try:
        definition = registry.get_rule(assessment.disease_id).definition
    except KeyError:
        return (
            str(meta.get("disease_name") or assessment.disease_id),
            assessment.specialty,
            str(meta.get("specialty") or assessment.specialty),
        )
    return definition.name, definition.specialty, definition.specialty_label


def assessment_to_brief(assessment: Assessment) -> AssessmentBrief:
    severity, risk, _ = _result_parts(assessment)
    disease_name, specialty, specialty_label = disease_identity(assessment)
    return AssessmentBrief(
        id=assessment.id,
        disease_id=assessment.disease_id,
        disease_name=disease_name,
        specialty=specialty,
        specialty_label=specialty_label,
        status=assessment.status,
        severity_grade=str(severity.get("grade", "未分级")),
        severity_level=int(severity.get("level", 1)),
        severity_tone=str(severity.get("tone", "neutral")),
        risk_percent=float(risk.get("percent", 0.0)),
        risk_tier=str(risk.get("tier", "low")),
        risk_tone=str(risk.get("tone", "neutral")),
        created_at=assessment.created_at,
        confirmed_at=assessment.confirmed_at,
    )


def assessment_to_read(assessment: Assessment) -> AssessmentRead:
    disease_name, _, specialty_label = disease_identity(assessment)
    confirmed_by_user = assessment.confirmed_by_user
    return AssessmentRead(
        id=assessment.id,
        patient=patient_summary(assessment.patient),
        specialty=assessment.specialty,
        specialty_label=specialty_label,
        disease_id=assessment.disease_id,
        disease_name=disease_name,
        inputs=assessment.inputs,
        result=assessment.result,
        status=assessment.status,
        decision=assessment.decision,
        note=assessment.note,
        confirmed_by=assessment.confirmed_by,
        confirmed_by_name=confirmed_by_user.display_name if confirmed_by_user else None,
        confirmed_at=assessment.confirmed_at,
        model_version=assessment.model_version,
        created_at=assessment.created_at,
        updated_at=assessment.updated_at,
    )


def assessment_to_queue(assessment: Assessment) -> AssessmentQueueItem:
    severity, risk, _ = _result_parts(assessment)
    disease_name, _, _ = disease_identity(assessment)
    return AssessmentQueueItem(
        id=assessment.id,
        patient_id=assessment.patient_id,
        patient_name=assessment.patient.name,
        mrn=assessment.patient.mrn,
        disease_id=assessment.disease_id,
        disease_name=disease_name,
        specialty=assessment.specialty,
        severity_grade=str(severity.get("grade", "未分级")),
        severity_level=int(severity.get("level", 1)),
        risk_percent=float(risk.get("percent", 0.0)),
        risk_tier=str(risk.get("tier", "low")),
        created_at=assessment.created_at,
    )
