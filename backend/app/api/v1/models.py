from __future__ import annotations

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.schemas.model import ModelsResponse
from app.services import model_service

router = APIRouter()


@router.get("", response_model=ModelsResponse)
async def get_models(_: CurrentUser) -> ModelsResponse:
    return model_service.get_models()
