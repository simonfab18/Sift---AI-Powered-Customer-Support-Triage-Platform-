"""add pilot release controls

Revision ID: 0012_pilot_release_controls
Revises: 0011_security_tenant_hardening
Create Date: 2026-07-09 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0012_pilot_release_controls"
down_revision: str | None = "0011_security_tenant_hardening"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("workspace_settings", sa.Column("sync_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("workspace_settings", sa.Column("draft_creation_enabled", sa.Boolean(), nullable=False, server_default=sa.true()))
    op.add_column("workspace_settings", sa.Column("pilot_feedback_contact", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("workspace_settings", "pilot_feedback_contact")
    op.drop_column("workspace_settings", "draft_creation_enabled")
    op.drop_column("workspace_settings", "sync_enabled")
