from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from app.api.deps import CurrentUser
from app.services import registry_service

router = APIRouter()


@router.get("")
async def get_registry(_: CurrentUser) -> dict[str, Any]:
    return registry_service.get_registry()
