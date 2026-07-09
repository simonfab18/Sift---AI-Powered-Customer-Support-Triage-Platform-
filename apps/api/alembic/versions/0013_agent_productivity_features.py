"""add agent productivity features

Revision ID: 0013_agent_productivity_features
Revises: 0012_pilot_release_controls
Create Date: 2026-07-09 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0013_agent_productivity_features"
down_revision: str | None = "0012_pilot_release_controls"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ticket_saved_views",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.String(length=120), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("filters", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.UniqueConstraint("organization_id", "user_id", "name", name="uq_saved_view_org_user_name"),
    )
    op.create_index("ix_ticket_saved_views_org_user", "ticket_saved_views", ["organization_id", "user_id"])

    op.create_table(
        "response_templates",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("category_tags", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=120), nullable=False),
        sa.Column("updated_by_user_id", sa.String(length=120), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
    )
    op.create_index("ix_response_templates_organization_id", "response_templates", ["organization_id"])

    op.create_table(
        "ticket_internal_notes",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=120), nullable=False),
        sa.Column("updated_by_user_id", sa.String(length=120), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
    )
    op.create_index("ix_ticket_internal_notes_ticket_id", "ticket_internal_notes", ["ticket_id"])

    op.create_table(
        "ticket_internal_note_edits",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("note_id", sa.String(length=36), nullable=False),
        sa.Column("edited_by_user_id", sa.String(length=120), nullable=False),
        sa.Column("previous_body", sa.Text(), nullable=False),
        sa.Column("new_body", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["note_id"], ["ticket_internal_notes.id"]),
    )

    op.create_table(
        "ticket_internal_note_mentions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("note_id", sa.String(length=36), nullable=False),
        sa.Column("mentioned_user_id", sa.String(length=120), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["note_id"], ["ticket_internal_notes.id"]),
        sa.UniqueConstraint("note_id", "mentioned_user_id", name="uq_note_mention_user"),
    )

    op.create_table(
        "ticket_collaboration_locks",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("resource_type", sa.String(length=40), nullable=False),
        sa.Column("resource_id", sa.String(length=36), nullable=False),
        sa.Column("locked_by_user_id", sa.String(length=120), nullable=False),
        sa.Column("mode", sa.String(length=20), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.UniqueConstraint("organization_id", "resource_type", "resource_id", name="uq_collaboration_lock_resource"),
    )
    op.create_index("ix_ticket_collaboration_locks_ticket_id", "ticket_collaboration_locks", ["ticket_id"])


def downgrade() -> None:
    op.drop_index("ix_ticket_collaboration_locks_ticket_id", table_name="ticket_collaboration_locks")
    op.drop_table("ticket_collaboration_locks")
    op.drop_table("ticket_internal_note_mentions")
    op.drop_table("ticket_internal_note_edits")
    op.drop_index("ix_ticket_internal_notes_ticket_id", table_name="ticket_internal_notes")
    op.drop_table("ticket_internal_notes")
    op.drop_index("ix_response_templates_organization_id", table_name="response_templates")
    op.drop_table("response_templates")
    op.drop_index("ix_ticket_saved_views_org_user", table_name="ticket_saved_views")
    op.drop_table("ticket_saved_views")
