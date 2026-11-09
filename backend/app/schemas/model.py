from __future__ import annotations

from pydantic import BaseModel


class ModelCard(BaseModel):
    id: str
    name: str
    kind: str
    status: str
    version: str
    description: str


class ModelsResponse(BaseModel):
    llm_mode: str
    llm_model: str
    prompt_version: str
    rule_version: str
    cards: list[ModelCard]
