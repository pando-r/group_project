from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import get_logger
from app.core.security import hash_password
from app.models.assessment import Assessment, AssessmentStatus
from app.models.audit import AuditLog
from app.models.patient import Patient
from app.models.rule_version import RuleVersion
from app.models.user import User, UserRole
from app.rules import registry
from app.rules.constants import RULE_VERSION_INFO

logger = get_logger(__name__)

_PATIENTS: list[dict[str, Any]] = [
    {"mrn": "MR20260001", "name": "张明远", "gender": "MALE", "age": 82},
    {"mrn": "MR20260002", "name": "李秀兰", "gender": "FEMALE", "age": 71},
    {"mrn": "MR20260003", "name": "王建国", "gender": "MALE", "age": 64},
    {"mrn": "MR20260004", "name": "陈雨薇", "gender": "FEMALE", "age": 52},
    {"mrn": "MR20260005", "name": "刘海峰", "gender": "MALE", "age": 59},
    {"mrn": "MR20260006", "name": "赵静", "gender": "FEMALE", "age": 45},
    {"mrn": "MR20260007", "name": "孙志强", "gender": "MALE", "age": 67},
    {"mrn": "MR20260008", "name": "周敏", "gender": "FEMALE", "age": 38},
    {"mrn": "MR20260009", "name": "吴桂英", "gender": "FEMALE", "age": 85},
    {"mrn": "MR20260010", "name": "徐文博", "gender": "MALE", "age": 72},
    {"mrn": "MR20260011", "name": "何晓东", "gender": "MALE", "age": 56},
    {"mrn": "MR20260012", "name": "郑丽华", "gender": "FEMALE", "age": 63},
    {"mrn": "MR20260013", "name": "马俊", "gender": "MALE", "age": 70},
    {"mrn": "MR20260014", "name": "高红", "gender": "FEMALE", "age": 49},
    {"mrn": "MR20260015", "name": "林志远", "gender": "MALE", "age": 61},
    {"mrn": "MR20260016", "name": "罗雪", "gender": "FEMALE", "age": 33},
    {"mrn": "MR20260017", "name": "黄德海", "gender": "MALE", "age": 88},
    {"mrn": "MR20260018", "name": "宋雅琴", "gender": "FEMALE", "age": 58},
]

