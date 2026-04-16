"""Create alert rules and delivery log tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f6a1b2c3d4e5"
down_revision = "e5f6a1b2c3d4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "alert_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("filters", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("channels", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{\"email\": true}'::jsonb")),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("last_triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("trigger_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_alert_rules_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_alert_rules"),
    )
    op.create_index("alert_rules_filters_gin_idx", "alert_rules", ["filters"], unique=False, postgresql_using="gin")
    op.create_index("ix_alert_rules_user_id_active", "alert_rules", ["user_id", "active"], unique=False)

    op.create_table(
        "alert_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country", sa.CHAR(length=2), nullable=False),
        sa.Column("channel", sa.String(length=20), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["rule_id"], ["alert_rules.id"], name="fk_alert_log_rule_id_alert_rules", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_alert_log"),
    )
    op.execute("CREATE INDEX alert_log_rule_id_sent_at_idx ON alert_log (rule_id, sent_at DESC)")
    op.create_index(
        "alert_log_pending_status_idx",
        "alert_log",
        ["status"],
        unique=False,
        postgresql_where=sa.text("status = 'pending'"),
    )


def downgrade() -> None:
    op.drop_index("alert_log_pending_status_idx", table_name="alert_log")
    op.execute("DROP INDEX IF EXISTS alert_log_rule_id_sent_at_idx")
    op.drop_table("alert_log")
    op.drop_index("ix_alert_rules_user_id_active", table_name="alert_rules")
    op.drop_index("alert_rules_filters_gin_idx", table_name="alert_rules")
    op.drop_table("alert_rules")
