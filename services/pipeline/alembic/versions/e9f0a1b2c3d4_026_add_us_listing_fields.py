"""Add US listing fields and model confidence metadata."""

from __future__ import annotations

from alembic import op

revision = "e9f0a1b2c3d4"
down_revision = "d8e9f0a1b2c3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE listings
            ADD COLUMN IF NOT EXISTS hoa_fees_monthly_usd INTEGER,
            ADD COLUMN IF NOT EXISTS lot_size_sqft NUMERIC(10, 2),
            ADD COLUMN IF NOT EXISTS lot_size_m2 NUMERIC(10, 2),
            ADD COLUMN IF NOT EXISTS tax_assessed_value_usd INTEGER,
            ADD COLUMN IF NOT EXISTS school_rating NUMERIC(3, 1),
            ADD COLUMN IF NOT EXISTS zestimate_reference_usd INTEGER,
            ADD COLUMN IF NOT EXISTS compete_score SMALLINT,
            ADD COLUMN IF NOT EXISTS mls_id TEXT,
            ADD COLUMN IF NOT EXISTS built_area_sqft NUMERIC(10, 2)
        """
    )
    op.execute(
        """
        ALTER TABLE model_versions
            ADD COLUMN IF NOT EXISTS transfer_learned BOOLEAN NOT NULL DEFAULT FALSE,
            ADD COLUMN IF NOT EXISTS base_country CHAR(2),
            ADD COLUMN IF NOT EXISTS confidence TEXT NOT NULL DEFAULT 'full'
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS listings_mls_id_idx
        ON listings (country, mls_id)
        WHERE mls_id IS NOT NULL
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS listings_mls_id_idx")
    op.execute(
        """
        ALTER TABLE model_versions
            DROP COLUMN IF EXISTS confidence,
            DROP COLUMN IF EXISTS base_country,
            DROP COLUMN IF EXISTS transfer_learned
        """
    )
    op.execute(
        """
        ALTER TABLE listings
            DROP COLUMN IF EXISTS built_area_sqft,
            DROP COLUMN IF EXISTS mls_id,
            DROP COLUMN IF EXISTS compete_score,
            DROP COLUMN IF EXISTS zestimate_reference_usd,
            DROP COLUMN IF EXISTS school_rating,
            DROP COLUMN IF EXISTS tax_assessed_value_usd,
            DROP COLUMN IF EXISTS lot_size_m2,
            DROP COLUMN IF EXISTS lot_size_sqft,
            DROP COLUMN IF EXISTS hoa_fees_monthly_usd
        """
    )
