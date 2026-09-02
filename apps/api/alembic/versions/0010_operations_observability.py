"""add operations observability fields

Revision ID: 0010_operations_observability
Revises: 0009_core_workflow_polish
Create Date: 2026-07-08 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0010_operations_observability"
down_revision: str | None = "0009_core_workflow_polish"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("job_runs", sa.Column("queue_name", sa.String(length=80), nullable=False, server_default="default"))
    op.add_column("job_runs", sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("job_runs", sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"))
    op.add_column("job_runs", sa.Column("correlation_id", sa.String(length=80), nullable=True))
    op.add_column("job_runs", sa.Column("related_resource_type", sa.String(length=80), nullable=True))
    op.add_column("job_runs", sa.Column("related_resource_id", sa.String(length=120), nullable=True))
    op.add_column("job_runs", sa.Column("error_class", sa.String(length=120), nullable=True))
    op.add_column("job_runs", sa.Column("error_code", sa.String(length=80), nullable=True))
    op.add_column("job_runs", sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("job_runs", sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("job_runs", sa.Column("duration_ms", sa.Integer(), nullable=True))
    op.add_column("job_runs", sa.Column("alert_owner", sa.String(length=120), nullable=True))
    op.add_column("job_runs", sa.Column("runbook_url", sa.String(length=500), nullable=True))
    op.create_index("ix_job_runs_queue_name", "job_runs", ["queue_name"])
    op.create_index("ix_job_runs_correlation_id", "job_runs", ["correlation_id"])
    op.create_index("ix_job_runs_related_resource_type", "job_runs", ["related_resource_type"])
    op.create_index("ix_job_runs_related_resource_id", "job_runs", ["related_resource_id"])
    op.create_index("ix_job_runs_error_class", "job_runs", ["error_class"])
    op.create_index("ix_job_runs_error_code", "job_runs", ["error_code"])
    op.create_index("ix_job_runs_retryable", "job_runs", ["retryable"])


def downgrade() -> None:
    op.drop_index("ix_job_runs_retryable", table_name="job_runs")
    op.drop_index("ix_job_runs_error_code", table_name="job_runs")
    op.drop_index("ix_job_runs_error_class", table_name="job_runs")
    op.drop_index("ix_job_runs_related_resource_id", table_name="job_runs")
    op.drop_index("ix_job_runs_related_resource_type", table_name="job_runs")
    op.drop_index("ix_job_runs_correlation_id", table_name="job_runs")
    op.drop_index("ix_job_runs_queue_name", table_name="job_runs")
    op.drop_column("job_runs", "runbook_url")
    op.drop_column("job_runs", "alert_owner")
    op.drop_column("job_runs", "duration_ms")
    op.drop_column("job_runs", "next_retry_at")
    op.drop_column("job_runs", "retryable")
    op.drop_column("job_runs", "error_code")
    op.drop_column("job_runs", "error_class")
    op.drop_column("job_runs", "related_resource_id")
    op.drop_column("job_runs", "related_resource_type")
    op.drop_column("job_runs", "correlation_id")
    op.drop_column("job_runs", "max_attempts")
    op.drop_column("job_runs", "attempts")
    op.drop_column("job_runs", "queue_name")
