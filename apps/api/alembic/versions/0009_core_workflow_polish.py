"""add core workflow polish fields

Revision ID: 0009_core_workflow_polish
Revises: 0008_auto_triage_jobs
Create Date: 2026-07-08 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0009_core_workflow_polish"
down_revision: str | None = "0008_auto_triage_jobs"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("reply_approvals", sa.Column("reply_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("reply_approvals", sa.Column("approved_reply_version", sa.Integer(), nullable=True))
    op.add_column("reply_suggestions", sa.Column("reply_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("reply_suggestions", sa.Column("approved_reply_version", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("reply_suggestions", "approved_reply_version")
    op.drop_column("reply_suggestions", "reply_version")
    op.drop_column("reply_approvals", "approved_reply_version")
    op.drop_column("reply_approvals", "reply_version")