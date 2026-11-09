from __future__ import annotations

from fastapi import APIRouter, Response

from app.api.deps import CurrentUser, DbSession
from app.core.config import settings
from app.core.security import create_access_token
from app.schemas.auth import LoginRequest, UserRead
from app.schemas.common import MessageResponse
from app.services.auth_service import authenticate

router = APIRouter()


@router.post("/login", response_model=UserRead)
async def login(payload: LoginRequest, response: Response, session: DbSession) -> UserRead:
    user = await authenticate(session, payload.username, payload.password)
    token = create_access_token(user.id, user.role)
    response.set_cookie(
        key=settings.cookie_name,
        value=token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,  # type: ignore[arg-type]
        path="/",
        domain=settings.cookie_domain,
    )
    return UserRead.model_validate(user)


@router.post("/logout", response_model=MessageResponse)
async def logout(response: Response) -> MessageResponse:
    response.delete_cookie(
        key=settings.cookie_name,
        path="/",
        domain=settings.cookie_domain,
    )
    return MessageResponse(message="已退出登录")


@router.get("/me", response_model=UserRead)
async def me(user: CurrentUser) -> UserRead:
    return UserRead.model_validate(user)
