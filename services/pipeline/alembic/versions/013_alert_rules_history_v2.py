"""Reshape alert rules for tiered rules and delivery history."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "a8b9c0d1e2f3"
down_revision = "f7a8b9c0d1e2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "alert_rules",
        sa.Column(
            "zone_ids",
            postgresql.ARRAY(postgresql.UUID(as_uuid=True)),
            nullable=False,
            server_default=sa.text("'{}'::uuid[]"),
        ),
    )
    op.add_column(
        "alert_rules",
        sa.Column(
            "category",
            sa.String(length=50),
            nullable=False,
            server_default=sa.text("'residential'"),
        ),
    )
    op.add_column(
        "alert_rules",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.alter_column("alert_rules", "name", existing_type=sa.String(length=100), type_=sa.String(length=255))
    op.rename_column("alert_rules", "filters", "filter")
    op.execute("UPDATE alert_rules SET is_active = active")
    op.execute(
        """
        UPDATE alert_rules
        SET channels = CASE
            WHEN jsonb_typeof(channels) = 'array' THEN channels
            WHEN jsonb_typeof(channels) = 'object' THEN COALESCE(
                (
                    SELECT jsonb_agg(jsonb_build_object('type', key))
                    FROM jsonb_each(channels)
                    WHERE value = 'true'::jsonb
                ),
                '[]'::jsonb
            )
            ELSE '[]'::jsonb
        END
        """
    )
    op.alter_column(
        "alert_rules",
        "channels",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'[]'::jsonb"),
    )
    op.drop_column("alert_rules", "active")
    op.drop_column("alert_rules", "last_triggered_at")
    op.drop_column("alert_rules", "trigger_count")
    op.drop_index("alert_rules_filters_gin_idx", table_name="alert_rules")
    op.drop_index("ix_alert_rules_user_id_active", table_name="alert_rules")
    op.create_index("idx_alert_rules_user_id", "alert_rules", ["user_id"], unique=False)
    op.create_index(
        "idx_alert_rules_user_active",
        "alert_rules",
        ["user_id"],
        unique=False,
        postgresql_where=sa.text("is_active = TRUE"),
    )

    op.rename_table("alert_log", "alert_history")
    op.rename_column("alert_history", "status", "delivery_status")
    op.rename_column("alert_history", "error_message", "error_detail")
    op.rename_column("alert_history", "sent_at", "delivered_at")
    op.rename_column("alert_history", "created_at", "triggered_at")
    op.drop_column("alert_history", "country")
    op.drop_index("alert_log_pending_status_idx", table_name="alert_history")
    op.execute("DROP INDEX IF EXISTS alert_log_rule_id_sent_at_idx")
    op.execute("DROP INDEX IF EXISTS ix_alert_log_listing_id")
    op.create_index(
        "idx_alert_history_rule_id",
        "alert_history",
        ["rule_id", sa.text("triggered_at DESC")],
        unique=False,
    )
    op.create_index("idx_alert_history_user", "alert_history", ["rule_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_alert_history_user", table_name="alert_history")
    op.drop_index("idx_alert_history_rule_id", table_name="alert_history")
    op.add_column("alert_history", sa.Column("country", sa.CHAR(length=2), nullable=False, server_default="DE"))
    op.rename_column("alert_history", "triggered_at", "created_at")
    op.rename_column("alert_history", "delivered_at", "sent_at")
    op.rename_column("alert_history", "error_detail", "error_message")
    op.rename_column("alert_history", "delivery_status", "status")
    op.rename_table("alert_history", "alert_log")
    op.execute("CREATE INDEX alert_log_rule_id_sent_at_idx ON alert_log (rule_id, sent_at DESC)")
    op.create_index(
        "alert_log_pending_status_idx",
        "alert_log",
        ["status"],
        unique=False,
        postgresql_where=sa.text("status = 'pending'"),
    )

    op.drop_index("idx_alert_rules_user_active", table_name="alert_rules")
    op.drop_index("idx_alert_rules_user_id", table_name="alert_rules")
    op.add_column(
        "alert_rules",
        sa.Column("trigger_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column("alert_rules", sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "alert_rules",
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.execute("UPDATE alert_rules SET active = is_active")
    op.rename_column("alert_rules", "filter", "filters")
    op.alter_column(
        "alert_rules",
        "channels",
        existing_type=postgresql.JSONB(astext_type=sa.Text()),
        server_default=sa.text("'{\"email\": true}'::jsonb"),
    )
    op.drop_column("alert_rules", "is_active")
    op.drop_column("alert_rules", "category")
    op.drop_column("alert_rules", "zone_ids")
    op.alter_column("alert_rules", "name", existing_type=sa.String(length=255), type_=sa.String(length=100))
    op.create_index("alert_rules_filters_gin_idx", "alert_rules", ["filters"], unique=False, postgresql_using="gin")
    op.create_index("ix_alert_rules_user_id_active", "alert_rules", ["user_id", "active"], unique=False)
