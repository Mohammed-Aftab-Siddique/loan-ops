"""Loan-ops application configuration.

Everything is env-driven (see docs/TECH_STACK.md): model/provider endpoints and
secrets come from the environment only — never from the repo (GOALS 1.3, 5.2).
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LOAN_OPS_",
        extra="ignore",
        populate_by_name=True,
    )

    app_name: str = "loan-ops"
    db_url: str = Field(
        default="sqlite:///./loan_ops.db",
        validation_alias=AliasChoices("LOAN_OPS_DB_URL"),
    )

    #: LLM provider selection: "ollama" (default) | "openrouter"
    llm_provider: str = Field(
        default="ollama",
        validation_alias=AliasChoices("LOAN_OPS_LLM_PROVIDER"),
    )
    llm_model: str = Field(
        default="qwen3.5:4b",
        validation_alias=AliasChoices("LOAN_OPS_MODEL"),
    )
    llm_temperature: float = 0.0

    #: Endpoints / credentials for the selected provider
    ollama_base_url: str = Field(
        default="http://localhost:11434",
        validation_alias=AliasChoices("OLLAMA_BASE_URL", "LOAN_OPS_OLLAMA_BASE_URL"),
    )
    openrouter_base_url: str = Field(
        default="https://openrouter.ai/api/v1",
        validation_alias=AliasChoices(
            "OPENROUTER_BASE_URL", "LOAN_OPS_OPENROUTER_BASE_URL"
        ),
    )
    openrouter_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("OPENROUTER_API_KEY", "LOAN_OPS_OPENROUTER_API_KEY"),
    )

    host: str = "127.0.0.1"  # LOAN_OPS_HOST
    port: int = 8000  # LOAN_OPS_PORT

    def validate_provider(self) -> None:
        """Fail fast on a misconfigured provider (GOALS 5.2)."""
        if self.llm_provider not in {"ollama", "openrouter"}:
            raise ValueError(
                f"LOAN_OPS_LLM_PROVIDER={self.llm_provider!r} is not supported. "
                "Supported values: ollama, openrouter."
            )
        if self.llm_provider == "openrouter" and not self.openrouter_api_key:
            raise ValueError(
                "LOAN_OPS_LLM_PROVIDER=openrouter requires OPENROUTER_API_KEY "
                "in the environment."
            )


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    get_settings.cache_clear()
