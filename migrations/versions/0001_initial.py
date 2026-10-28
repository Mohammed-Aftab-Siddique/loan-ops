"""Initial schema: applications, check_results, decisions, audit_log.

Revision ID: 0001_initial
Revises:
Create Date: 2026-10-28
"""

import sqlalchemy as sa
from alembic import op

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "applications",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("applicant_name", sa.String(), nullable=False),
        sa.Column("applicant_id_number", sa.String(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(), nullable=False, server_default="intake"),
        sa.Column("outcome", sa.String(), nullable=True),
        sa.Column("loan_amount", sa.Float(), nullable=False),
        sa.Column("monthly_income", sa.Float(), nullable=False),
        sa.Column("existing_monthly_debt", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "check_results",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "application_id", sa.Integer(),
            sa.ForeignKey("applications.id"), nullable=False,
        ),
        sa.Column("check", sa.String(), nullable=False),
        sa.Column("result_class", sa.String(), nullable=False),
        sa.Column("reason", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "decisions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "application_id", sa.Integer(),
            sa.ForeignKey("applications.id"), nullable=False,
        ),
        sa.Column("outcome", sa.String(), nullable=False),
        sa.Column("rule", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False, server_default=""),
        sa.Column("provider", sa.String(), nullable=False, server_default=""),
        sa.Column("decided_by", sa.String(), nullable=False, server_default="agent"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "application_id", sa.Integer(),
            sa.ForeignKey("applications.id"), nullable=False,
        ),
        sa.Column("event", sa.String(), nullable=False),
        sa.Column("detail", sa.JSON(), nullable=False),
        sa.Column("actor", sa.String(), nullable=False, server_default="agent"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("decisions")
    op.drop_table("check_results")
    op.drop_table("applications")
