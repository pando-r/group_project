from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(BACKEND_DIR / ".env", BACKEND_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "MedRisk"
    app_env: str = "development"
    log_debug: bool = False
    api_v1_prefix: str = "/api/v1"
    secret_key: str = "medrisk-local-development-secret-change-me"
    access_token_expire_minutes: int = 480
    cookie_name: str = "medrisk_token"
    cookie_secure: bool = False
    cookie_samesite: str = "lax"
    cookie_domain: str | None = None

    database_url: str = "sqlite+aiosqlite:///" + (BACKEND_DIR / "medrisk_dev.db").as_posix()
    db_echo: bool = False
    auto_create_tables: bool = True
    auto_seed: bool = True

    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    seed_doctor_username: str = "doctor"
    seed_doctor_password: str = "MedRisk2026!"
    seed_admin_username: str = "admin"
    seed_admin_password: str = "Admin2026!"

    rule_version: str = "rules-2026.11.1"
    prompt_version: str = "prompts-2026.11.2"

    llm_mock: bool = True
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_model: str = "deepseek-flash"
    llm_timeout: int = 30
    llm_max_retries: int = 2
    llm_temperature: float = 0.1
    llm_max_output_tokens: int = 2048
    llm_thinking: bool = False
    llm_backoff_seconds: float = 0.5
    llm_token_budget: int = 30000
    llm_tracing: bool = False

    agent_checkpoint_path: str = (BACKEND_DIR / "agent_checkpoints.db").as_posix()
    agent_run_timeout_seconds: int = 90
    agent_max_tool_calls: int = 8
    agent_tool_timeout_seconds: float = 10.0

    @field_validator("app_env")
    @classmethod
    def _normalise_env(cls, value: str) -> str:
        return value.strip().lower()

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
