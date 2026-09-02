"""add automatic triage job state

Revision ID: 0008_auto_triage_jobs
Revises: 0007_gmail_sync_locks
Create Date: 2026-07-08 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0008_auto_triage_jobs"
down_revision: str | None = "0007_gmail_sync_locks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("tickets", sa.Column("triage_status", sa.String(length=30), nullable=False, server_default="not_queued"))
    op.add_column("tickets", sa.Column("active_triage_job_id", sa.String(length=36), nullable=True))
    op.add_column("tickets", sa.Column("triage_error_message", sa.Text(), nullable=True))
    op.add_column("tickets", sa.Column("triage_attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("tickets", sa.Column("last_triage_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tickets", sa.Column("last_triage_completed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_tickets_triage_status", "tickets", ["triage_status"])
    op.create_index("ix_tickets_active_triage_job_id", "tickets", ["active_triage_job_id"])

    op.add_column("ai_triage_results", sa.Column("prompt_version", sa.String(length=80), nullable=False, server_default="triage-v1"))
    op.add_column("ai_triage_results", sa.Column("schema_version", sa.String(length=80), nullable=False, server_default="triage-output-v1"))
    op.add_column("ai_triage_results", sa.Column("latency_ms", sa.Integer(), nullable=True))
    op.add_column("ai_triage_results", sa.Column("job_run_id", sa.String(length=36), nullable=True))
    op.create_index("ix_ai_triage_results_job_run_id", "ai_triage_results", ["job_run_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_triage_results_job_run_id", table_name="ai_triage_results")
    op.drop_column("ai_triage_results", "job_run_id")
    op.drop_column("ai_triage_results", "latency_ms")
    op.drop_column("ai_triage_results", "schema_version")
    op.drop_column("ai_triage_results", "prompt_version")

    op.drop_index("ix_tickets_active_triage_job_id", table_name="tickets")
    op.drop_index("ix_tickets_triage_status", table_name="tickets")
    op.drop_column("tickets", "last_triage_completed_at")
    op.drop_column("tickets", "last_triage_started_at")
    op.drop_column("tickets", "triage_attempts")
    op.drop_column("tickets", "triage_error_message")
    op.drop_column("tickets", "active_triage_job_id")
    op.drop_column("tickets", "triage_status")