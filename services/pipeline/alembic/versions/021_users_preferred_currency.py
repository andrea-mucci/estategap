"""Add preferred currency to users."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "f4a5b6c7d8e9"
down_revision = "e2f3a4b5c6d7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "preferred_currency",
            sa.String(length=3),
            nullable=False,
            server_default=sa.text("'EUR'"),
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "preferred_currency")
