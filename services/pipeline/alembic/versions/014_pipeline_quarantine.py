"""Add pipeline quarantine support and listing completeness."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b9c0d1e2f3a4"
down_revision = "a8b9c0d1e2f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "quarantine",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("source", sa.String(length=30), nullable=False),
        sa.Column("source_id", sa.String(length=80), nullable=True),
        sa.Column("country", sa.CHAR(length=2), nullable=True),
        sa.Column("portal", sa.String(length=30), nullable=True),
        sa.Column("reason", sa.String(length=50), nullable=False),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "quarantined_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("NOW()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_quarantine"),
    )
    op.create_index(
        "ix_quarantine_source_country_quarantined_at",
        "quarantine",
        ["source", "country", "quarantined_at"],
        unique=False,
    )
    op.add_column("listings", sa.Column("data_completeness", sa.Numeric(4, 2), nullable=True))


def downgrade() -> None:
    op.drop_column("listings", "data_completeness")
    op.drop_index("ix_quarantine_source_country_quarantined_at", table_name="quarantine")
    op.drop_table("quarantine")
