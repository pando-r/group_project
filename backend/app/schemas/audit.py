from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AuditLogRead(BaseModel):
    id: UUID
    assessment_id: UUID
    actor_id: UUID
    actor_name: str
    action: str
    detail: dict[str, Any]
    created_at: datetime
