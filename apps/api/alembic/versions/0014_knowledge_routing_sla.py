"""add knowledge routing and sla features

Revision ID: 0014_knowledge_routing_sla
Revises: 0013_agent_productivity_features
Create Date: 2026-07-10 00:00:00
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "0014_knowledge_routing_sla"
down_revision: str | None = "0013_agent_productivity_features"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("owner_user_id", sa.String(length=120), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("source_metadata", sa.JSON(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
    )
    op.create_index("ix_knowledge_sources_organization_id", "knowledge_sources", ["organization_id"])
    op.create_index("ix_knowledge_sources_status", "knowledge_sources", ["status"])
    op.create_index("ix_knowledge_sources_effective_from", "knowledge_sources", ["effective_from"])
    op.create_index("ix_knowledge_sources_effective_until", "knowledge_sources", ["effective_until"])

    op.create_table(
        "routing_rules",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("priority_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("conditions", sa.JSON(), nullable=False),
        sa.Column("actions", sa.JSON(), nullable=False),
        sa.Column("created_by_user_id", sa.String(length=120), nullable=False),
        sa.Column("updated_by_user_id", sa.String(length=120), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
    )
    op.create_index("ix_routing_rules_organization_id", "routing_rules", ["organization_id"])
    op.create_index("ix_routing_rules_priority_order", "routing_rules", ["priority_order"])
    op.create_index("ix_routing_rules_is_active", "routing_rules", ["is_active"])

    op.create_table(
        "routing_rule_executions",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("routing_rule_id", sa.String(length=36), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("matched", sa.Boolean(), nullable=False),
        sa.Column("actions_applied", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["routing_rule_id"], ["routing_rules.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
    )
    op.create_index("ix_routing_rule_executions_organization_id", "routing_rule_executions", ["organization_id"])
    op.create_index("ix_routing_rule_executions_routing_rule_id", "routing_rule_executions", ["routing_rule_id"])
    op.create_index("ix_routing_rule_executions_ticket_id", "routing_rule_executions", ["ticket_id"])
    op.create_index("ix_routing_rule_executions_created_at", "routing_rule_executions", ["created_at"])

    op.create_table(
        "knowledge_usage_events",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("organization_id", sa.String(length=36), nullable=False),
        sa.Column("knowledge_source_id", sa.String(length=36), nullable=False),
        sa.Column("ticket_id", sa.String(length=36), nullable=False),
        sa.Column("ai_triage_result_id", sa.String(length=36), nullable=True),
        sa.Column("prompt_version", sa.String(length=80), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("matched_terms", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"]),
        sa.ForeignKeyConstraint(["knowledge_source_id"], ["knowledge_sources.id"]),
        sa.ForeignKeyConstraint(["ticket_id"], ["tickets.id"]),
        sa.ForeignKeyConstraint(["ai_triage_result_id"], ["ai_triage_results.id"]),
    )
    op.create_index("ix_knowledge_usage_events_organization_id", "knowledge_usage_events", ["organization_id"])
    op.create_index("ix_knowledge_usage_events_knowledge_source_id", "knowledge_usage_events", ["knowledge_source_id"])
    op.create_index("ix_knowledge_usage_events_ticket_id", "knowledge_usage_events", ["ticket_id"])
    op.create_index("ix_knowledge_usage_events_ai_triage_result_id", "knowledge_usage_events", ["ai_triage_result_id"])
    op.create_index("ix_knowledge_usage_events_created_at", "knowledge_usage_events", ["created_at"])

    op.add_column("ai_triage_results", sa.Column("knowledge_sources", sa.JSON(), nullable=False, server_default='[]'))
    op.add_column("tickets", sa.Column("first_review_due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tickets", sa.Column("resolution_due_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("tickets", sa.Column("sla_status", sa.String(length=30), nullable=False, server_default="on_track"))
    op.create_index("ix_tickets_sla_status", "tickets", ["sla_status"])
    op.create_index("ix_tickets_first_review_due_at", "tickets", ["first_review_due_at"])
    op.create_index("ix_tickets_resolution_due_at", "tickets", ["resolution_due_at"])

    op.add_column("workspace_settings", sa.Column("business_timezone", sa.String(length=80), nullable=False, server_default="UTC"))
    op.add_column("workspace_settings", sa.Column("business_hours", sa.JSON(), nullable=False, server_default='{}'))
    op.add_column("workspace_settings", sa.Column("first_review_target_minutes", sa.Integer(), nullable=False, server_default="240"))
    op.add_column("workspace_settings", sa.Column("resolution_target_minutes", sa.Integer(), nullable=False, server_default="1440"))


def downgrade() -> None:
    op.drop_column("workspace_settings", "resolution_target_minutes")
    op.drop_column("workspace_settings", "first_review_target_minutes")
    op.drop_column("workspace_settings", "business_hours")
    op.drop_column("workspace_settings", "business_timezone")
    op.drop_index("ix_tickets_resolution_due_at", table_name="tickets")
    op.drop_index("ix_tickets_first_review_due_at", table_name="tickets")
    op.drop_index("ix_tickets_sla_status", table_name="tickets")
    op.drop_column("tickets", "sla_status")
    op.drop_column("tickets", "resolution_due_at")
    op.drop_column("tickets", "first_review_due_at")
    op.drop_column("ai_triage_results", "knowledge_sources")
    op.drop_index("ix_knowledge_usage_events_created_at", table_name="knowledge_usage_events")
    op.drop_index("ix_knowledge_usage_events_ai_triage_result_id", table_name="knowledge_usage_events")
    op.drop_index("ix_knowledge_usage_events_ticket_id", table_name="knowledge_usage_events")
    op.drop_index("ix_knowledge_usage_events_knowledge_source_id", table_name="knowledge_usage_events")
    op.drop_index("ix_knowledge_usage_events_organization_id", table_name="knowledge_usage_events")
    op.drop_table("knowledge_usage_events")
    op.drop_index("ix_routing_rule_executions_created_at", table_name="routing_rule_executions")
    op.drop_index("ix_routing_rule_executions_ticket_id", table_name="routing_rule_executions")
    op.drop_index("ix_routing_rule_executions_routing_rule_id", table_name="routing_rule_executions")
    op.drop_index("ix_routing_rule_executions_organization_id", table_name="routing_rule_executions")
    op.drop_table("routing_rule_executions")
    op.drop_index("ix_routing_rules_is_active", table_name="routing_rules")
    op.drop_index("ix_routing_rules_priority_order", table_name="routing_rules")
    op.drop_index("ix_routing_rules_organization_id", table_name="routing_rules")
    op.drop_table("routing_rules")
    op.drop_index("ix_knowledge_sources_effective_until", table_name="knowledge_sources")
    op.drop_index("ix_knowledge_sources_effective_from", table_name="knowledge_sources")
    op.drop_index("ix_knowledge_sources_status", table_name="knowledge_sources")
    op.drop_index("ix_knowledge_sources_organization_id", table_name="knowledge_sources")
    op.drop_table("knowledge_sources")