_ASSESSMENTS: list[dict[str, Any]] = [
    {
        "mrn": "MR20260001",
        "disease_id": "hip_fracture",
        "fields": {"age": 82, "asa": "III", "hemoglobin": 92, "fracture_type": "31B"},
        "days_ago": 1,
        "status": "PENDING",
    },
    {
        "mrn": "MR20260002",
        "disease_id": "knee_oa",
        "fields": {"kl_grade": "3", "pain_vas": 7, "age": 71, "bmi": 31.5},
        "days_ago": 2,
        "status": "CONFIRMED",
    },
    {
        "mrn": "MR20260003",
        "disease_id": "pulmonary_nodule",
        "fields": {
            "nodule_type": "solid",
            "diameter_mm": 9,
            "growth": True,
            "age": 64,
            "smoking_pack_years": 35,
        },
        "days_ago": 3,
        "status": "PENDING",
    },
    {
        "mrn": "MR20260004",
        "disease_id": "lung_cancer_preop",
        "fields": {"tnm_stage": "IIIA", "ppo_fev1": 45, "ppo_dlco": 42, "rcri": 2},
        "days_ago": 4,
        "status": "CONFIRMED",
    },
    {
        "mrn": "MR20260005",
        "disease_id": "hcc",
        "fields": {
            "child_pugh": "A",
            "bclc": "B",
            "cnlc": "IIb",
            "tumor_size": 6.2,
            "afp": 480,
            "portal_invasion": False,
        },
        "days_ago": 5,
        "status": "PENDING",
    },
    {
        "mrn": "MR20260006",
        "disease_id": "acute_cholecystitis",
        "fields": {"tokyo_grade": "II", "asa": "III", "wbc": 19, "bilirubin": 30, "symptom_days": 4},
        "days_ago": 6,
        "status": "CONFIRMED",
    },
    {
        "mrn": "MR20260007",
        "disease_id": "prostate_cancer",
        "fields": {
            "psa": 22,
            "grade_group": "4",
            "clinical_t": "T3a",
            "positive_cores_pct": 60,
            "capra": 7,
        },
        "days_ago": 7,
        "status": "CONFIRMED",
    },
    {
        "mrn": "MR20260008",
        "disease_id": "upper_urinary_stone",
        "fields": {
            "guy_score": "3",
            "stone_size": 25,
            "stone_location": "renal_lower",
            "hydronephrosis": "moderate",
            "egfr": 58,
        },
        "days_ago": 8,
        "status": "PENDING",
    },
    {
        "mrn": "MR20260009",
        "disease_id": "hip_fracture",
        "fields": {"age": 85, "asa": "IV", "hemoglobin": 78, "fracture_type": "31C"},
        "days_ago": 9,
        "status": "CONFIRMED",
    },
    {
        "mrn": "MR20260010",
        "disease_id": "pulmonary_nodule",
        "fields": {
            "nodule_type": "part_solid",
            "diameter_mm": 16,
            "growth": False,
            "age": 72,
            "smoking_pack_years": 50,
        },
        "days_ago": 11,
        "status": "CONFIRMED",
    },
    {
        "mrn": "MR20260011",
        "disease_id": "hcc",
        "fields": {
            "child_pugh": "B",
            "bclc": "C",
            "cnlc": "IIIa",
            "tumor_size": 8.5,
            "afp": 1200,
            "portal_invasion": True,
        },
        "days_ago": 12,
        "status": "PENDING",
    },
    {
        "mrn": "MR20260012",
        "disease_id": "knee_oa",
        "fields": {"kl_grade": "4", "pain_vas": 8, "age": 63, "bmi": 27},
        "days_ago": 14,
        "status": "CONFIRMED",
    },
    {
        "mrn": "MR20260013",
        "disease_id": "prostate_cancer",
        "fields": {
            "psa": 8,
            "grade_group": "2",
            "clinical_t": "T2a",
            "positive_cores_pct": 25,
            "capra": 3,
        },
        "days_ago": 16,
        "status": "CONFIRMED",
    },
    {
        "mrn": "MR20260014",
        "disease_id": "acute_cholecystitis",
        "fields": {"tokyo_grade": "I", "asa": "II", "wbc": 13, "bilirubin": 18, "symptom_days": 2},
        "days_ago": 18,
        "status": "CONFIRMED",
    },
    {
        "mrn": "MR20260015",
        "disease_id": "lung_cancer_preop",
        "fields": {"tnm_stage": "II", "ppo_fev1": 58, "ppo_dlco": 55, "rcri": 1},
        "days_ago": 21,
        "status": "PENDING",
    },
    {
        "mrn": "MR20260016",
        "disease_id": "upper_urinary_stone",
        "fields": {
            "guy_score": "1",
            "stone_size": 6,
            "stone_location": "ureter",
            "hydronephrosis": "mild",
            "egfr": 95,
        },
        "days_ago": 24,
        "status": "CONFIRMED",
    },
    {
        "mrn": "MR20260017",
        "disease_id": "hip_fracture",
        "fields": {"age": 88, "asa": "III", "hemoglobin": 112, "fracture_type": "31A"},
        "days_ago": 27,
        "status": "CONFIRMED",
    },
    {
        "mrn": "MR20260018",
        "disease_id": "pulmonary_nodule",
        "fields": {
            "nodule_type": "ground_glass",
            "diameter_mm": 12,
            "growth": False,
            "age": 58,
            "smoking_pack_years": 10,
        },
        "days_ago": 30,
        "status": "PENDING",
    },
    {
        "mrn": "MR20260003",
        "disease_id": "pulmonary_nodule",
        "fields": {
            "nodule_type": "solid",
            "diameter_mm": 5,
            "growth": False,
            "age": 64,
            "smoking_pack_years": 35,
        },
        "days_ago": 32,
        "status": "CONFIRMED",
    },
    {
        "mrn": "MR20260005",
        "disease_id": "hcc",
        "fields": {
            "child_pugh": "A",
            "bclc": "A",
            "cnlc": "Ia",
            "tumor_size": 3.2,
            "afp": 120,
            "portal_invasion": False,
        },
        "days_ago": 40,
        "status": "CONFIRMED",
    },
]


