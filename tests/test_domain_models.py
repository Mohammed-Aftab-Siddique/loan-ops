"""GOALS 2.1/2.2 — outcome contract and single source of policy truth."""

from __future__ import annotations

import pytest
from conftest import clean_application
from pydantic import ValidationError

from loan_ops import policy
from loan_ops.models import CheckResult, Decision, LoanApplication


def test_outcome_literal_accepts_only_the_three_contract_values() -> None:
    for value in ("approved", "denied", "refer"):
        decision = Decision(
            application_id="1", outcome=value, rule="r", check_results=[]
        )  # type: ignore[arg-type]
        assert decision.outcome == value

    for bad in ("APPROVED", "maybe", "", "reject"):
        with pytest.raises(ValidationError):
            Decision(application_id="1", outcome=bad, rule="r")  # type: ignore[arg-type]


def test_check_result_class_is_limited_to_pass_fail_refer() -> None:
    CheckResult(check="credit", result_class="pass", reason="ok")
    with pytest.raises(ValidationError):
        CheckResult(check="credit", result_class="maybe", reason="ok")  # type: ignore[arg-type]


def test_policy_values_match_docs() -> None:
    """Frozen numbers from docs/POLICY.md — changing them is deliberate."""
    assert policy.CREDIT_MIN_AUTO_APPROVAL_SCORE == 650
    assert policy.CREDIT_HARD_FAIL_SCORE == 580
    assert policy.CREDIT_MIN_HISTORY_MONTHS == 12
    assert policy.CREDIT_SETTLED_DEFAULT_GRACE_MONTHS == 24
    assert policy.DTI_AUTO_APPROVAL_LIMIT == 0.40
    assert policy.DTI_HARD_FAIL_LIMIT == 0.44
    assert policy.AUTO_APPROVAL_MAX_AMOUNT == 50_000.0
    assert policy.FRAUD_SOFT_SIGNAL_ESCALATE_TO_HARD == 2
    assert policy.PROOF_OF_ADDRESS_MAX_AGE_DAYS == 90
    assert policy.VALID_OUTCOMES == frozenset({"approved", "denied", "refer"})


def test_checks_read_thresholds_from_policy_module_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Raise the approval threshold -> 700 becomes borderline (proves the
    check consults the policy module, not an inline number)."""
    from loan_ops import checks

    monkeypatch.setattr(policy, "CREDIT_MIN_AUTO_APPROVAL_SCORE", 750)
    result = checks.credit_check(LoanApplication(**clean_application(credit_score=700)))
    assert result.result_class == "refer"


def test_application_payload_rejects_non_positive_money() -> None:
    with pytest.raises(ValidationError):
        LoanApplication(**clean_application(loan_amount=0))


def test_decision_requires_audit_rule_text() -> None:
    with pytest.raises(ValidationError):
        Decision(application_id="1", outcome="denied", rule="")
