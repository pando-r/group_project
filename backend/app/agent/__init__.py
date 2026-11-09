from __future__ import annotations

import os

from app.core.config import settings

# Tracing is opt-in. Mock mode must be completely offline even when the
# developer shell exports tracing credentials, and live model calls must not
# ship prompts to a third-party tracer unless LLM_TRACING is explicitly set.
if settings.llm_mock or not settings.llm_tracing:
    os.environ["LANGSMITH_TRACING"] = "false"
    os.environ["LANGCHAIN_TRACING_V2"] = "false"
    os.environ["ANONYMIZED_TELEMETRY"] = "false"

__all__ = ["settings"]
