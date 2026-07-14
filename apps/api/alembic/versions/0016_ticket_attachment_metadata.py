"""add ticket attachment metadata

Revision ID: 0016_ticket_attachment_metadata
Revises: 0015_multiple_gmail_inboxes
Create Date: 2026-07-11 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0016_ticket_attachment_metadata"
down_revision: str | None = "0015_multiple_gmail_inboxes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ticket_attachments",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("gmail_connection_id", sa.String(length=36), nullable=True),
        sa.Column("gmail_message_id", sa.String(length=160), nullable=True),
        sa.Column("gmail_attachment_id", sa.String(length=240), nullable=True),
        sa.Column("filename", sa.String(length=500), nullable=True),
        sa.Column("mime_type", sa.String(length=160), nullable=True),
        sa.Column("size_bytes", sa.Integer(), nullable=True),
        sa.Column("content_disposition", sa.String(length=80), nullable=True),
        sa.Column("is_inline", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("policy_status", sa.String(length=40), nullable=False, server_default="metadata_only"),
        sa.Column("storage_status", sa.String(length=40), nullable=False, server_default="not_downloaded"),
        sa.Column("scan_status", sa.String(length=40), nullable=False, server_default="not_scanned"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["gmail_connection_id"], ["gmail_connections.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "ticket_id", "gmail_attachment_id", name="uq_ticket_attachment_gmail"),
    )
    op.create_index("ix_ticket_attachments_gmail_attachment_id", "ticket_attachments", ["gmail_attachment_id"])
    op.create_index("ix_ticket_attachments_gmail_connection_id", "ticket_attachments", ["gmail_connection_id"])
    op.create_index("ix_ticket_attachments_gmail_message_id", "ticket_attachments", ["gmail_message_id"])
    op.create_index("ix_ticket_attachments_mime_type", "ticket_attachments", ["mime_type"])
    op.create_index("ix_ticket_attachments_organization_id", "ticket_attachments", ["organization_id"])
    op.create_index("ix_ticket_attachments_ticket_id", "ticket_attachments", ["ticket_id"])


def downgrade() -> None:
    op.drop_index("ix_ticket_attachments_ticket_id", table_name="ticket_attachments")
    op.drop_index("ix_ticket_attachments_organization_id", table_name="ticket_attachments")
    op.drop_index("ix_ticket_attachments_mime_type", table_name="ticket_attachments")
    op.drop_index("ix_ticket_attachments_gmail_message_id", table_name="ticket_attachments")
    op.drop_index("ix_ticket_attachments_gmail_connection_id", table_name="ticket_attachments")
    op.drop_index("ix_ticket_attachments_gmail_attachment_id", table_name="ticket_attachments")
    op.drop_table("ticket_attachments")
