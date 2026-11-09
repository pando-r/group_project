from __future__ import annotations

import ipaddress
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import TokenError, decode_access_token, user_id_from_payload
from app.db.session import get_db
from app.models.user import User, UserRole

DbSession = Annotated[AsyncSession, Depends(get_db)]


def _bearer_token(request: Request) -> str | None:
    header = request.headers.get("Authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None
    return None


async def get_current_user(request: Request, session: DbSession) -> User:
    token = request.cookies.get(settings.cookie_name) or _bearer_token(request)
    if not token:
        raise UnauthorizedError()
    try:
        payload = decode_access_token(token)
        user_id: UUID = user_id_from_payload(payload)
    except TokenError as exc:
        raise UnauthorizedError(str(exc)) from exc
    user = await session.get(User, user_id)
    if user is None:
        raise UnauthorizedError("登录用户不存在或已停用")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


async def require_doctor(user: CurrentUser) -> User:
    if user.role != UserRole.DOCTOR:
        raise ForbiddenError("该操作仅限医生执行")
    return user


async def require_admin(user: CurrentUser) -> User:
    if user.role != UserRole.ADMIN:
        raise ForbiddenError("该操作仅限管理员执行")
    return user


DoctorUser = Annotated[User, Depends(require_doctor)]
AdminUser = Annotated[User, Depends(require_admin)]


def request_ip(request: Request) -> str | None:
    if request.client is None:
        return None
    try:
        return str(ipaddress.ip_address(request.client.host))
    except ValueError:
        return None
