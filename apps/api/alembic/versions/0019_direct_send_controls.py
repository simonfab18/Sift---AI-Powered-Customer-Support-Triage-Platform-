"""add direct send controls

Revision ID: 0019_direct_send_controls
Revises: 0018_widen_gmail_attachment_id
Create Date: 2026-07-14 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0019_direct_send_controls"
down_revision: str | None = "0018_widen_gmail_attachment_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("workspace_settings", sa.Column("direct_send_enabled", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "gmail_sent_messages",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("reply_suggestion_id", sa.String(length=36), nullable=False),
        sa.Column("gmail_message_id", sa.String(length=160), nullable=False),
        sa.Column("gmail_thread_id", sa.String(length=160), nullable=True),
        sa.Column("reply_version", sa.Integer(), nullable=False),
        sa.Column("sent_by_user_id", sa.String(length=120), nullable=False),
        sa.Column("test_mode", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("organization_id", "reply_suggestion_id", name="uq_gmail_sent_org_suggestion"),
    )
    op.create_index("ix_gmail_sent_messages_created_at", "gmail_sent_messages", ["created_at"])
    op.create_index("ix_gmail_sent_messages_gmail_message_id", "gmail_sent_messages", ["gmail_message_id"])
    op.create_index("ix_gmail_sent_messages_gmail_thread_id", "gmail_sent_messages", ["gmail_thread_id"])
    op.create_index("ix_gmail_sent_messages_organization_id", "gmail_sent_messages", ["organization_id"])
    op.create_index("ix_gmail_sent_messages_reply_suggestion_id", "gmail_sent_messages", ["reply_suggestion_id"])
    op.create_index("ix_gmail_sent_messages_sent_at", "gmail_sent_messages", ["sent_at"])
    op.create_index("ix_gmail_sent_messages_sent_by_user_id", "gmail_sent_messages", ["sent_by_user_id"])
    op.create_index("ix_gmail_sent_messages_ticket_id", "gmail_sent_messages", ["ticket_id"])


def downgrade() -> None:
    op.drop_index("ix_gmail_sent_messages_ticket_id", table_name="gmail_sent_messages")
    op.drop_index("ix_gmail_sent_messages_sent_by_user_id", table_name="gmail_sent_messages")
    op.drop_index("ix_gmail_sent_messages_sent_at", table_name="gmail_sent_messages")
    op.drop_index("ix_gmail_sent_messages_reply_suggestion_id", table_name="gmail_sent_messages")
    op.drop_index("ix_gmail_sent_messages_organization_id", table_name="gmail_sent_messages")
    op.drop_index("ix_gmail_sent_messages_gmail_thread_id", table_name="gmail_sent_messages")
    op.drop_index("ix_gmail_sent_messages_gmail_message_id", table_name="gmail_sent_messages")
    op.drop_index("ix_gmail_sent_messages_created_at", table_name="gmail_sent_messages")
    op.drop_table("gmail_sent_messages")
    op.drop_column("workspace_settings", "direct_send_enabled")
