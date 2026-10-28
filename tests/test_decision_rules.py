"""Deterministic decision rules (docs/PROCESS.md Outcomes) + GOALS 3.6 gate."""

from __future__ import annotations

import pytest
from conftest import clean_application

from loan_ops.agents.decision import deterministic_outcome
from loan_ops.checks import CHECKS
from loan_ops.models import LoanApplication


def _results_dict(**overrides):
    app = LoanApplication(**clean_application(**overrides))
    run = {check(app).check: check(app) for check in CHECKS}
    return run, app


def test_all_pass_under_50k_is_approved() -> None:
    results, app = _results_dict()
    outcome, rule = deterministic_outcome(results, app.loan_amount)
    assert outcome == "approved"
    assert "All four checks passed" in rule


def test_at_50k_is_approved_over_50k_is_refer() -> None:
    results, app = _results_dict()
    assert deterministic_outcome(results, 50_000.0)[0] == "approved"
    outcome, rule = deterministic_outcome(results, 50_000.01)
    assert outcome == "refer"
    assert "exceeds" in rule.lower()


def test_any_hard_fail_is_denied_with_cited_check() -> None:
    results, app = _results_dict(identity_doc_valid=False)
    outcome, rule = deterministic_outcome(results, app.loan_amount)
    assert outcome == "denied"
    assert "identity" in rule.lower()


@pytest.mark.parametrize(
    "overrides",
    [
        {"fraud_soft_signals": 1},
        {"credit_score": 640},
        {"legal_name_changed_recently": True},
    ],
)
def test_borderline_is_refer(overrides: dict) -> None:
    results, app = _results_dict(**overrides)
    outcome, rule = deterministic_outcome(results, app.loan_amount)
    assert outcome == "refer"
    boundary_check = next(
        name
        for name in ("identity", "credit", "fraud")
        if results[name].result_class == "refer"
    )
    assert boundary_check in rule.lower()


def test_incomplete_results_are_refer() -> None:
    results, app = _results_dict()
    results.pop("fraud")
    outcome, _ = deterministic_outcome(results, app.loan_amount)
    assert outcome == "refer"
