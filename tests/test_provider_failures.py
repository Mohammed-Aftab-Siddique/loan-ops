"""GOALS 5.1/5.2 — provider failures degrade to refer; config fails fast."""

from __future__ import annotations

from conftest import clean_application
from fakes import ProviderUnavailableModel

from loan_ops import pipeline, records


def test_unreachable_provider_degrades_to_refer(monkeypatch) -> None:
    from loan_ops.agents import factory as fac

    def broken(settings=None):
        raise RuntimeError("Ollama is down")

    monkeypatch.setattr(fac, "build_chat_model", broken)
    result = pipeline.process(clean_application())
    app_id = result["application_id"]

    assert result["outcome"] == "refer"
    assert result["provider"] == "none"
    assert "provider unavailable" in result["rule"].lower()
    # the four checks were still executed and recorded — nothing invented
    assert len(result["check_results"]) == 4
    audit = records.get_audit(app_id)
    assert {"application_received", "checks_executed", "decision_recorded"} <= {
        e["event"] for e in audit
    }
    # the degraded decision is still referable to a human underwriter
    records.resolve_referral(app_id, "approved", "uw-1")
    assert records.get_application(app_id)["outcome"] == "approved"


def test_provider_model_error_inside_run_degrades_to_refer(monkeypatch) -> None:
    """Model wiring fails after startup: run must end refer, never crash."""
    from loan_ops.agents import factory as fac

    monkeypatch.setattr(
        fac, "build_chat_model", lambda settings=None: ProviderUnavailableModel()
    )
    result = pipeline.process(clean_application())
    assert result["outcome"] == "refer"
