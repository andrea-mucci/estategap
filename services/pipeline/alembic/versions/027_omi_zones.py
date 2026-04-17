"""Create the Italy OMI zone reference table."""

from __future__ import annotations

from alembic import op

revision = "d8e9f0a1b2c3"
down_revision = "c7d8e9f0a1b2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS omi_zones (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            zona_omi VARCHAR(20) NOT NULL,
            comune_istat VARCHAR(10),
            comune_name VARCHAR(150),
            period VARCHAR(10) NOT NULL,
            tipologia VARCHAR(80) NOT NULL,
            fascia VARCHAR(20),
            price_min NUMERIC(10, 2),
            price_max NUMERIC(10, 2),
            geometry geometry(MULTIPOLYGON, 4326),
            loaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_omi_zone UNIQUE (zona_omi, period, tipologia)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS omi_zones_lookup_idx ON omi_zones (zona_omi, period, tipologia)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS omi_zones_geom_idx ON omi_zones USING GIST (geometry)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS omi_zones_geom_idx")
    op.execute("DROP INDEX IF EXISTS omi_zones_lookup_idx")
    op.drop_table("omi_zones")
