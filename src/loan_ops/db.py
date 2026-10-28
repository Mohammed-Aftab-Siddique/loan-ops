"""SQLAlchemy ORM models.

Tables (docs/PLAN.md Phase 1): applications, check_results, decisions, audit_log.
Audit entries are append-only; decisions/checks reference applications.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class ApplicationRow(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    applicant_name: Mapped[str] = mapped_column(String, nullable=False)
    applicant_id_number: Mapped[str] = mapped_column(String, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    # state: "intake" until processed; referrals remain "referred" until an
    # underwriter resolves them ("resolved")
    state: Mapped[str] = mapped_column(String, nullable=False, default="intake")
    outcome: Mapped[str | None] = mapped_column(String, nullable=True)
    loan_amount: Mapped[float] = mapped_column(Float, nullable=False)
    monthly_income: Mapped[float] = mapped_column(Float, nullable=False)
    existing_monthly_debt: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    check_results: Mapped[list["CheckResultRow"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    decisions: Mapped[list["DecisionRow"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )
    audit: Mapped[list["AuditRow"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )


class CheckResultRow(Base):
    __tablename__ = "check_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), nullable=False)
    check: Mapped[str] = mapped_column(String, nullable=False)
    result_class: Mapped[str] = mapped_column(String, nullable=False)
    reason: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    application: Mapped[ApplicationRow] = relationship(back_populates="check_results")


class DecisionRow(Base):
    __tablename__ = "decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), nullable=False)
    outcome: Mapped[str] = mapped_column(String, nullable=False)
    rule: Mapped[str] = mapped_column(String, nullable=False)
    model: Mapped[str] = mapped_column(String, nullable=False, default="")
    provider: Mapped[str] = mapped_column(String, nullable=False, default="")
    decided_by: Mapped[str] = mapped_column(String, nullable=False, default="agent")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    application: Mapped[ApplicationRow] = relationship(back_populates="decisions")


class AuditRow(Base):
    """Append-only audit log (docs/PROCESS.md §Audit)."""

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    application_id: Mapped[int] = mapped_column(ForeignKey("applications.id"), nullable=False)
    event: Mapped[str] = mapped_column(String, nullable=False)
    detail: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    actor: Mapped[str] = mapped_column(String, nullable=False, default="agent")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    application: Mapped[ApplicationRow] = relationship(back_populates="audit")
