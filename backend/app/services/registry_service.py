from __future__ import annotations

from typing import Any

from app.rules import registry


def get_registry() -> dict[str, Any]:
    return registry.public_registry()
