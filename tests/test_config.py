"""GOALS 1.3 / 5.2 — env-driven configuration and fail-fast provider setup."""

from __future__ import annotations

import pytest

from loan_ops.config import Settings, get_settings, reset_settings_cache


def test_invalid_provider_fails_fast() -> None:
    settings = Settings(llm_provider="aws")
    with pytest.raises(ValueError, match="not supported"):
        settings.validate_provider()


def test_openrouter_without_key_fails_fast() -> None:
    settings = Settings(llm_provider="openrouter", openrouter_api_key="")
    with pytest.raises(ValueError, match="OPENROUTER_API_KEY"):
        settings.validate_provider()


def test_openrouter_with_key_passes_validation() -> None:
    settings = Settings(llm_provider="openrouter", openrouter_api_key="sk-test")
    settings.validate_provider()


def test_env_changes_are_picked_up(monkeypatch: pytest.MonkeyPatch) -> None:
    """Model/provider/DB selection is env-driven without code edits (1.3)."""
    monkeypatch.setenv("LOAN_OPS_LLM_PROVIDER", "openrouter")
    monkeypatch.setenv("LOAN_OPS_MODEL", "mistral/mistral-small")
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-env")
    monkeypatch.setenv("LOAN_OPS_DB_URL", "sqlite:///env-test.db")
    reset_settings_cache()
    try:
        settings = get_settings()
        assert settings.llm_provider == "openrouter"
        assert settings.llm_model == "mistral/mistral-small"
        assert settings.openrouter_api_key == "sk-env"
        assert settings.db_url == "sqlite:///env-test.db"
    finally:
        monkeypatch.delenv("LOAN_OPS_LLM_PROVIDER", raising=False)
        monkeypatch.delenv("LOAN_OPS_MODEL", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        monkeypatch.delenv("LOAN_OPS_DB_URL", raising=False)
        reset_settings_cache()


def test_ollama_default_needs_no_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LOAN_OPS_LLM_PROVIDER", "ollama")
    reset_settings_cache()
    try:
        settings = get_settings()
        settings.validate_provider()  # must not raise
    finally:
        monkeypatch.delenv("LOAN_OPS_LLM_PROVIDER", raising=False)
        reset_settings_cache()
