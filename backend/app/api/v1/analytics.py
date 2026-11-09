from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, DbSession
from app.schemas.analytics import AnalyticsOverview
from app.services import analytics_service

router = APIRouter()


@router.get("/overview", response_model=AnalyticsOverview)
async def overview(
    session: DbSession,
    _: CurrentUser,
    date_from: date | None = Query(default=None, alias="from"),
    date_to: date | None = Query(default=None, alias="to"),
) -> AnalyticsOverview:
    end = date_to or date.today()
    start = date_from or (end - timedelta(days=29))
    return await analytics_service.overview(session, start=start, end=end)
