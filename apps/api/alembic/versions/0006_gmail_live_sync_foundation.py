"""gmail live sync foundation

Revision ID: 0006_gmail_live_sync
Revises: 0005_ai_conf_workspace
Create Date: 2026-07-08 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0006_gmail_live_sync"
down_revision: str | None = "0005_ai_conf_workspace"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("gmail_connections", sa.Column("gmail_history_id", sa.String(length=80), nullable=True))
    op.add_column("gmail_connections", sa.Column("watch_expires_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("gmail_connections", sa.Column("last_notification_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("gmail_connections", sa.Column("last_sync_started_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("gmail_connections", sa.Column("last_successful_sync_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("gmail_connections", sa.Column("sync_status", sa.String(length=40), nullable=False, server_default="disconnected"))
    op.add_column("gmail_connections", sa.Column("sync_error_code", sa.String(length=80), nullable=True))
    op.add_column("gmail_connections", sa.Column("sync_error_message", sa.Text(), nullable=True))
    op.add_column("gmail_connections", sa.Column("consecutive_sync_failures", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("gmail_connections", sa.Column("watch_status", sa.String(length=40), nullable=False, server_default="disconnected"))
    op.add_column("gmail_connections", sa.Column("watch_error", sa.Text(), nullable=True))
    op.add_column("gmail_connections", sa.Column("disconnected_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_gmail_connections_watch_status", "gmail_connections", ["watch_status"])
    op.create_index("ix_gmail_connections_sync_status", "gmail_connections", ["sync_status"])

    op.create_table(
        "gmail_sync_events",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("gmail_connection_id", sa.String(length=36), nullable=True),
        sa.Column("trigger_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("pubsub_message_id", sa.String(length=160), nullable=True),
        sa.Column("notification_history_id", sa.String(length=80), nullable=True),
        sa.Column("start_history_id", sa.String(length=80), nullable=True),
        sa.Column("end_history_id", sa.String(length=80), nullable=True),
        sa.Column("messages_seen", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("messages_imported", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("messages_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tickets_created", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("tickets_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duration_ms", sa.Integer(), nullable=True),
        sa.Column("error_code", sa.String(length=80), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("metadata", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["gmail_connection_id"], ["gmail_connections.id"]),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_gmail_sync_events_organization_id", "gmail_sync_events", ["organization_id"])
    op.create_index("ix_gmail_sync_events_gmail_connection_id", "gmail_sync_events", ["gmail_connection_id"])
    op.create_index("ix_gmail_sync_events_created_at", "gmail_sync_events", ["created_at"])
    op.create_index("ix_gmail_sync_events_status", "gmail_sync_events", ["status"])
    op.create_index("ix_gmail_sync_events_trigger_type", "gmail_sync_events", ["trigger_type"])
    op.create_index("ix_gmail_sync_events_pubsub_message_id", "gmail_sync_events", ["pubsub_message_id"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_gmail_sync_events_pubsub_message_id", table_name="gmail_sync_events")
    op.drop_index("ix_gmail_sync_events_trigger_type", table_name="gmail_sync_events")
    op.drop_index("ix_gmail_sync_events_status", table_name="gmail_sync_events")
    op.drop_index("ix_gmail_sync_events_created_at", table_name="gmail_sync_events")
    op.drop_index("ix_gmail_sync_events_gmail_connection_id", table_name="gmail_sync_events")
    op.drop_index("ix_gmail_sync_events_organization_id", table_name="gmail_sync_events")
    op.drop_table("gmail_sync_events")

    op.drop_index("ix_gmail_connections_sync_status", table_name="gmail_connections")
    op.drop_index("ix_gmail_connections_watch_status", table_name="gmail_connections")
    op.drop_column("gmail_connections", "disconnected_at")
    op.drop_column("gmail_connections", "watch_error")
    op.drop_column("gmail_connections", "watch_status")
    op.drop_column("gmail_connections", "consecutive_sync_failures")
    op.drop_column("gmail_connections", "sync_error_message")
    op.drop_column("gmail_connections", "sync_error_code")
    op.drop_column("gmail_connections", "sync_status")
    op.drop_column("gmail_connections", "last_successful_sync_at")
    op.drop_column("gmail_connections", "last_sync_started_at")
    op.drop_column("gmail_connections", "last_notification_at")
    op.drop_column("gmail_connections", "watch_expires_at")
    op.drop_column("gmail_connections", "gmail_history_id")
