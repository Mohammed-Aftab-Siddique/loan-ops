"""GOALS 3.5 + docs/PROC.md steps 6-8: persistence, complete audit trail,
referral queue integrity (human-only resolution)."""

from __future__ import annotations

import pytest
from conftest import clean_application
from fakes import ScriptedToolsModel

from loan_ops import pipeline, records


@pytest.fixture(autouse=True)
def scripted_agent(monkeypatch):
    """Deterministic scripted model for pipeline tests."""
    from loan_ops.agents import factory as fac

    monkeypatch.setattr(
        fac,
        "build_chat_model",
        lambda settings=None: ScriptedToolsModel("approved", "scripted rule"),
    )
    yield


def test_full_pipeline_writes_complete_audit_trail() -> None:
    result = pipeline.process(clean_application())
    app_id = result["application_id"]

    assert result["outcome"] == "approved"
    assert len(result["check_results"]) == 4
    assert result["audit_events"] == len(records.get_audit(app_id))

    stored = records.get_application(app_id)
    assert stored is not None
    assert stored["outcome"] == "approved"
    assert {cr["check"] for cr in stored["check_results"]} == {
        "identity", "credit", "affordability", "fraud",
    }

    audit = records.get_audit(app_id)
    events = {entry["event"] for entry in audit}
    assert {"application_received", "checks_executed", "decision_recorded"} <= events
    last_decision = [e for e in audit if e["event"] == "decision_recorded"][-1]
    assert last_decision["detail"]["outcome"] == "approved"
    assert last_decision["detail"]["decided_by"] == "agent"
    assert last_decision["detail"]["provider"] == result["provider"]


def test_referral_entering_and_leaving_the_underwriter_queue() -> None:
    refer = pipeline.process(clean_application(fraud_soft_signals=1))
    rid = refer["application_id"]
    assert refer["outcome"] == "refer"
    assert rid in {r["id"] for r in records.referral_queue()}

    with pytest.raises(ValueError):
        records.resolve_referral(rid, "maybe", "uw-1")
    records.resolve_referral(rid, "approved", "uw-1")

    stored = records.get_application(rid)
    assert stored["outcome"] == "approved" and stored["state"] == "resolved"
    assert rid not in {r["id"] for r in records.referral_queue()}
    assert any(entry["actor"] == "uw-1" for entry in records.get_audit(rid))


def test_non_referral_cannot_be_resolved_by_underwriter() -> None:
    result = pipeline.process(clean_application())
    with pytest.raises(ValueError):
        records.resolve_referral(result["application_id"], "approved", "uw-1")
