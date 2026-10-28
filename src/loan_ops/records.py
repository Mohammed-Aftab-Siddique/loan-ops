"""Persistence service: applications, check results, decisions, audit log.

Audit entries are append-only and every decision must carry the tool results
that justified it (docs/PROCESS.md §Audit, GOALS 3.5).

No modifications or deletions are exposed on any code path for audit entries.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from loan_ops.db import ApplicationRow, AuditRow, CheckResultRow, DecisionRow
from loan_ops.models import CheckResult, LoanApplication
from loan_ops.store import session_scope


def create_application(payload: dict[str, Any]) -> int:
    """Validate payload through LoanApplication and persist an intake row."""
    app = LoanApplication(**payload)
    with session_scope() as session:
        row = ApplicationRow(
            applicant_name=app.applicant_name,
            applicant_id_number=app.applicant_id_number,
            payload=app.model_dump(),
            loan_amount=app.loan_amount,
            monthly_income=app.monthly_income,
            existing_monthly_debt=app.existing_monthly_debt,
        )
        session.add(row)
        session.flush()
        log_audit(
            session,
            row.id,
            "application_received",
            {"risk_tier": "pending"},
            actor="system",
        )
        return row.id


def save_check_results(session: Session, application_id: int, results: list[CheckResult]) -> None:
    for result in results:
        session.add(CheckResultRow(application_id=application_id, **result.model_dump()))
    log_audit(
        session,
        application_id,
        "checks_executed",
        {"results": [r.model_dump() for r in results]},
        actor="checks",
    )


def save_decision(
    session: Session,
    application_id: int,
    outcome: str,
    rule: str,
    model: str = "",
    provider: str = "",
    decided_by: str = "agent",
) -> None:
    session.add(
        DecisionRow(
            application_id=application_id,
            outcome=outcome,
            rule=rule,
            model=model,
            provider=provider,
            decided_by=decided_by,
        )
    )
    row = session.get(ApplicationRow, application_id)
    if row is None:
        raise ValueError(f"application {application_id} not found")
    row.outcome = outcome
    if decided_by == "agent":
        row.state = "resolved" if outcome != "refer" else "referred"
    log_audit(
        session,
        application_id,
        "decision_recorded",
        {"outcome": outcome, "rule": rule, "decided_by": decided_by,
         "provider": provider, "model": model},
        actor=decided_by,
    )


def resolve_referral(
    application_id: int, decision: str, underwriter_id: str
) -> None:
    """Human underwriter decision on a referred case (docs/PROCESS.md Outcomes)."""
    if decision not in ("approved", "denied"):
        raise ValueError("underwriter decision must be 'approved' or 'denied'")
    with session_scope() as session:
        row = session.get(ApplicationRow, application_id)
        if row is None:
            raise ValueError(f"application {application_id} not found")
        if row.outcome != "refer":
            raise ValueError(f"application {application_id} is not a referral")
        save_decision(
            session,
            application_id,
            outcome=decision,
            rule=f"Human underwriter decision by {underwriter_id}",
            decided_by=underwriter_id,
        )
        row.state = "resolved"


def log_audit(
    session: Session, application_id: int, event: str, detail: dict[str, Any], actor: str
) -> None:
    session.add(
        AuditRow(application_id=application_id, event=event, detail=detail, actor=actor)
    )


def get_application(application_id: int) -> dict[str, Any] | None:
    with session_scope() as session:
        row = session.get(ApplicationRow, application_id)
        if row is None:
            return None
        return _serialize(row)


def list_applications() -> list[dict[str, Any]]:
    with session_scope() as session:
        rows = session.scalars(select(ApplicationRow).order_by(ApplicationRow.id.desc())).all()
        return [_serialize(row) for row in rows]


def referral_queue() -> list[dict[str, Any]]:
    with session_scope() as session:
        rows = session.scalars(
            select(ApplicationRow)
            .where(ApplicationRow.outcome == "refer", ApplicationRow.state == "referred")
            .order_by(ApplicationRow.id)
        ).all()
        return [_serialize(row) for row in rows]


def get_audit(application_id: int) -> list[dict[str, Any]]:
    with session_scope() as session:
        rows = session.scalars(
            select(AuditRow)
            .where(AuditRow.application_id == application_id)
            .order_by(AuditRow.id)
        ).all()
        return [
            {
                "id": row.id,
                "event": row.event,
                "detail": row.detail,
                "actor": row.actor,
                "created_at": row.created_at.isoformat(),
            }
            for row in rows
        ]


def _serialize(row: ApplicationRow) -> dict[str, Any]:
    return {
        "id": row.id,
        "applicant_name": row.applicant_name,
        "applicant_id_number": row.applicant_id_number,
        "state": row.state,
        "outcome": row.outcome,
        "loan_amount": row.loan_amount,
        "monthly_income": row.monthly_income,
        "existing_monthly_debt": row.existing_monthly_debt,
        "payload": row.payload,
        "created_at": row.created_at.isoformat(),
        "check_results": [
            {
                "check": cr.check,
                "result_class": cr.result_class,
                "reason": cr.reason,
            }
            for cr in row.check_results
        ],
    }
