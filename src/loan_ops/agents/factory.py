"""LLM provider factory — the only module allowed to know about providers.

Selection (docs/TECH_STACK.md): LOAN_OPS_LLM_PROVIDER = ollama (default) |
openrouter. All application, check, and agent logic depends only on this
factory's returned chat-model interface — never on a concrete provider
class (GOALS 3.2).
"""

from __future__ import annotations

import os

from langchain_core.language_models.chat_models import BaseChatModel

from loan_ops.config import Settings, get_settings


def build_chat_model(settings: Settings | None = None) -> BaseChatModel:
    """Return the configured chat model.

    Raises a clear error for unsupported providers or a missing API key;
    callers surface this at startup (fail fast, GOALS 5.2).
    """
    settings = settings or get_settings()
    settings.validate_provider()

    if settings.llm_provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=settings.llm_model,
            base_url=os.environ.get("OLLAMA_BASE_URL", settings.ollama_base_url),
            temperature=settings.llm_temperature,
        )

    if settings.llm_provider == "openrouter":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(
            model=settings.llm_model,
            api_key=os.environ["OPENROUTER_API_KEY"],
            base_url=settings.openrouter_base_url,  # OpenAI-compatible endpoint
            temperature=settings.llm_temperature,
            default_headers={"HTTP-Referer": "http://localhost", "X-Title": "loan-ops"},
        )

    raise ValueError(f"Unknown LLM provider: {settings.llm_provider!r}")
