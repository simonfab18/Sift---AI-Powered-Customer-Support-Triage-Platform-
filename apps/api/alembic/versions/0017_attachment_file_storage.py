"""add attachment file storage metadata

Revision ID: 0017_attachment_file_storage
Revises: 0016_ticket_attachment_metadata
Create Date: 2026-07-11 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0017_attachment_file_storage"
down_revision: str | None = "0016_ticket_attachment_metadata"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("ticket_attachments", sa.Column("storage_object_name", sa.String(length=1024), nullable=True))
    op.add_column("ticket_attachments", sa.Column("stored_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_ticket_attachments_storage_status", "ticket_attachments", ["storage_status"])


def downgrade() -> None:
    op.drop_index("ix_ticket_attachments_storage_status", table_name="ticket_attachments")
    op.drop_column("ticket_attachments", "stored_at")
    op.drop_column("ticket_attachments", "storage_object_name")