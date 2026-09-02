"""add gmail sync lock fields

Revision ID: 0007_gmail_sync_locks
Revises: 0006_gmail_live_sync
Create Date: 2026-07-08 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0007_gmail_sync_locks"
down_revision: str | None = "0006_gmail_live_sync"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("gmail_connections", sa.Column("sync_lock_id", sa.String(length=80), nullable=True))
    op.add_column("gmail_connections", sa.Column("sync_lock_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_gmail_connections_sync_lock_expires_at", "gmail_connections", ["sync_lock_expires_at"])


def downgrade() -> None:
    op.drop_index("ix_gmail_connections_sync_lock_expires_at", table_name="gmail_connections")
    op.drop_column("gmail_connections", "sync_lock_expires_at")
    op.drop_column("gmail_connections", "sync_lock_id")
