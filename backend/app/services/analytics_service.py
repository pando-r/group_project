from __future__ import annotations

from collections import Counter, defaultdict
from datetime import UTC, date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assessment import Assessment, AssessmentStatus
from app.rules import registry
from app.schemas.analytics import (
    AnalyticsOverview,
    DiseaseCount,
    SpecialtyCount,
    TrendPoint,
)
from app.services.presenters import disease_identity


async def overview(
    session: AsyncSession,
    *,
    start: date,
    end: date,
) -> AnalyticsOverview:
    if end < start:
        start, end = end, start
    if (end - start).days > 90:
        start = end - timedelta(days=90)

    start_dt = datetime.combine(start, time.min, tzinfo=UTC)
    end_dt = datetime.combine(end + timedelta(days=1), time.min, tzinfo=UTC)
    assessments = list(
        (
            await session.scalars(
                select(Assessment)
                .where(Assessment.created_at >= start_dt, Assessment.created_at < end_dt)
                .order_by(Assessment.created_at.asc())
            )
        ).all()
    )

    trend_counts: dict[date, Counter[str]] = defaultdict(Counter)
    day = start
    while day <= end:
        trend_counts[day] = Counter()
        day += timedelta(days=1)

    disease_counts: Counter[str] = Counter()
    disease_risks: defaultdict[str, list[float]] = defaultdict(list)
    disease_confirmed: Counter[str] = Counter()
    specialty_counts: Counter[str] = Counter()
    confirmed = 0
    high_risk = 0
    risk_values: list[float] = []

    for assessment in assessments:
        result = assessment.result or {}
        risk = result.get("risk", {}) if isinstance(result, dict) else {}
        tier = risk.get("tier", "low")
        percent = float(risk.get("percent", 0.0))
        risk_values.append(percent)
        if tier in {"high", "critical"}:
            high_risk += 1
        if assessment.status == AssessmentStatus.CONFIRMED:
            confirmed += 1
            disease_confirmed[assessment.disease_id] += 1

        day_key = assessment.created_at.date()
        bucket = trend_counts[day_key]
        bucket["total"] += 1
        bucket["pending"] += int(assessment.status == AssessmentStatus.PENDING)
        bucket["confirmed"] += int(assessment.status == AssessmentStatus.CONFIRMED)
        bucket["high_risk"] += int(tier in {"high", "critical"})

        disease_counts[assessment.disease_id] += 1
        disease_risks[assessment.disease_id].append(percent)
        _, specialty, _ = disease_identity(assessment)
        specialty_counts[specialty] += 1

    total = len(assessments)
    by_disease = []
    for disease_id, count in disease_counts.most_common():
        try:
            definition = registry.get_rule(disease_id).definition
            name = definition.name
        except KeyError:
            name = disease_id
        risks = disease_risks[disease_id]
        by_disease.append(
            DiseaseCount(
                disease_id=disease_id,
                disease_name=name,
                count=count,
                average_risk=round(sum(risks) / len(risks), 1) if risks else 0.0,
                confirmed_rate=round(disease_confirmed[disease_id] / count * 100, 1) if count else 0.0,
            )
        )

    by_specialty = [
        SpecialtyCount(
            specialty=specialty,
            specialty_label=next(
                (
                    rule.definition.specialty_label
                    for rule in registry.list_rules()
                    if rule.definition.specialty == specialty
                ),
                specialty,
            ),
            count=count,
        )
        for specialty, count in specialty_counts.most_common()
    ]

    return AnalyticsOverview(
        total_assessments=total,
        confirmed_assessments=confirmed,
        pending_assessments=total - confirmed,
        high_risk_assessments=high_risk,
        confirmation_rate=round(confirmed / total * 100, 1) if total else 0.0,
        average_risk=round(sum(risk_values) / len(risk_values), 1) if risk_values else 0.0,
        trend=[
            TrendPoint(
                date=day.isoformat(),
                total=counts["total"],
                confirmed=counts["confirmed"],
                pending=counts["pending"],
                high_risk=counts["high_risk"],
            )
            for day, counts in sorted(trend_counts.items())
        ],
        by_disease=by_disease,
        by_specialty=by_specialty,
    )
