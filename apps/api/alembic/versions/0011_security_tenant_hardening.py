"""add security tenant hardening fields

Revision ID: 0011_security_tenant_hardening
Revises: 0010_operations_observability
Create Date: 2026-07-09 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0011_security_tenant_hardening"
down_revision: str | None = "0010_operations_observability"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("gmail_connections", sa.Column("token_key_version", sa.Integer(), nullable=False, server_default="1"))
    op.add_column("gmail_connections", sa.Column("reauthorization_required_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("gmail_connections", sa.Column("reauthorization_reason", sa.String(length=120), nullable=True))
    op.add_column("gmail_connections", sa.Column("last_token_error_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("gmail_connections", "last_token_error_at")
    op.drop_column("gmail_connections", "reauthorization_reason")
    op.drop_column("gmail_connections", "reauthorization_required_at")
    op.drop_column("gmail_connections", "token_key_version")
