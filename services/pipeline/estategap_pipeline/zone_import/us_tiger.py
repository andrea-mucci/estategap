"""Import US TIGER/Line administrative zones into the shared zones table."""

from __future__ import annotations

import argparse
import asyncio
import re
from pathlib import Path
from typing import Any

import asyncpg  # type: ignore[import-untyped]
import geopandas as gpd


TIGER_BASE_URL = "https://www2.census.gov/geo/tiger/TIGER2024"
LEVEL_CONFIG = {
    "state": {
        "path": "STATE/tl_2024_us_state.zip",
        "code_column": "STATEFP",
        "name_column": "NAME",
        "level": 1,
        "parent_level": None,
    },
    "county": {
        "path": "COUNTY/tl_2024_us_county.zip",
        "code_column": "GEOID",
        "name_column": "NAME",
        "level": 2,
        "parent_level": 1,
    },
    "city": {
        "path": "PLACE/tl_2024_{state_fips}_place.zip",
        "code_column": "GEOID",
        "name_column": "NAME",
        "level": 3,
        "parent_level": 2,
    },
    "zipcode": {
        "path": "ZCTA520/tl_2024_us_zcta520.zip",
        "code_column": "ZCTA5CE20",
        "name_column": "ZCTA5CE20",
        "level": 3,
        "parent_level": 2,
    },
    "neighbourhood": {
        "path": "BG/tl_2024_{state_fips}_bg.zip",
        "code_column": "GEOID",
        "name_column": "NAME",
        "level": 4,
        "parent_level": 3,
    },
}


def slugify(parts: list[str]) -> str:
    text = "-".join(part.strip().lower() for part in parts if part and part.strip())
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def source_url_for(level: str, state_fips: str | None = None) -> str:
    config = LEVEL_CONFIG[level]
    return f"{TIGER_BASE_URL}/{config['path'].format(state_fips=state_fips or '36')}"


def load_tiger_frame(source: str | Path) -> gpd.GeoDataFrame:
    frame = gpd.read_file(source)
    if frame.crs is None or frame.crs.to_epsg() != 4326:
        frame = frame.to_crs(epsg=4326)
    return frame


def records_from_frame(level: str, frame: gpd.GeoDataFrame) -> list[dict[str, Any]]:
    config = LEVEL_CONFIG[level]
    records: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        geometry = row.geometry
        if geometry is None:
            continue
        code = str(row.get(config["code_column"]) or "").strip()
        name = str(row.get(config["name_column"]) or code).strip()
        if not code or not name:
            continue
        records.append(
            {
                "name": name,
                "name_local": code,
                "country_code": "US",
                "level": config["level"],
                "geometry_wkt": geometry.wkt,
                "bbox_wkt": geometry.envelope.wkt,
                "area_km2": float(frame.loc[[_]].to_crs(epsg=3857).geometry.area.iloc[0] / 1_000_000),
                "slug": slugify(["us", level, code]),
            }
        )
    return records


async def upsert_records(pool: asyncpg.Pool, records: list[dict[str, Any]]) -> None:
    if not records:
        return
    async with pool.acquire() as conn:
        for record in sorted(records, key=lambda item: (item["level"], item["slug"])):
            await conn.execute(
                """
                INSERT INTO zones (
                    name,
                    name_local,
                    country_code,
                    level,
                    geometry,
                    bbox,
                    area_km2,
                    slug
                ) VALUES (
                    $1,
                    $2,
                    $3,
                    $4,
                    ST_GeomFromText($5, 4326),
                    ST_GeomFromText($6, 4326),
                    $7,
                    $8
                )
                ON CONFLICT (slug) DO UPDATE SET
                    name = EXCLUDED.name,
                    name_local = EXCLUDED.name_local,
                    geometry = EXCLUDED.geometry,
                    bbox = EXCLUDED.bbox,
                    area_km2 = EXCLUDED.area_km2,
                    updated_at = NOW()
                """,
                record["name"],
                record["name_local"],
                record["country_code"],
                record["level"],
                record["geometry_wkt"],
                record["bbox_wkt"],
                record["area_km2"],
                record["slug"],
            )


async def resolve_parents(pool: asyncpg.Pool, child_level: int, parent_level: int) -> None:
    async with pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE zones child
            SET parent_id = parent.id
            FROM zones parent
            WHERE child.country_code = 'US'
              AND parent.country_code = 'US'
              AND child.level = $1
              AND parent.level = $2
              AND ST_Within(ST_Centroid(child.geometry), parent.geometry)
            """,
            child_level,
            parent_level,
        )


async def import_level(
    pool: asyncpg.Pool,
    *,
    level: str,
    source: str | Path,
) -> list[dict[str, Any]]:
    frame = await asyncio.to_thread(load_tiger_frame, source)
    records = await asyncio.to_thread(records_from_frame, level, frame)
    await upsert_records(pool, records)
    parent_level = LEVEL_CONFIG[level]["parent_level"]
    if isinstance(parent_level, int):
        await resolve_parents(pool, LEVEL_CONFIG[level]["level"], parent_level)
    return records


async def main() -> None:
    parser = argparse.ArgumentParser(description="Import US TIGER/Line zones")
    parser.add_argument("--level", nargs="+", required=True, choices=sorted(LEVEL_CONFIG))
    parser.add_argument("--state-fips", default="36")
    parser.add_argument("--database-url", required=True)
    args = parser.parse_args()

    pool = await asyncpg.create_pool(args.database_url, min_size=1, max_size=2)
    try:
        for level in args.level:
            await import_level(
                pool,
                level=level,
                source=source_url_for(level, args.state_fips if args.state_fips != "all" else None),
            )
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
