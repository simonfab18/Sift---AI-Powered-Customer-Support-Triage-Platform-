"""add reply suggestion version history

Revision ID: 0022_reply_suggestion_versions
Revises: 0021_attachment_ai_optin
Create Date: 2026-07-16 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0022_reply_suggestion_versions"
down_revision: str | None = "0021_attachment_ai_optin"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "reply_suggestion_versions",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("reply_suggestion_id", sa.String(length=36), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["reply_suggestion_id"], ["reply_suggestions.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reply_suggestion_id", "version", name="uq_reply_suggestion_versions_suggestion_version"),
    )
    for column in ["created_at", "created_by_user_id", "organization_id", "reply_suggestion_id", "ticket_id"]:
        op.create_index(f"ix_reply_suggestion_versions_{column}", "reply_suggestion_versions", [column])


def downgrade() -> None:
    for column in ["created_at", "created_by_user_id", "organization_id", "reply_suggestion_id", "ticket_id"]:
        op.drop_index(f"ix_reply_suggestion_versions_{column}", table_name="reply_suggestion_versions")
    op.drop_table("reply_suggestion_versions")