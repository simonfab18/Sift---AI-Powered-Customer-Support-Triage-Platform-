"""add gmail shared inbox metadata

Revision ID: 0020_gmail_shared_inbox_metadata
Revises: 0019_direct_send_controls
Create Date: 2026-07-14 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0020_gmail_shared_inbox_metadata"
down_revision: str | None = "0019_direct_send_controls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "gmail_connections",
        sa.Column("inbox_type", sa.String(length=40), nullable=False, server_default="individual"),
    )
    op.add_column("gmail_connections", sa.Column("shared_address", sa.String(length=320), nullable=True))
    op.add_column("gmail_connections", sa.Column("channel_notes", sa.Text(), nullable=True))
    op.create_index("ix_gmail_connections_inbox_type", "gmail_connections", ["inbox_type"])


def downgrade() -> None:
    op.drop_index("ix_gmail_connections_inbox_type", table_name="gmail_connections")
    op.drop_column("gmail_connections", "channel_notes")
    op.drop_column("gmail_connections", "shared_address")
    op.drop_column("gmail_connections", "inbox_type")