# Procedure: Agent Run-through

This is the mandatory step-by-step procedure for the **loan-processing agent** (human or AI) responsible for processing loan applications. **Always read this file in full, and re-read the reference documents listed below, before processing any loan application.** It does not apply to development work on this codebase.

## Required Reading

Before touching any task, read in order:

1. `docs/PROCESS.md` – the approval process and its four checks.
2. `docs/POLICY.md` – thresholds and rules for each check.
3. `docs/TECH_STACK.md` – stack constraints (uv, Python, LangChain `create_agent`).

Skipping the reading step is a process violation; if any document is ambiguous, stop and ask, do not guess.

## Loan Application Procedure

Work through these steps for each application. Do not skip or reorder steps.

1. **Load context** – Read the three documents above and pull the full application record.
2. **Validate intake** – Confirm all required fields are present (identity, amounts, income, authorization). Incomplete → return to applicant, stop.
3. **Run checks in order** – Identity → Credit → Affordability → Fraud. Execute each check with a tool, never by estimation. Record the raw result of each.
4. **Classify each result** – Against `POLICY.md`: pass / fail (hard) / refer (borderline). Stop early on a hard failure.
5. **Decide the outcome** – Apply the decision rules:
   - All pass → `approved`.
   - Any hard fail → `denied` (record the failing rule).
   - Anything borderline/marginal, or amount > $50,000 → `refer` with a written summary for the underwriter.
6. **Record the decision** – Write the outcome, every check result, and the rule or agent reasoning that produced it to the audit log. No decision may be logged without its justifying tool results.
7. **Notify** – Approved or denied → notify the applicant with the outcome (and reason if denied). Referred → hand off to the underwriter queue; do not contact the applicant about the referral.
8. **Verify** – Confirm the audit entry exists and is complete before marking the task done.

## Rules of Conduct

- Never invent check results; every result must come from an executed tool or recorded data.
- Never flip a `refer` to `approved` or `denied` on your own — only a human underwriter decides referred cases.
- Every task ends with either a completed run-through or an explicitly skipped step with a logged reason.
