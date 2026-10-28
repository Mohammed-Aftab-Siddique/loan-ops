# Loan Policy

This document defines the policies behind the four checks described in `docs/PROCESS.md`. The process decides *what* to check; this document decides *how* each check is applied and what counts as pass, fail (hard), or borderline (refer).

## 1. Identity Check Policy

- Identification must include one government-issued photo ID and one proof of address dated within the last 90 days.
- Name, date of birth, and address on documents must match the application exactly; minor typos are acceptable if explicable.
- **Pass** – documents valid and data matches.
- **Fail (hard)** – documents are expired, forged, or identity data directly contradicts the application.
- **Refer** – documents partially legible, address out of service area, or recently changed legal name without supporting papers.

## 2. Credit Check Policy

- A minimum credit score of **650** is required for automated approval.
- **Hard fail** triggers: active bankruptcy, unresolved default, or score below **580**.
- **Refer** triggers: score 580–649 (thin or rebuilding credit), insufficient credit history (fewer than 12 months), or a settled default older than 24 months.
- Credit pulls are authorized once per application; re-pulls require applicant consent and are logged.

## 3. Affordability Check Policy

- Debt-to-income (DTI) ceiling for automated approval: **40%** of verified monthly income.
- Income must come from at least one of: payslips (last 3 months), tax returns (last 2 years), or audited business accounts.
- **Pass** – DTI at or under 40% with verified income.
- **Fail (hard)** – DTI above **44%** (10% over limit), or income cannot be verified at all.
- **Refer** – DTI between 40% and 44%, variable or seasonal income, or income documents partially missing.
- Loan purpose must be lawful and non-speculative; gambling and crypto trading are ineligible purposes (hard fail).

## 4. Fraud Check Policy

- Automated screening compares application data against internal blacklists, device fingerprints, and behavioral signals.
- **Fail (hard)** – confirmed blacklist match, synthetic identity indicators, or documented collusion with prior fraudulent applications.
- **Refer** – single soft signal (new device, address used on multiple recent applications, mismatched phone carrier records). Two or more soft signals escalate to a hard fail review.
- Suspected fraud referrals must not contact the applicant about the suspicion; only the underwriter may do so.

## General Provisions

- All thresholds in this policy are reviewed quarterly; changes require sign-off from the risk owner.
- Applicants may appeal any decision within 30 days; appeals are handled by a different underwriter than the original refer.
- Data gathered during checks is stored per the retention policy and never shared outside loan-ops.
