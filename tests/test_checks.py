"""GOALS 2.3/2.4/2.5 — check tool contract, boundary coverage, determinism."""

from __future__ import annotations

import pytest
from conftest import clean_application

from loan_ops import checks
from loan_ops.models import CheckResult, LoanApplication

RESULT_CLASSES = {"pass", "fail", "refer"}


def _app(**kw):
    return LoanApplication(**clean_application(**kw))


# --- GOALS 2.3: every check is a typed tool returning CheckResult ---


@pytest.mark.parametrize("check", checks.CHECKS, ids=lambda c: c.__name__)
def test_check_contract(check) -> None:
    result = check(_app())
    assert isinstance(result, CheckResult)
    assert result.result_class in RESULT_CLASSES
    assert result.reason.strip()
    assert result.check in ("identity", "credit", "affordability", "fraud")


# --- Identity boundaries (POLICY §1) ---


@pytest.mark.parametrize("age,expect", [(89, "pass"), (90, "pass"), (91, "fail")])
def test_proof_of_address_age_boundary(age: int, expect: str) -> None:
    assert checks.identity_check(_app(proof_of_address_age_days=age)).result_class == expect


@pytest.mark.parametrize(
    "kw,expect",
    [
        ({"identity_doc_valid": False}, "fail"),
        ({"legal_name_changed_recently": True}, "refer"),
    ],
)
def test_identity_fail_and_refer_paths(kw: dict, expect: str) -> None:
    assert checks.identity_check(_app(**kw)).result_class == expect


# --- Credit boundaries (POLICY §2) ---


@pytest.mark.parametrize(
    "score,expect",
    [(0, "fail"), (579, "fail"), (580, "refer"), (649, "refer"), (650, "pass"), (1000, "pass")],
)
def test_credit_score_boundaries(score: int, expect: str) -> None:
    assert checks.credit_check(_app(credit_score=score)).result_class == expect


@pytest.mark.parametrize(
    "kw,expect",
    [
        ({"bankruptcy_active": True}, "fail"),
        ({"default_unresolved": True}, "fail"),
    ],
)
def test_credit_hard_fail_records(kw: dict, expect: str) -> None:
    assert checks.credit_check(_app(**kw)).result_class == expect


@pytest.mark.parametrize("months,expect", [(0, "refer"), (11, "refer"), (12, "pass")])
def test_credit_history_length_boundary(months: int, expect: str) -> None:
    assert checks.credit_check(_app(credit_history_months=months)).result_class == expect


@pytest.mark.parametrize("settled,expect", [(None, "pass"), (25, "pass"), (24, "refer"), (1, "refer")])
def test_settled_default_grace_boundary(settled: int | None, expect: str) -> None:
    assert checks.credit_check(_app(default_settled_months_ago=settled)).result_class == expect


# --- Affordability boundaries (POLICY §3) ---
# income=10000, debt=2000 -> payment must push (2000 + loan/12)/10000


def test_dti_pass_at_exactly_40_percent() -> None:
    # (1000 + 36000/12) / 10000 == 0.40 -> pass (limit uses strict >)
    result = checks.affordability_check(
        _app(monthly_income=10_000, existing_monthly_debt=1_000, loan_amount=36_000)
    )
    assert result.result_class == "pass"


def test_dti_refer_band() -> None:
    # (1000 + 36001/12) / 10000 == 0.400008 -> refer
    result = checks.affordability_check(
        _app(monthly_income=10_000, existing_monthly_debt=1_000, loan_amount=36_001)
    )
    assert result.result_class == "refer"


def test_dti_fail_just_over_44_percent() -> None:
    # (1000 + 40801/12) / 10000 == 0.440008 -> hard fail
    result = checks.affordability_check(
        _app(monthly_income=10_000, existing_monthly_debt=1_000, loan_amount=40_801)
    )
    assert result.result_class == "fail"


def test_dti_at_exactly_44_percent_stays_in_refer_band() -> None:
    # (1000 + 40800/12) / 10000 == 0.44 -> in the refer band (band is 40%-44%)
    result = checks.affordability_check(
        _app(monthly_income=10_000, existing_monthly_debt=1_000, loan_amount=40_800)
    )
    assert result.result_class == "refer"


@pytest.mark.parametrize("purpose", ["gambling", "crypto trading"])
def test_ineligible_purposes_are_hard_fail(purpose: str) -> None:
    assert checks.affordability_check(_app(loan_purpose=purpose)).result_class == "fail"


def test_missing_income_documents_refer() -> None:
    assert (
        checks.affordability_check(_app(income_documents_current=False)).result_class == "refer"
    )


# --- Fraud boundaries (POLICY §4) ---


@pytest.mark.parametrize(
    "kw,expect",
    [
        ({"blacklist_match": True}, "fail"),
        ({"synthetic_identity_indicators": True}, "fail"),
        ({"fraud_soft_signals": 0}, "pass"),
        ({"fraud_soft_signals": 1}, "refer"),
        ({"fraud_soft_signals": 2}, "refer"),
        ({"fraud_soft_signals": 9}, "refer"),
    ],
)
def test_fraud_signal_boundaries(kw: dict, expect: str) -> None:
    result = checks.fraud_check(_app(**kw))
    assert result.result_class == expect
    if kw.get("fraud_soft_signals") == 2:
        assert "escalate" in result.reason.lower()


# --- GOALS 2.5: deterministic results ---


def test_checks_are_pure() -> None:
    app = _app()
    for check in checks.CHECKS:
        assert check(app) == check(app)


def test_check_order_and_names_match_process() -> None:
    assert checks.CHECK_NAMES == ("identity", "credit", "affordability", "fraud")
