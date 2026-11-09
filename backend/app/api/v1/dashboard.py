from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser, DbSession
from app.schemas.dashboard import DashboardResponse
from app.services import dashboard_service

router = APIRouter()


@router.get("", response_model=DashboardResponse)
async def dashboard(session: DbSession, _: CurrentUser) -> DashboardResponse:
    return await dashboard_service.build_dashboard(session)
