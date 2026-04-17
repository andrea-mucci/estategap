"""Add production hardening indexes and anonymization tracking."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "028_add_performance_indexes"
down_revision = "f0a1b2c3d4e5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("anonymized_at", sa.DateTime(timezone=True), nullable=True))

    with op.get_context().autocommit_block():
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_listings_country_status_created
            ON listings (country, status, created_at DESC)
            """
        )
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_listings_zone_score_active
            ON listings (zone_id, deal_score DESC)
            WHERE status = 'active'
            """
        )
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_alert_rules_user_active
            ON alert_rules (user_id)
            WHERE is_active = TRUE
            """
        )
        op.execute(
            """
            CREATE INDEX IF NOT EXISTS ix_alert_history_user_created
            ON alert_history (rule_id, triggered_at DESC)
            """
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.execute("DROP INDEX IF EXISTS ix_alert_history_user_created")
        op.execute("DROP INDEX IF EXISTS ix_alert_rules_user_active")
        op.execute("DROP INDEX IF EXISTS ix_listings_zone_score_active")
        op.execute("DROP INDEX IF EXISTS ix_listings_country_status_created")

    op.drop_column("users", "anonymized_at")
