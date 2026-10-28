"""Shared test fixtures: isolated DB, clean settings, scripted fake models."""

from __future__ import annotations

from typing import Any

import pytest

from loan_ops import config as config_mod
from loan_ops import store as store_mod


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch: pytest.MonkeyPatch):
    """Point the app at a throwaway DB and reset all caches per test."""
    monkeypatch.setenv("LOAN_OPS_DB_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    config_mod.reset_settings_cache()
    store_mod.reset_engine_cache()
    from loan_ops.store import create_all

    reset_settings = config_mod.get_settings()  # fresh env values
    assert reset_settings.db_url.startswith("sqlite:///")
    create_all()
    yield
    config_mod.reset_settings_cache()
    store_mod.reset_engine_cache()


def clean_application(**overrides: Any) -> dict[str, Any]:
    """A base application profile that passes all four checks."""
    payload: dict[str, Any] = {
        "applicant_name": "Jane Doe",
        "applicant_id_number": "ID-123456",
        "identity_doc_valid": True,
        "proof_of_address_age_days": 10,
        "legal_name_changed_recently": False,
        "credit_score": 720,
        "bankruptcy_active": False,
        "default_unresolved": False,
        "default_settled_months_ago": None,
        "credit_history_months": 60,
        "monthly_income": 10_000.0,
        "income_documents_current": True,
        "existing_monthly_debt": 1_000.0,
        "loan_amount": 10_000.0,
        "loan_purpose": "home improvement",
        "blacklist_match": False,
        "synthetic_identity_indicators": False,
        "fraud_soft_signals": 0,
    }
    payload.update(overrides)
    return payload
