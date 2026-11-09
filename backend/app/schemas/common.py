from __future__ import annotations

from pydantic import BaseModel


class PageResponse[T](BaseModel):
    page: int
    size: int
    total: int
    records: list[T]


class MessageResponse(BaseModel):
    message: str
