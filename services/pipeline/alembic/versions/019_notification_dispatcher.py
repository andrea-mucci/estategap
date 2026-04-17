"""Add notification dispatcher columns to users and alert_history."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "f4b5c6d7e8f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "preferred_language",
            sa.String(length=10),
            nullable=False,
            server_default=sa.text("'en'"),
        ),
    )
    op.add_column("users", sa.Column("telegram_chat_id", sa.BigInteger(), nullable=True))
    op.add_column("users", sa.Column("telegram_link_token", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("push_subscription_json", sa.Text(), nullable=True))
    op.add_column("users", sa.Column("webhook_secret", sa.String(length=64), nullable=True))
    op.add_column("users", sa.Column("phone_e164", sa.String(length=20), nullable=True))

    op.add_column("alert_history", sa.Column("event_id", sa.Uuid(), nullable=True))
    op.add_column(
        "alert_history",
        sa.Column(
            "attempt_count",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.create_index("idx_alert_history_event_id", "alert_history", ["event_id"], unique=False)
    op.create_index(
        "uq_alert_history_event_channel",
        "alert_history",
        ["event_id", "channel"],
        unique=True,
        postgresql_where=sa.text("event_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_alert_history_event_channel", table_name="alert_history")
    op.drop_index("idx_alert_history_event_id", table_name="alert_history")
    op.drop_column("alert_history", "attempt_count")
    op.drop_column("alert_history", "event_id")

    op.drop_column("users", "phone_e164")
    op.drop_column("users", "webhook_secret")
    op.drop_column("users", "push_subscription_json")
    op.drop_column("users", "telegram_link_token")
    op.drop_column("users", "telegram_chat_id")
    op.drop_column("users", "preferred_language")
