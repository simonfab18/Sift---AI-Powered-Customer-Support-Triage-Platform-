"""add multiple gmail inbox metadata

Revision ID: 0015_multiple_gmail_inboxes
Revises: 0014_knowledge_routing_sla
Create Date: 2026-07-11 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0015_multiple_gmail_inboxes"
down_revision: str | None = "0014_knowledge_routing_sla"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("gmail_connections", sa.Column("display_name", sa.String(length=120), nullable=True))
    op.add_column(
        "mail_import_rules",
        sa.Column("routing_direction", sa.String(length=40), nullable=False, server_default="shared_queue"),
    )
    op.create_index("ix_mail_import_rules_routing_direction", "mail_import_rules", ["routing_direction"])


def downgrade() -> None:
    op.drop_index("ix_mail_import_rules_routing_direction", table_name="mail_import_rules")
    op.drop_column("mail_import_rules", "routing_direction")
    op.drop_column("gmail_connections", "display_name")
