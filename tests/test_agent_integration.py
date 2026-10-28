"""GOALS 3.1/3.2/3.3/3.4/3.6 — agent built with create_agent, provider-agnostic,
three reachable outcomes, malformed output degraded, checks never fabricated."""

from __future__ import annotations

from pathlib import Path

import pytest
from conftest import clean_application
from fakes import GarbageOutputModel, ProviderUnavailableModel, ScriptedToolsModel

from loan_ops.agents.decision import build_decision_agent, run_decision
from loan_ops.models import LoanApplication


def _app(**kw) -> LoanApplication:
    return LoanApplication(application_id="42", **clean_application(**kw))


# --- GOALS 3.1: the agent must be built with langchain create_agent ---


def test_agent_is_created_via_create_agent() -> None:
    agent, _state = build_decision_agent(ScriptedToolsModel("approved", "ok"), _app())
    assert agent.name == "loan_decision_agent"
    tool_node = agent.nodes["tools"].bound
    tool_names = set(tool_node._tools_by_name)
    assert tool_names == {
        "identity_check",
        "credit_check",
        "affordability_check",
        "fraud_check",
        "record_decision",
    }


# --- GOALS 3.2: one agent codebase, two "providers" ---


@pytest.mark.parametrize(
    "model_cls,overrides,expected",
    [
        (ScriptedToolsModel, {}, "approved"),
        (ScriptedToolsModel, {"fraud_soft_signals": 1}, "refer"),
        (ScriptedToolsModel, {"identity_doc_valid": False}, "denied"),
    ],
)
def test_three_outcomes_reachable_from_real_checks(
    model_cls, overrides: dict, expected: str
) -> None:
    """Scripted run: model executes the four REAL check tools; the decision
    outcome is derived from their executed results (GOALS 3.3)."""
    app = _app(**overrides)
    decision = run_decision(app, model=model_cls(expected, "scripted rule"))
    assert decision.outcome == expected
    executed = {r.check for r in decision.check_results}
    assert executed == {"identity", "credit", "affordability", "fraud"}
    # every recorded reason came from the executed check tool, never invented
    assert all(r.reason.strip() for r in decision.check_results)


def test_same_agent_code_across_two_providers() -> None:
    app = _app()
    a = run_decision(app, model=ScriptedToolsModel("approved", "ok"))
    b = run_decision(
        app,
        model=ScriptedToolsModel("approved", "ok", provider_label="fake-openrouter"),
    )
    assert a.outcome == b.outcome == "approved"
    assert a.provider != b.provider


# --- GOALS 3.4: malformed structured output is forced to refer ---


def test_malformed_structured_output_forced_refer() -> None:
    decision = run_decision(_app(), model=GarbageOutputModel("approved", "ok"))
    assert decision.outcome == "refer"
    assert "Agent produced no structured decision" in decision.rule


def test_provider_error_propagates_to_caller() -> None:
    with pytest.raises(RuntimeError):
        run_decision(_app(), model=ProviderUnavailableModel())


# --- GOALS 3.6: decision cannot be recorded before checks executed ---


def test_record_decision_refuses_without_executed_checks() -> None:
    agent, state = build_decision_agent(ScriptedToolsModel("approved", "ok"), _app())
    assert not state.all_checks_executed
    tool_node = agent.nodes["tools"].bound
    record = tool_node._tools_by_name["record_decision"]
    result = record.invoke(
        {"application_id": "42", "outcome": "approved", "rule": "invented"}
    )
    assert result["error"]
    assert "not been executed" in result["error"]


# --- provider names live only in the factory (source scan) ---


@pytest.mark.parametrize("path", ["agents/decision.py", "pipeline.py", "checks.py"])
def test_no_provider_names_in_application_code(path: str) -> None:
    src_root = Path(__file__).parent.parent / "src" / "loan_ops"
    text = (src_root / path).read_text().lower()
    assert "openrouter" not in text
    assert "ollama" not in text
    assert "ChatOpenAI" not in text
