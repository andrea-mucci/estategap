"""Add enrichment columns and POI storage."""

from __future__ import annotations

from alembic import op

revision = "c0d1e2f3a4b5"
down_revision = "b9c0d1e2f3a4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE listings
            ADD COLUMN IF NOT EXISTS cadastral_ref VARCHAR(30),
            ADD COLUMN IF NOT EXISTS official_built_area_m2 NUMERIC(10, 2),
            ADD COLUMN IF NOT EXISTS area_discrepancy_flag BOOLEAN,
            ADD COLUMN IF NOT EXISTS building_geometry_wkt TEXT,
            ADD COLUMN IF NOT EXISTS enrichment_status VARCHAR(20) DEFAULT 'pending',
            ADD COLUMN IF NOT EXISTS enrichment_attempted_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS dist_metro_m INTEGER,
            ADD COLUMN IF NOT EXISTS dist_train_m INTEGER,
            ADD COLUMN IF NOT EXISTS dist_airport_m INTEGER,
            ADD COLUMN IF NOT EXISTS dist_park_m INTEGER,
            ADD COLUMN IF NOT EXISTS dist_beach_m INTEGER
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS listings_enrichment_status
        ON listings (country, enrichment_status)
        WHERE enrichment_status = 'pending'
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS pois (
            id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
            osm_id BIGINT,
            country CHAR(2) NOT NULL,
            category VARCHAR(20) NOT NULL,
            name TEXT,
            location geometry(POINT, 4326) NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS pois_location_gist ON pois USING GIST (location)")
    op.execute("CREATE INDEX IF NOT EXISTS pois_country_category ON pois (country, category)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS pois_country_category")
    op.execute("DROP INDEX IF EXISTS pois_location_gist")
    op.execute("DROP TABLE IF EXISTS pois")
    op.execute("DROP INDEX IF EXISTS listings_enrichment_status")
    op.execute(
        """
        ALTER TABLE listings
            DROP COLUMN IF EXISTS dist_beach_m,
            DROP COLUMN IF EXISTS dist_park_m,
            DROP COLUMN IF EXISTS dist_airport_m,
            DROP COLUMN IF EXISTS dist_train_m,
            DROP COLUMN IF EXISTS dist_metro_m,
            DROP COLUMN IF EXISTS enrichment_attempted_at,
            DROP COLUMN IF EXISTS enrichment_status,
            DROP COLUMN IF EXISTS building_geometry_wkt,
            DROP COLUMN IF EXISTS area_discrepancy_flag,
            DROP COLUMN IF EXISTS official_built_area_m2,
            DROP COLUMN IF EXISTS cadastral_ref
        """
    )
