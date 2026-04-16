"""Create reference-data tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "b2c3d4e5f6a1"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "countries",
        sa.Column("code", sa.CHAR(length=2), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("code", name="pk_countries"),
    )
    op.create_table(
        "portals",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(length=60), nullable=False),
        sa.Column("country_code", sa.CHAR(length=2), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("spider_class", sa.String(length=80), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("config", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.ForeignKeyConstraint(["country_code"], ["countries.code"], name="fk_portals_country_code_countries"),
        sa.PrimaryKeyConstraint("id", name="pk_portals"),
        sa.UniqueConstraint("name", "country_code", name="uq_portals_name_country"),
    )
    op.create_index("ix_portals_country_code_enabled", "portals", ["country_code", "enabled"], unique=False)
    op.create_table(
        "exchange_rates",
        sa.Column("currency", sa.CHAR(length=3), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("rate_to_eur", sa.Numeric(12, 6), nullable=False),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.PrimaryKeyConstraint("currency", "date", name="pk_exchange_rates"),
    )


def downgrade() -> None:
    op.drop_table("exchange_rates")
    op.drop_index("ix_portals_country_code_enabled", table_name="portals")
    op.drop_table("portals")
    op.drop_table("countries")
