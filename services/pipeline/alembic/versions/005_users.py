"""Create users table."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e5f6a1b2c3d4"
down_revision = "d4e5f6a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=True),
        sa.Column("oauth_provider", sa.String(length=20), nullable=True),
        sa.Column("oauth_subject", sa.String(length=100), nullable=True),
        sa.Column("display_name", sa.String(length=100), nullable=True),
        sa.Column("avatar_url", sa.Text(), nullable=True),
        sa.Column("subscription_tier", sa.String(length=20), nullable=False, server_default=sa.text("'free'")),
        sa.Column("stripe_customer_id", sa.String(length=30), nullable=True),
        sa.Column("stripe_sub_id", sa.String(length=30), nullable=True),
        sa.Column("subscription_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("alert_limit", sa.SmallInteger(), nullable=False, server_default=sa.text("3")),
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
        sa.UniqueConstraint("email", name="uq_users_email"),
        sa.UniqueConstraint("stripe_customer_id", name="uq_users_stripe_customer_id"),
        sa.UniqueConstraint("stripe_sub_id", name="uq_users_stripe_sub_id"),
    )
    op.create_index(
        "ix_users_email_active",
        "users",
        ["email"],
        unique=False,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("ix_users_email_active", table_name="users")
    op.drop_table("users")
