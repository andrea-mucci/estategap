"""Create partitioned listings and price-history tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "c3d4e5f6a1b2"
down_revision = "b2c3d4e5f6a1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE listings (
            id UUID NOT NULL DEFAULT gen_random_uuid(),
            canonical_id UUID,
            country CHAR(2) NOT NULL,
            source VARCHAR(30) NOT NULL,
            source_id VARCHAR(80) NOT NULL,
            source_url TEXT NOT NULL,
            portal_id UUID REFERENCES portals(id),
            address TEXT,
            neighborhood VARCHAR(100),
            district VARCHAR(100),
            city VARCHAR(100),
            region VARCHAR(100),
            postal_code VARCHAR(15),
            location geometry(POINT, 4326),
            zone_id UUID,
            asking_price NUMERIC(14, 2),
            currency CHAR(3) NOT NULL DEFAULT 'EUR',
            asking_price_eur NUMERIC(14, 2),
            price_per_m2_eur NUMERIC(10, 2),
            property_category VARCHAR(20),
            property_type VARCHAR(30),
            built_area NUMERIC(10, 2),
            area_unit VARCHAR(5) DEFAULT 'm2',
            built_area_m2 NUMERIC(10, 2),
            usable_area_m2 NUMERIC(10, 2),
            plot_area_m2 NUMERIC(12, 2),
            bedrooms SMALLINT,
            bathrooms SMALLINT,
            toilets SMALLINT,
            floor_number SMALLINT,
            total_floors SMALLINT,
            parking_spaces SMALLINT,
            has_lift BOOLEAN,
            has_pool BOOLEAN,
            has_garden BOOLEAN,
            terrace_area_m2 NUMERIC(8, 2),
            garage_area_m2 NUMERIC(8, 2),
            year_built SMALLINT,
            last_renovated SMALLINT,
            condition VARCHAR(20),
            energy_rating CHAR(1),
            energy_rating_kwh NUMERIC(8, 2),
            co2_rating CHAR(1),
            co2_kg_m2 NUMERIC(8, 2),
            frontage_m NUMERIC(6, 2),
            ceiling_height_m NUMERIC(4, 2),
            loading_docks SMALLINT,
            power_kw NUMERIC(8, 2),
            office_area_m2 NUMERIC(10, 2),
            warehouse_area_m2 NUMERIC(10, 2),
            buildability_index NUMERIC(4, 2),
            urban_classification VARCHAR(30),
            land_use VARCHAR(30),
            estimated_price NUMERIC(14, 2),
            deal_score NUMERIC(5, 2),
            deal_tier SMALLINT,
            confidence_low NUMERIC(14, 2),
            confidence_high NUMERIC(14, 2),
            shap_features JSONB,
            model_version VARCHAR(30),
            scored_at TIMESTAMPTZ,
            status VARCHAR(20) NOT NULL DEFAULT 'active',
            description_orig TEXT,
            description_lang CHAR(2),
            images_count SMALLINT DEFAULT 0,
            first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            published_at TIMESTAMPTZ,
            delisted_at TIMESTAMPTZ,
            raw_hash CHAR(64),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            days_on_market INTEGER GENERATED ALWAYS AS (
                CASE
                    WHEN published_at IS NULL THEN NULL
                    ELSE EXTRACT(DAY FROM COALESCE(delisted_at, NOW()) - published_at)::INTEGER
                END
            ) STORED,
            PRIMARY KEY (id, country),
            UNIQUE (source, source_id, country)
        ) PARTITION BY LIST (country)
        """
    )
    for country in ["ES", "FR", "IT", "PT", "DE", "GB", "NL", "US"]:
        op.execute(
            f"CREATE TABLE listings_{country.lower()} PARTITION OF listings FOR VALUES IN ('{country}')"
        )
    op.execute("CREATE TABLE listings_other PARTITION OF listings DEFAULT")
    op.execute("CREATE INDEX listings_location_gist_idx ON listings USING GIST (location)")
    op.execute("CREATE INDEX listings_country_status_idx ON listings (country, status)")
    op.execute(
        "CREATE INDEX listings_city_status_active_idx ON listings (city, status) WHERE status = 'active'"
    )
    op.execute(
        "CREATE INDEX listings_deal_tier_active_idx ON listings (deal_tier) WHERE status = 'active'"
    )
    op.execute(
        """
        CREATE INDEX listings_description_search_idx
        ON listings USING GIN (to_tsvector('simple', COALESCE(description_orig, '')))
        """
    )
    op.execute("CREATE INDEX listings_zone_id_idx ON listings (zone_id) WHERE zone_id IS NOT NULL")
    op.execute("CREATE INDEX listings_scored_at_idx ON listings (scored_at) WHERE scored_at IS NOT NULL")

    op.create_table(
        "price_history",
        sa.Column("id", sa.BigInteger(), sa.Identity(), nullable=False),
        sa.Column("listing_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("country", sa.CHAR(length=2), nullable=False),
        sa.Column("old_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("new_price", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), nullable=False),
        sa.Column("old_price_eur", sa.Numeric(14, 2), nullable=True),
        sa.Column("new_price_eur", sa.Numeric(14, 2), nullable=True),
        sa.Column("change_type", sa.String(length=20), nullable=False, server_default=sa.text("'price_change'")),
        sa.Column("old_status", sa.String(length=20), nullable=True),
        sa.Column("new_status", sa.String(length=20), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("source", sa.String(length=30), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_price_history"),
    )
    op.execute(
        "CREATE INDEX price_history_listing_id_recorded_at_idx ON price_history (listing_id, recorded_at DESC)"
    )
    op.execute(
        "CREATE INDEX ix_price_history_country_recorded_at ON price_history (country, recorded_at DESC)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_price_history_country_recorded_at")
    op.execute("DROP INDEX IF EXISTS price_history_listing_id_recorded_at_idx")
    op.drop_table("price_history")
    op.execute("DROP TABLE IF EXISTS listings CASCADE")
