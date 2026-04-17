"""Add delivery frequency to alert rules."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "f4b5c6d7e8f9"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "alert_rules",
        sa.Column(
            "frequency",
            sa.String(length=10),
            nullable=False,
            server_default=sa.text("'instant'"),
        ),
    )
    op.create_check_constraint(
        "alert_rules_frequency_check",
        "alert_rules",
        "frequency IN ('instant', 'hourly', 'daily')",
    )
    op.create_index(
        "idx_alert_rules_frequency",
        "alert_rules",
        ["frequency"],
        unique=False,
        postgresql_where=sa.text("is_active = TRUE"),
    )


def downgrade() -> None:
    op.drop_index("idx_alert_rules_frequency", table_name="alert_rules")
    op.drop_constraint("alert_rules_frequency_check", "alert_rules", type_="check")
    op.drop_column("alert_rules", "frequency")
