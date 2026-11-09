from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.config import settings
from app.models.assessment import Assessment, AssessmentStatus
from app.models.audit import AuditLog
from app.models.patient import Patient
from app.rules import registry
from app.schemas.dashboard import (
    ActivityItem,
    DashboardResponse,
    MetricCard,
    ModelStatus,
    RiskSlice,
)
from app.services.presenters import assessment_to_queue

_ACTION_LABELS = {
    "ASSESSMENT_CREATED": "创建评估",
    "ASSESSMENT_CONFIRMED": "确认签字",
    "AGENT_ASSESSMENT_CREATED": "AI 草稿转评估",
}


def _tier_labels(tier: str) -> tuple[str, str]:
    return {
        "low": ("低风险", "success"),
        "moderate": ("中风险", "warning"),
        "high": ("高风险", "danger"),
        "critical": ("极高风险", "danger"),
    }.get(tier, ("未分级", "neutral"))


async def build_dashboard(session: AsyncSession) -> DashboardResponse:
    patient_count = int((await session.scalar(select(func.count()).select_from(Patient))) or 0)
    assessments = list(
        (
            await session.scalars(
                select(Assessment)
                .options(joinedload(Assessment.patient))
                .order_by(Assessment.created_at.desc())
            )
        ).all()
    )
    now = datetime.now(UTC)
    month_count = sum(
        1
        for assessment in assessments
        if assessment.created_at.year == now.year and assessment.created_at.month == now.month
    )
    pending = [assessment for assessment in assessments if assessment.status == AssessmentStatus.PENDING]
    high_risk = [
        assessment
        for assessment in assessments
        if (assessment.result.get("risk", {}) or {}).get("tier") in {"high", "critical"}
    ]

    tier_counts = {"low": 0, "moderate": 0, "high": 0, "critical": 0}
    for assessment in assessments:
        tier = (assessment.result.get("risk", {}) or {}).get("tier")
        if tier in tier_counts:
            tier_counts[tier] += 1
    maximum = max(len(assessments), 1)
    risk_distribution = []
    for tier, count in tier_counts.items():
        label, tone = _tier_labels(tier)
        risk_distribution.append(
            RiskSlice(
                tier=tier,
                label=label,
                count=count,
                percent=round(count / maximum * 100, 1),
                tone=tone,
            )
        )

    audit_statement = (
        select(AuditLog)
        .options(joinedload(AuditLog.assessment).joinedload(Assessment.patient))
        .order_by(AuditLog.created_at.desc())
        .limit(8)
    )
    audit_rows = list((await session.scalars(audit_statement)).all())
    activity = []
    for log in audit_rows:
        assessment = log.assessment
        if assessment is None:
            continue
        detail: dict[str, Any] = log.detail if isinstance(log.detail, dict) else {}
        activity.append(
            ActivityItem(
                assessment_id=str(assessment.id),
                patient_name=assessment.patient.name if assessment.patient else "未知患者",
                action=_ACTION_LABELS.get(log.action, log.action),
                detail=str(detail.get("summary", "")),
                created_at=log.created_at,
            )
        )

    model_status = ModelStatus(
        mode="mock" if settings.llm_mock else "live",
        mode_label="离线演示模型" if settings.llm_mock else "真实模型",
        model=settings.llm_model if not settings.llm_mock else "mock-clinical-v1（离线）",
        prompt_version=settings.prompt_version,
        rule_version=registry.ACTIVE_RULE_VERSION,
        note=(
            "LLM_MOCK=1，Agent 使用离线脚本模型，不向外部供应商发送任何数据。"
            if settings.llm_mock
            else ("已接入 DeepSeek；调用前完成脱敏，供应商须承诺不用于训练或改用私有化端点。")
        ),
    )

    return DashboardResponse(
        metrics=[
            MetricCard(key="patients", label="患者总数", value=patient_count, hint="合成演示数据"),
            MetricCard(key="monthly", label="本月评估", value=month_count, unit="例"),
            MetricCard(key="pending", label="待确认", value=len(pending), unit="例", hint="需医生签字"),
            MetricCard(
                key="high_risk",
                label="高风险评估",
                value=len(high_risk),
                unit="例",
                hint="高风险与极高风险合计",
            ),
        ],
        pending_queue=[assessment_to_queue(item) for item in pending[:8]],
        risk_distribution=risk_distribution,
        recent_activity=activity,
        model_status=model_status,
    )
