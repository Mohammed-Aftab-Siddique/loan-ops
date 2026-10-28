"""Policy constants — the single source of truth for check thresholds.

Numbers mirror docs/POLICY.md. Only this module may reference raw thresholds;
check code must use these names (GOALS 2.2).
"""

from __future__ import annotations

# --- Credit check (docs/POLICY.md §2) ---
CREDIT_MIN_AUTO_APPROVAL_SCORE = 650
CREDIT_HARD_FAIL_SCORE = 580
CREDIT_MIN_HISTORY_MONTHS = 12
CREDIT_SETTLED_DEFAULT_GRACE_MONTHS = 24

# --- Affordability check (docs/POLICY.md §3) ---
DTI_AUTO_APPROVAL_LIMIT = 0.40
DTI_HARD_FAIL_LIMIT = 0.44  # auto-approval limit + 10%
AUTO_APPROVAL_MAX_AMOUNT = 50_000.0
INCOME_DOC_LOOKBACK_PAYS = ("last 3 months",)
INELIGIBLE_PURPOSES = {"gambling", "crypto trading"}

# --- Fraud check (docs/POLICY.md §4) ---
FRAUD_SOFT_SIGNAL_ESCALATE_TO_HARD = 2

# --- Identity check (docs/POLICY.md §1) ---
PROOF_OF_ADDRESS_MAX_AGE_DAYS = 90

# --- Process (docs/PROCESS.md) ---
OUTCOME_APPROVED = "approved"
OUTCOME_DENIED = "denied"
OUTCOME_REFER = "refer"
VALID_OUTCOMES = frozenset({OUTCOME_APPROVED, OUTCOME_DENIED, OUTCOME_REFER})
