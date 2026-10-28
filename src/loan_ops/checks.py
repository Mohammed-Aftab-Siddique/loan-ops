"""Check implementations — docs/POLICY.md rules as code.

Each check takes a LoanApplication and returns a CheckResult with a result
class of pass / fail / refer and a concrete reason string. Checks are pure:
same input -> identical CheckResult (GOALS 2.5).
"""

from __future__ import annotations

from loan_ops import policy
from loan_ops.models import CheckResult, LoanApplication

CHECK_NAMES = ("identity", "credit", "affordability", "fraud")


def identity_check(app: LoanApplication) -> CheckResult:
    """docs/POLICY.md §1 — Identity Check."""
    if not app.identity_doc_valid:
        return CheckResult(
            check="identity",
            result_class="fail",
            reason="Identity documents are expired, forged, or contradict the application.",
        )
    if app.proof_of_address_age_days > policy.PROOF_OF_ADDRESS_MAX_AGE_DAYS:
        return CheckResult(
            check="identity",
            result_class="fail",
            reason=f"Proof of address is {app.proof_of_address_age_days} days old "
            f"(older than the {policy.PROOF_OF_ADDRESS_MAX_AGE_DAYS}-day policy limit).",
        )
    if app.legal_name_changed_recently:
        return CheckResult(
            check="identity",
            result_class="refer",
            reason="Recent legal name change lacks supporting papers; verify manually.",
        )
    return CheckResult(
        check="identity",
        result_class="pass",
        reason="Identity documents valid and match application data.",
    )


def credit_check(app: LoanApplication) -> CheckResult:
    """docs/POLICY.md §2 — Credit Check."""
    if app.bankruptcy_active:
        return CheckResult(
            check="credit", result_class="fail", reason="Active bankruptcy on record."
        )
    if app.default_unresolved:
        return CheckResult(
            check="credit", result_class="fail", reason="Unresolved default on record."
        )
    if app.credit_score < policy.CREDIT_HARD_FAIL_SCORE:
        return CheckResult(
            check="credit",
            result_class="fail",
            reason=f"Credit score {app.credit_score} is below the hard-fail floor of "
            f"{policy.CREDIT_HARD_FAIL_SCORE}.",
        )
    if app.credit_history_months < policy.CREDIT_MIN_HISTORY_MONTHS:
        return CheckResult(
            check="credit",
            result_class="refer",
            reason=f"Insufficient credit history ({app.credit_history_months} months "
            f"< {policy.CREDIT_MIN_HISTORY_MONTHS}); thin file needs eyes.",
        )
    if (
        app.credit_score < policy.CREDIT_MIN_AUTO_APPROVAL_SCORE
        or (
            app.default_settled_months_ago is not None
            and app.default_settled_months_ago <= policy.CREDIT_SETTLED_DEFAULT_GRACE_MONTHS
        )
    ):
        return CheckResult(
            check="credit",
            result_class="refer",
            reason="Score 580-649 or settled default within grace period; borderline file.",
        )
    return CheckResult(
        check="credit",
        result_class="pass",
        reason="Credit score meets the approval threshold; no adverse records.",
    )


def affordability_check(app: LoanApplication) -> CheckResult:
    """docs/POLICY.md §3 — Affordability Check."""
    if app.loan_purpose in policy.INELIGIBLE_PURPOSES:
        return CheckResult(
            check="affordability",
            result_class="fail",
            reason=f"Loan purpose {app.loan_purpose!r} is ineligible by policy.",
        )
    if not app.income_documents_current:
        return CheckResult(
            check="affordability",
            result_class="refer",
            reason="Income documents partially missing; affordability unverifiable.",
        )
    payment = app.loan_amount / 12.0  # 12-month standard repayment schedule
    ratio = (app.existing_monthly_debt + payment) / app.monthly_income
    pct = ratio * 100
    if ratio > policy.DTI_HARD_FAIL_LIMIT:
        return CheckResult(
            check="affordability",
            result_class="fail",
            reason=f"DTI {pct:.1f}% exceeds the hard limit of "
            f"{policy.DTI_HARD_FAIL_LIMIT * 100:.0f}%.",
        )
    if ratio > policy.DTI_AUTO_APPROVAL_LIMIT:
        return CheckResult(
            check="affordability",
            result_class="refer",
            reason=f"DTI {pct:.1f}% falls in the refer band "
            f"({policy.DTI_AUTO_APPROVAL_LIMIT * 100:.0f}%-"
            f"{policy.DTI_HARD_FAIL_LIMIT * 100:.0f}%).",
        )
    return CheckResult(
        check="affordability",
        result_class="pass",
        reason=f"DTI {pct:.1f}% is within the {policy.DTI_AUTO_APPROVAL_LIMIT * 100:.0f}% limit.",
    )


def fraud_check(app: LoanApplication) -> CheckResult:
    """docs/POLICY.md §4 — Fraud Check."""
    if app.blacklist_match or app.synthetic_identity_indicators:
        return CheckResult(
            check="fraud",
            result_class="fail",
            reason="Confirmed blacklist match or synthetic identity indicators.",
        )
    if app.fraud_soft_signals >= policy.FRAUD_SOFT_SIGNAL_ESCALATE_TO_HARD:
        return CheckResult(
            check="fraud",
            result_class="refer",
            reason=f"{app.fraud_soft_signals} soft signals — escalate for hard-fail review.",
        )
    if app.fraud_soft_signals == 1:
        return CheckResult(
            check="fraud",
            result_class="refer",
            reason="Single soft fraud signal; manual verification required.",
        )
    return CheckResult(
        check="fraud", result_class="pass", reason="No fraud signals detected."
    )


CHECKS = (
    identity_check,
    credit_check,
    affordability_check,
    fraud_check,
)


def run_all_checks(app: LoanApplication) -> tuple[str, ...]:
    """Run the four checks in process order and return result classes."""
    return tuple(check(app).result_class for check in CHECKS)


__all__ = [
    "CHECKS",
    "CHECK_NAMES",
    "identity_check",
    "credit_check",
    "affordability_check",
    "fraud_check",
    "run_all_checks",
]
