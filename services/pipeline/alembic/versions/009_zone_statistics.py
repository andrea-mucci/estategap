"""Create the zone statistics materialized view."""

from __future__ import annotations

from alembic import op

revision = "c3d4e5f6a1b3"
down_revision = "b2c3d4e5f6a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE MATERIALIZED VIEW zone_statistics AS
        SELECT
            z.id AS zone_id,
            z.country_code,
            z.name AS zone_name,
            COUNT(*) AS listing_count,
            COUNT(*) FILTER (WHERE l.status = 'active') AS active_listings,
            PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY l.price_per_m2_eur) AS median_price_m2_eur,
            SUM(l.asking_price_eur) AS total_volume_eur,
            AVG(l.deal_score) AS avg_deal_score,
            MIN(l.asking_price_eur) AS min_price_eur,
            MAX(l.asking_price_eur) AS max_price_eur,
            NOW() AS refreshed_at
        FROM zones z
        JOIN listings l ON l.zone_id = z.id
        WHERE l.status = 'active'
          AND l.price_per_m2_eur IS NOT NULL
        GROUP BY z.id, z.country_code, z.name
        WITH DATA
        """
    )
    op.execute("CREATE UNIQUE INDEX zone_statistics_zone_id_idx ON zone_statistics (zone_id)")
    op.execute("CREATE INDEX zone_statistics_country_code_idx ON zone_statistics (country_code)")
    op.execute(
        """
        CREATE OR REPLACE FUNCTION refresh_zone_statistics()
        RETURNS void LANGUAGE plpgsql AS $$
        BEGIN
            REFRESH MATERIALIZED VIEW zone_statistics;
        END;
        $$;
        """
    )


def downgrade() -> None:
    op.execute("DROP FUNCTION IF EXISTS refresh_zone_statistics()")
    op.execute("DROP INDEX IF EXISTS zone_statistics_country_code_idx")
    op.execute("DROP INDEX IF EXISTS zone_statistics_zone_id_idx")
    op.execute("DROP MATERIALIZED VIEW IF EXISTS zone_statistics")
