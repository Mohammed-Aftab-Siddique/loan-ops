"""Pydantic domain models: applications, check results, outcomes.

The outcome contract (docs/PROCESS.md, GOALS 2.1): an outcome is exactly
"approved" | "denied" | "refer" — anything else fails validation.
"""

from __future__ import annotations

import enum
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from loan_ops.policy import VALID_OUTCOMES


class Outcome(str, enum.Enum):
    APPROVED = "approved"
    DENIED = "denied"
    REFER = "refer"


ResultClass = Literal["pass", "fail", "refer"]


class _ValidatedOutcome(str):
    pass


class CheckResult(BaseModel):
    """Result of one of the four checks — never a bare boolean (GOALS 2.3)."""

    check: Literal["identity", "credit", "affordability", "fraud"]
    result_class: ResultClass
    reason: str = Field(min_length=1)


class LoanApplication(BaseModel):
    application_id: str | None = None
    applicant_name: str = Field(min_length=1)
    applicant_id_number: str = Field(min_length=1)
    identity_doc_valid: bool
    proof_of_address_age_days: int = Field(ge=0)
    legal_name_changed_recently: bool = False
    credit_score: int = Field(ge=0, le=1000)
    bankruptcy_active: bool = False
    default_unresolved: bool = False
    default_settled_months_ago: int | None = Field(default=None, ge=0)
    credit_history_months: int = Field(ge=0)
    monthly_income: float = Field(gt=0)
    income_documents_current: bool = True
    existing_monthly_debt: float = Field(ge=0)
    loan_amount: float = Field(gt=0)
    loan_purpose: str = Field(min_length=1)
    blacklist_match: bool = False
    synthetic_identity_indicators: bool = False
    fraud_soft_signals: int = Field(default=0, ge=0)

    @field_validator("loan_purpose")
    @classmethod
    def _purpose_lawful(cls, v: str) -> str:
        return v.strip().lower()


class Decision(BaseModel):
    application_id: str
    outcome: Literal["approved", "denied", "refer"]
    rule: str = Field(min_length=1)
    check_results: list[CheckResult] = []
    model: str = ""
    provider: str = ""

    @field_validator("outcome")
    @classmethod
    def _valid_outcome(cls, v: str) -> str:
        if v not in VALID_OUTCOMES:
            raise ValueError(f"invalid outcome {v!r}; expected one of {sorted(VALID_OUTCOMES)}")
        return v