def _birth_date_for_age(age: int, seed_index: int) -> date:
    today = date.today()
    try:
        base = today.replace(year=today.year - age)
    except ValueError:
        base = today.replace(year=today.year - age, day=28)
    return base - timedelta(days=seed_index * 19)


async def seed_database(session: AsyncSession) -> bool:
    existing_users = int((await session.scalar(select(func.count()).select_from(User))) or 0)
    if existing_users > 0:
        return False

    doctor = User(
        username=settings.seed_doctor_username,
        password_hash=hash_password(settings.seed_doctor_password),
        display_name="林知远",
        role=UserRole.DOCTOR,
    )
    admin = User(
        username=settings.seed_admin_username,
        password_hash=hash_password(settings.seed_admin_password),
        display_name="系统管理员",
        role=UserRole.ADMIN,
    )
    session.add_all([doctor, admin])

    session.add(
        RuleVersion(
            version=RULE_VERSION_INFO.version,
            changelog=RULE_VERSION_INFO.changelog,
        )
    )
    await session.flush()

    patients: dict[str, Patient] = {}
    for index, record in enumerate(_PATIENTS):
        patient = Patient(
            mrn=record["mrn"],
            name=record["name"],
            gender=record["gender"],
            birth_date=_birth_date_for_age(int(record["age"]), index),
        )
        session.add(patient)
        patients[patient.mrn] = patient
    await session.flush()

    now = datetime.now(UTC)
    for record in _ASSESSMENTS:
        patient = patients[record["mrn"]]
        rule = registry.get_rule(record["disease_id"])
        evaluation = rule.evaluator(record["fields"])
        created_at = now - timedelta(days=int(record["days_ago"]), hours=2)
        is_confirmed = record["status"] == AssessmentStatus.CONFIRMED
        assessment = Assessment(
            patient_id=patient.id,
            specialty=rule.definition.specialty,
            disease_id=rule.definition.id,
            inputs={
                "fields": record["fields"],
                "context": {"source": "seed", "deidentified": True},
            },
            result=evaluation.model_dump(mode="json"),
            status=AssessmentStatus(record["status"]),
            decision="同意评估结论" if is_confirmed else None,
            note="合成演示病例，已完成临床复核。" if is_confirmed else None,
            confirmed_by=doctor.id if is_confirmed else None,
            confirmed_at=created_at + timedelta(hours=1) if is_confirmed else None,
            model_version=RULE_VERSION_INFO.version,
            created_at=created_at,
            updated_at=created_at,
        )
        session.add(assessment)
        await session.flush()
        session.add(
            AuditLog(
                assessment_id=assessment.id,
                actor_id=doctor.id,
                action="ASSESSMENT_CREATED",
                detail={
                    "summary": f"{rule.definition.short_name} · {evaluation.severity.grade}",
                    "disease_id": rule.definition.id,
                    "risk_tier": evaluation.risk.tier,
                    "source": "seed",
                },
                ip=None,
                created_at=created_at,
            )
        )
        if is_confirmed:
            session.add(
                AuditLog(
                    assessment_id=assessment.id,
                    actor_id=doctor.id,
                    action="ASSESSMENT_CONFIRMED",
                    detail={"summary": "评估已签字确认", "decision": "同意评估结论"},
                    ip=None,
                    created_at=created_at + timedelta(hours=1),
                )
            )

    await session.commit()
    logger.info("seed_completed", patients=len(patients), assessments=len(_ASSESSMENTS))
    return True
