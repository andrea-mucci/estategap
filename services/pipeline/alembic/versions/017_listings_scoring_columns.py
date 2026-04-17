"""Normalize listings scoring columns for the scorer service."""

from __future__ import annotations

from alembic import op

revision = "e2f3a4b5c6d7"
down_revision = "d1e2f3a4b5c6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'listings'
                  AND column_name = 'estimated_price'
            ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'listings'
                  AND column_name = 'estimated_price_eur'
            ) THEN
                ALTER TABLE listings RENAME COLUMN estimated_price TO estimated_price_eur;
            END IF;

            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'listings'
                  AND column_name = 'confidence_low'
            ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'listings'
                  AND column_name = 'confidence_low_eur'
            ) THEN
                ALTER TABLE listings RENAME COLUMN confidence_low TO confidence_low_eur;
            END IF;

            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'listings'
                  AND column_name = 'confidence_high'
            ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'listings'
                  AND column_name = 'confidence_high_eur'
            ) THEN
                ALTER TABLE listings RENAME COLUMN confidence_high TO confidence_high_eur;
            END IF;
        END
        $$;
        """
    )
    op.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS estimated_price_eur NUMERIC(14, 2)")
    op.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS confidence_low_eur NUMERIC(14, 2)")
    op.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS confidence_high_eur NUMERIC(14, 2)")
    op.execute("ALTER TABLE listings ADD COLUMN IF NOT EXISTS comparable_ids UUID[]")
    op.execute("ALTER TABLE listings ALTER COLUMN estimated_price_eur TYPE NUMERIC(14, 2)")
    op.execute("ALTER TABLE listings ALTER COLUMN deal_score TYPE NUMERIC(6, 2)")
    op.execute("ALTER TABLE listings ALTER COLUMN confidence_low_eur TYPE NUMERIC(14, 2)")
    op.execute("ALTER TABLE listings ALTER COLUMN confidence_high_eur TYPE NUMERIC(14, 2)")
    op.execute("ALTER TABLE listings ALTER COLUMN model_version TYPE VARCHAR(100)")
    op.execute("ALTER TABLE listings ALTER COLUMN shap_features SET DEFAULT '[]'::jsonb")
    op.execute("UPDATE listings SET shap_features = '[]'::jsonb WHERE shap_features IS NULL")
    op.execute("ALTER TABLE listings ALTER COLUMN shap_features SET NOT NULL")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS listings_deal_tier_idx
        ON listings (deal_tier)
        WHERE deal_tier IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS listings_scored_at_idx
        ON listings (scored_at)
        WHERE scored_at IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS listings_scored_at_idx")
    op.execute("DROP INDEX IF EXISTS listings_deal_tier_idx")
    op.execute("ALTER TABLE listings ALTER COLUMN shap_features DROP NOT NULL")
    op.execute("ALTER TABLE listings ALTER COLUMN shap_features DROP DEFAULT")
    op.execute("ALTER TABLE listings ALTER COLUMN model_version TYPE VARCHAR(30)")
    op.execute("ALTER TABLE listings ALTER COLUMN deal_score TYPE NUMERIC(5, 2)")
    op.execute("ALTER TABLE listings DROP COLUMN IF EXISTS comparable_ids")
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'listings'
                  AND column_name = 'estimated_price_eur'
            ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'listings'
                  AND column_name = 'estimated_price'
            ) THEN
                ALTER TABLE listings RENAME COLUMN estimated_price_eur TO estimated_price;
            END IF;

            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'listings'
                  AND column_name = 'confidence_low_eur'
            ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'listings'
                  AND column_name = 'confidence_low'
            ) THEN
                ALTER TABLE listings RENAME COLUMN confidence_low_eur TO confidence_low;
            END IF;

            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'listings'
                  AND column_name = 'confidence_high_eur'
            ) AND NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'listings'
                  AND column_name = 'confidence_high'
            ) THEN
                ALTER TABLE listings RENAME COLUMN confidence_high_eur TO confidence_high;
            END IF;
        END
        $$;
        """
    )
