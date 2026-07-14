"""widen gmail attachment id

Revision ID: 0018_widen_gmail_attachment_id
Revises: 0017_attachment_file_storage
Create Date: 2026-07-12 18:45:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018_widen_gmail_attachment_id"
down_revision: str | None = "0017_attachment_file_storage"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "ticket_attachments",
        "gmail_attachment_id",
        existing_type=sa.String(length=240),
        type_=sa.Text(),
        existing_nullable=True,
    )


def downgrade() -> None:
    op.alter_column(
        "ticket_attachments",
        "gmail_attachment_id",
        existing_type=sa.Text(),
        type_=sa.String(length=240),
        existing_nullable=True,
    )
