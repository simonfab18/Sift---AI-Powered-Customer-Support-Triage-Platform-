"""add attachment ai processing opt in

Revision ID: 0021_attachment_ai_optin
Revises: 0020_gmail_shared_inbox_metadata
Create Date: 2026-07-14 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0021_attachment_ai_optin"
down_revision: str | None = "0020_gmail_shared_inbox_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "workspace_settings",
        sa.Column("attachment_ai_processing_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("workspace_settings", "attachment_ai_processing_enabled")