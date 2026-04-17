from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("geopandas")

from estategap_pipeline.zone_import.us_tiger import import_level


@pytest.mark.asyncio
async def test_import_us_county_resolves_parent(asyncpg_pool) -> None:
    fixture = Path(__file__).resolve().parent / "fixtures" / "us_tiger_county_sample.geojson"
    async with asyncpg_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO zones (
                name,
                name_local,
                country_code,
                level,
                geometry,
                bbox,
                slug
            ) VALUES (
                'New York',
                '36',
                'US',
                1,
                ST_GeomFromText('POLYGON((-74.5 40.4, -73.5 40.4, -73.5 45.1, -74.5 45.1, -74.5 40.4))', 4326),
                ST_GeomFromText('POLYGON((-74.5 40.4, -73.5 40.4, -73.5 45.1, -74.5 45.1, -74.5 40.4))', 4326),
                'us-state-36'
            )
            ON CONFLICT (slug) DO NOTHING
            """
        )

    records = await import_level(asyncpg_pool, level="county", source=fixture)

    assert records[0]["level"] == 2
    async with asyncpg_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT name, name_local, level, parent_id, ST_AsText(geometry) AS geometry_wkt
            FROM zones
            WHERE slug = 'us-county-36061'
            """
        )

    assert row is not None
    assert row["name"] == "New York County"
    assert row["name_local"] == "36061"
    assert row["level"] == 2
    assert row["parent_id"] is not None
    assert row["geometry_wkt"] is not None
