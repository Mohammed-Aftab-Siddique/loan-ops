# Loan Approval Process

This document describes the process for approving a loan application in the **loan-ops** project. Every application must end in exactly one of three outcomes: **approved**, **denied**, or **refer** (sent for human review).

## Application Intake

An application is complete only when it contains:

- Applicant identity and contact details
- Requested loan amount, term, and purpose
- Declared income and employment status
- Authorization to run credit and verification checks

Incomplete applications are returned to the applicant and do not enter review.

## Checks

Run the following checks in order. Stop and record the result of each.

1. **Identity check** – Applicant's identity is verified against submitted documents.
2. **Credit check** – Credit score meets the minimum threshold (650) and there is no active bankruptcy or unresolved default.
3. **Affordability check** – Monthly debt payments plus the proposed loan payment must not exceed 40% of verified monthly income.
4. **Fraud check** – No flags from fraud screening (mismatched identity data, suspicious application patterns).

## Outcomes

- **Approve** – All four checks pass. Issue the loan at the standard rate for the applicant's credit tier.
- **Deny** – Any single check fails with a *hard* reason (failed identity, active bankruptcy, confirmed fraud, or affordability over limit by more than 10%). Notify the applicant with the denial reason.
- **Refer** – Send to a human underwriter when:
  - Any check fails for a *soft* or borderline reason (e.g., missing documents but identity plausible, affordability within 10% over limit, thin credit file).
  - Two or more checks return marginal results.
  - The loan amount exceeds the automated limit ($50,000), regardless of check results.

A referred application is decided only by a human underwriter; automation never approves or denies it.

## Audit

Record every application, each check result, and the final outcome (with the deciding rule or underwriter ID) in the audit log.

## Running Tests

```bash
uv run pytest -q --cov=loan_ops   # tests + coverage (gate: ≥90% on checks/agents/store)
uv run ruff check .               # lint; 0 warnings tolerated
```

*Note: this document used to be a starter template; it now describes the real loan-ops process. Build sequence and goals live in `docs/PLAN.md` and `docs/GOALS.md`.*
