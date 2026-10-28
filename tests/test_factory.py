"""Factory tests — provider wiring built correctly (no network calls)."""

from __future__ import annotations

import pytest

from loan_ops.agents import factory
from loan_ops.config import Settings


def test_build_ollama_model_by_default() -> None:
    model = factory.build_chat_model(Settings(llm_provider="ollama", llm_model="qwen3.5:0.8b"))
    assert type(model).__name__ == "ChatOllama"
    assert model.model == "qwen3.5:0.8b"


def test_build_openrouter_model_with_key(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    model = factory.build_chat_model(
        Settings(
            llm_provider="openrouter",
            llm_model="mistralai/mistral-small",
            openrouter_api_key="sk-test",
        )
    )
    assert type(model).__name__ == "ChatOpenAI"
    assert model.model_name == "mistralai/mistral-small"


def test_unsupported_provider_raises_clear_error() -> None:
    with pytest.raises(ValueError, match="not supported"):
        factory.build_chat_model(Settings(llm_provider="bedrock"))


def test_missing_openrouter_key_raises(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        factory.build_chat_model(Settings(llm_provider="openrouter", openrouter_api_key=""))
