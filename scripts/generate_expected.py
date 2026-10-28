"""Generate data/expected_decisions.json from data/loan_applications.json.

Runs every intake through the REAL code path (LoanApplication validation ->
the four checks in `loan_ops.checks` -> `deterministic_outcome`), so the
expected outputs come from executed tools, never from estimates
(docs/PROC.md rules of conduct). Deterministic and LLM-free: the outcome
contract derives from executed check results alone.

Usage: uv run python scripts/generate_expected.py
"""

from __future__ import annotations

import json
from pathlib import Path

from loan_ops.agents.decision import deterministic_outcome
from loan_ops.checks import CHECKS
from loan_ops.models import LoanApplication
from loan_ops.policy import VALID_OUTCOMES

DATA = Path(__file__).resolve().parent.parent / "data"
INPUT = DATA / "loan_applications.json"
OUTPUT = DATA / "expected_decisions.json"

INTAKE_REJECTED = "rejected_at_intake"  # not a decision outcome (docs/PROC.md step 2)


def evaluate(record: dict) -> dict:
    """Run one record through validation + the four checks + decision rules."""
    try:
        app = LoanApplication(**{"application_id": None, **record})
    except Exception as exc:
        return {
            "application_id": record.get("application_id", "<unknown>"),
            "applicant_name": record.get("applicant_name"),
            "loan_amount": record.get("loan_amount"),
            "status": INTAKE_REJECTED,
            "reason": f"Intake validation failed: {exc}",
            "checks": [],
        }

    results = [check(app) for check in CHECKS]  # identity, credit, affordability, fraud
    results_by_name = {r.check: r for r in results}
    outcome, rule = deterministic_outcome(results_by_name, app.loan_amount)
    assert outcome in VALID_OUTCOMES, outcome

    return {
        "application_id": record["application_id"],
        "applicant_name": record["applicant_name"],
        "loan_amount": record["loan_amount"],
        "status": outcome,
        "reason": rule,
        "checks": [r.model_dump() for r in results],
    }


def main() -> None:
    payload = json.loads(INPUT.read_text())
    decisions = [evaluate(record) for record in payload["applications"]]

    OUTPUT.write_text(
        json.dumps(
            {
                "notes": {
                    "description": (
                        "Expected loan approval status for every record in "
                        "loan_applications.json, produced by running the real "
                        "loan-ops code path (intake validation -> four checks -> "
                        "deterministic decision rules). Not hand-written."
                    ),
                    "status_values": [
                        *sorted(VALID_OUTCOMES),
                        INTAKE_REJECTED,
                    ],
                    "status_meaning": (
                        f"'{INTAKE_REJECTED}' is not one of the three decision "
                        "outcomes; it means the record failed intake validation and "
                        "was returned to the applicant without entering review "
                        "(docs/PROCESS.md, docs/PROC.md step 2)."
                    ),
                    "reason": (
                        "The rule(s) from docs/PROCESS.md that produced the status, "
                        "including the executed check result(s) that justify it."
                    ),
                    "ui_visibility": (
                        "Not displayed in the UI. The web UI keeps every "
                        "application in a waiting state until the agent runs; "
                        "this file exists for offline verification and tests."
                    ),
                },
                "decisions": decisions,
            },
            indent=2,
        )
        + "\n"
    )
    counts: dict[str, int] = {}
    for d in decisions:
        counts[d["status"]] = counts.get(d["status"], 0) + 1
    print(f"wrote {OUTPUT} — {len(decisions)} records, {counts}")


if __name__ == "__main__":
    main()
