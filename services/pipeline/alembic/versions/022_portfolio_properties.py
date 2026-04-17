"""Create portfolio properties table."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "f4a5b6c7d8ea"
down_revision = "f4a5b6c7d8e9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portfolio_properties",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("address", sa.Text(), nullable=False),
        sa.Column("lat", sa.Float(), nullable=True),
        sa.Column("lng", sa.Float(), nullable=True),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=False),
        sa.Column("purchase_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("purchase_currency", sa.String(length=3), nullable=False),
        sa.Column("purchase_price_eur", sa.Numeric(18, 4), nullable=False),
        sa.Column("purchase_date", sa.Date(), nullable=False),
        sa.Column("monthly_rental_income", sa.Numeric(18, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("monthly_rental_income_eur", sa.Numeric(18, 4), nullable=False, server_default=sa.text("0")),
        sa.Column("area_m2", sa.Numeric(10, 2), nullable=True),
        sa.Column("property_type", sa.String(length=20), nullable=False, server_default=sa.text("'residential'")),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.CheckConstraint("purchase_price > 0", name="ck_portfolio_properties_purchase_price"),
        sa.CheckConstraint("monthly_rental_income >= 0", name="ck_portfolio_properties_monthly_rental_income"),
        sa.CheckConstraint("purchase_date <= CURRENT_DATE", name="ck_portfolio_properties_purchase_date"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_portfolio_properties_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["zone_id"], ["zones.id"], name="fk_portfolio_properties_zone_id_zones"),
        sa.PrimaryKeyConstraint("id", name="pk_portfolio_properties"),
    )
    op.create_index("idx_portfolio_properties_user_id", "portfolio_properties", ["user_id"], unique=False)
    op.create_index("idx_portfolio_properties_country", "portfolio_properties", ["country"], unique=False)
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_portfolio_properties_updated_at()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_portfolio_properties_updated_at
        BEFORE UPDATE ON portfolio_properties
        FOR EACH ROW
        EXECUTE FUNCTION set_portfolio_properties_updated_at();
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_portfolio_properties_updated_at ON portfolio_properties")
    op.execute("DROP FUNCTION IF EXISTS set_portfolio_properties_updated_at()")
    op.drop_index("idx_portfolio_properties_country", table_name="portfolio_properties")
    op.drop_index("idx_portfolio_properties_user_id", table_name="portfolio_properties")
    op.drop_table("portfolio_properties")
