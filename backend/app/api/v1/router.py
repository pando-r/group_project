from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    agent,
    analytics,
    assessments,
    audit,
    auth,
    dashboard,
    models,
    patients,
    registry,
)

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(patients.router, prefix="/patients", tags=["patients"])
api_router.include_router(assessments.router, prefix="/assessments", tags=["assessments"])
api_router.include_router(agent.router, prefix="/agent", tags=["agent"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["dashboard"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["analytics"])
api_router.include_router(registry.router, prefix="/registry", tags=["registry"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(audit.router, prefix="/audit", tags=["audit"])
