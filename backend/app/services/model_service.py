from __future__ import annotations

from app.core.config import settings
from app.rules import registry
from app.schemas.model import ModelCard, ModelsResponse


def get_models() -> ModelsResponse:
    mode = "mock" if settings.llm_mock else "live"
    return ModelsResponse(
        llm_mode=mode,
        llm_model=settings.llm_model if not settings.llm_mock else "mock-clinical-v1",
        prompt_version=settings.prompt_version,
        rule_version=registry.ACTIVE_RULE_VERSION,
        cards=[
            ModelCard(
                id="rules",
                name="确定性规则引擎",
                kind="rules",
                status="active",
                version=registry.ACTIVE_RULE_VERSION,
                description="8 个病种的纯函数评估器，输出版本化三层结果与规则引用。",
            ),
            ModelCard(
                id="llm",
                name="报告草稿语言模型",
                kind="llm",
                status="mock" if settings.llm_mock else "configured",
                version=settings.llm_model if not settings.llm_mock else "mock-clinical-v1",
                description=(
                    "已接入 LangGraph Agent（Mock 模型）：只调用 tools 读取评估与证据，"
                    "草稿经数值/引用校验后进入医生复核；不直接写库。"
                    if settings.llm_mock
                    else (
                        "已接入 DeepSeek（OpenAI 兼容端点）：提示词仅含脱敏患者标识，"
                        "草稿经数值/引用校验后进入医生复核；不直接写库。"
                    )
                ),
            ),
            ModelCard(
                id="rag",
                name="指南向量检索",
                kind="rag",
                status="pending",
                version="pgvector / 1024d",
                description="将在第 8 步启用；引用逐条绑定到指南 chunk 或规则条目。",
            ),
        ],
    )
