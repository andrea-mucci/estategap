from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

pytest.importorskip("asyncpg")
pytest.importorskip("pandas")
pytest.importorskip("testcontainers")

import asyncpg
from testcontainers.postgres import PostgresContainer

from estategap_ml.trainer.data_export import export_training_data


def _asyncpg_dsn(sqlalchemy_dsn: str) -> str:
    return sqlalchemy_dsn.replace("postgresql+psycopg2://", "postgresql://", 1)


@pytest.mark.asyncio
async def test_export_training_data_filters_out_ineligible_rows() -> None:
    with PostgresContainer("postgis/postgis:16-3.4") as postgres:
        dsn = _asyncpg_dsn(postgres.get_connection_url())
        conn = await asyncpg.connect(dsn)
        try:
            await conn.execute("CREATE EXTENSION IF NOT EXISTS postgis")
            await conn.execute(
                """
                CREATE TABLE listings (
                    id UUID PRIMARY KEY,
                    country CHAR(2) NOT NULL,
                    city TEXT,
                    zone_id UUID,
                    location geometry(POINT, 4326),
                    asking_price_eur NUMERIC,
                    price_per_m2_eur NUMERIC,
                    built_area_m2 NUMERIC,
                    usable_area_m2 NUMERIC,
                    bedrooms SMALLINT,
                    bathrooms SMALLINT,
                    floor_number SMALLINT,
                    total_floors SMALLINT,
                    has_lift BOOLEAN,
                    parking_spaces SMALLINT,
                    property_type TEXT,
                    property_category TEXT,
                    energy_rating CHAR(1),
                    condition TEXT,
                    year_built SMALLINT,
                    images_count SMALLINT,
                    days_on_market INTEGER,
                    published_at TIMESTAMPTZ,
                    status TEXT,
                    dist_metro_m INTEGER,
                    dist_train_m INTEGER,
                    dist_beach_m INTEGER,
                    data_completeness NUMERIC,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
                """
            )
            records = []
            for idx in range(50):
                eligible = idx < 30
                records.append(
                    (
                        uuid4(),
                        "ES",
                        "Madrid",
                        None,
                        "POINT(-3.7038 40.4168)",
                        300000 + idx,
                        4000 + idx,
                        80,
                        70,
                        2,
                        1,
                        2,
                        6,
                        True,
                        1,
                        "apartment",
                        "residential",
                        "B",
                        "good",
                        2010,
                        5,
                        45 if eligible else 5,
                        "2025-06-01T00:00:00Z",
                        "sold" if eligible else "active",
                        250,
                        500,
                        10000,
                        0.9,
                    )
                )
            await conn.executemany(
                """
                INSERT INTO listings (
                    id, country, city, zone_id, location, asking_price_eur, price_per_m2_eur,
                    built_area_m2, usable_area_m2, bedrooms, bathrooms, floor_number,
                    total_floors, has_lift, parking_spaces, property_type, property_category,
                    energy_rating, condition, year_built, images_count, days_on_market,
                    published_at, status, dist_metro_m, dist_train_m, dist_beach_m, data_completeness
                )
                VALUES (
                    $1, $2, $3, $4, ST_GeomFromText($5, 4326), $6, $7, $8, $9, $10, $11, $12,
                    $13, $14, $15, $16, $17, $18, $19, $20, $21, $22, $23, $24, $25, $26, $27, $28
                )
                """,
                records,
            )
        finally:
            await conn.close()

        frame = await export_training_data("es", dsn)
        assert len(frame) == 30
        assert frame["asking_price_eur"].notna().all()
        assert frame["built_area_m2"].notna().all()
