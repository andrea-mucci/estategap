"""Add per-user ownership to custom zones."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "e2f3a4b5c6d7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "zones",
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_zones_user_id_users",
        "zones",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_zones_user_id", "zones", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_zones_user_id", table_name="zones")
    op.drop_constraint("fk_zones_user_id_users", "zones", type_="foreignkey")
    op.drop_column("zones", "user_id")
