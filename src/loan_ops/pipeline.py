"""Pipeline orchestrator: intake -> checks (agent-executed) -> decision ->
persistence. Implements docs/PROC.md steps 2-8 per application."""

from __future__ import annotations

import os
from typing import Any

from loan_ops.agents.decision import run_decision
from loan_ops.checks import CHECKS
from loan_ops.models import Decision, LoanApplication
from loan_ops.policy import OUTCOME_REFER
from loan_ops.records import (
    create_application,
    get_application,
    get_audit,
    save_check_results,
    save_decision,
)
from loan_ops.store import session_scope


def _provider_unavailable_decision(
    app: LoanApplication, application_id: int, exc: Exception
) -> Decision:
    """Execute checks ourselves and escalate to refer — never guess (GOALS 5.1)."""
    if os.environ.get("LOAN_OPS_DEBUG"):
        import traceback

        traceback.print_exception(exc)
    results = [check(app) for check in CHECKS]
    return Decision(
        application_id=str(application_id),
        outcome=OUTCOME_REFER,
        rule=f"LLM provider unavailable ({type(exc).__name__}), escalated to refer.",
        check_results=results,
        model="",
        provider="none",
    )


def process(payload: dict[str, Any]) -> dict[str, Any]:
    """Full run-through for one application.

    Steps (docs/PROC.md): intake validation (2), checks executed via agent
    tools (3), decision from process rules (4-5), persistence + audit (6),
    verify audit entry (8).
    """
    application_id = create_application(payload)
    stored = get_application(application_id)
    if stored is None:  # pragma: no cover - defensive
        raise RuntimeError(f"application {application_id} vanished after insert")
    app = LoanApplication(
        **{**stored["payload"], "application_id": str(application_id)}
    )

    try:
        decision = run_decision(app)
    except Exception as exc:  # provider unreachable / misconfigured
        decision = _provider_unavailable_decision(app, application_id, exc)

    with session_scope() as session:
        save_check_results(session, application_id, decision.check_results)
        save_decision(
            session,
            application_id,
            outcome=decision.outcome,
            rule=decision.rule,
            model=decision.model,
            provider=decision.provider,
            decided_by="agent",
        )

    # Step 8 (docs/PROC.md): verify the audit entry exists and is complete.
    audit = get_audit(application_id)
    events = {entry["event"] for entry in audit}
    if not {"application_received", "checks_executed", "decision_recorded"} <= events:
        raise RuntimeError(f"audit trail incomplete for application {application_id}")

    return {
        "application_id": application_id,
        "outcome": decision.outcome,
        "rule": decision.rule,
        "model": decision.model,
        "provider": decision.provider,
        "check_results": [r.model_dump() for r in decision.check_results],
        "audit_events": len(audit),
    }
