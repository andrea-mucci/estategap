"""Add EU listing columns for UK, FR, IT, and NL portals."""

from __future__ import annotations

from alembic import op

revision = "a5b6c7d8e9f0"
down_revision = "f4a5b6c7d8ea"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE listings
            ADD COLUMN IF NOT EXISTS council_tax_band VARCHAR(2),
            ADD COLUMN IF NOT EXISTS epc_rating VARCHAR(1),
            ADD COLUMN IF NOT EXISTS tenure VARCHAR(20),
            ADD COLUMN IF NOT EXISTS leasehold_years_remaining SMALLINT,
            ADD COLUMN IF NOT EXISTS seller_type VARCHAR(10),
            ADD COLUMN IF NOT EXISTS omi_zone_code VARCHAR(20),
            ADD COLUMN IF NOT EXISTS omi_price_min_eur_m2 NUMERIC(10, 2),
            ADD COLUMN IF NOT EXISTS omi_price_max_eur_m2 NUMERIC(10, 2),
            ADD COLUMN IF NOT EXISTS omi_period VARCHAR(10),
            ADD COLUMN IF NOT EXISTS price_vs_omi NUMERIC(6, 4),
            ADD COLUMN IF NOT EXISTS bag_id VARCHAR(32),
            ADD COLUMN IF NOT EXISTS official_area_m2 NUMERIC(10, 2),
            ADD COLUMN IF NOT EXISTS dvf_nearby_count SMALLINT,
            ADD COLUMN IF NOT EXISTS dvf_median_price_m2 NUMERIC(10, 2),
            ADD COLUMN IF NOT EXISTS uk_lr_match_count SMALLINT,
            ADD COLUMN IF NOT EXISTS uk_lr_last_price_gbp INTEGER,
            ADD COLUMN IF NOT EXISTS uk_lr_last_date DATE
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS listings_bag_id_idx
        ON listings (country, bag_id)
        WHERE bag_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS listings_bag_id_idx")
    op.execute(
        """
        ALTER TABLE listings
            DROP COLUMN IF EXISTS uk_lr_last_date,
            DROP COLUMN IF EXISTS uk_lr_last_price_gbp,
            DROP COLUMN IF EXISTS uk_lr_match_count,
            DROP COLUMN IF EXISTS dvf_median_price_m2,
            DROP COLUMN IF EXISTS dvf_nearby_count,
            DROP COLUMN IF EXISTS official_area_m2,
            DROP COLUMN IF EXISTS bag_id,
            DROP COLUMN IF EXISTS price_vs_omi,
            DROP COLUMN IF EXISTS omi_period,
            DROP COLUMN IF EXISTS omi_price_max_eur_m2,
            DROP COLUMN IF EXISTS omi_price_min_eur_m2,
            DROP COLUMN IF EXISTS omi_zone_code,
            DROP COLUMN IF EXISTS seller_type,
            DROP COLUMN IF EXISTS leasehold_years_remaining,
            DROP COLUMN IF EXISTS tenure,
            DROP COLUMN IF EXISTS epc_rating,
            DROP COLUMN IF EXISTS council_tax_band
        """
    )
