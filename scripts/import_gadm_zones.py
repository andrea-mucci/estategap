"""Import GADM administrative boundaries into the shared zones table."""

from __future__ import annotations

import argparse
import asyncio
import re
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import asyncpg  # type: ignore[import-untyped]
import geopandas as gpd


LEVEL_MAP = {
    "IT": ("NAME_0", "NAME_1", "NAME_2", "NAME_3"),
    "FR": ("NAME_0", "NAME_1", "NAME_2", "NAME_3"),
    "GB": ("NAME_0", "NAME_1", "NAME_2", "NAME_3"),
    "NL": ("NAME_0", "NAME_1", "NAME_2"),
}
COUNTRY_USES_PIECES = {"FR": True, "IT": False, "GB": False, "NL": False}


def slugify(parts: Iterable[str]) -> str:
    text = "-".join(part.strip().lower() for part in parts if part and part.strip())
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def load_gadm_records(country: str, file_path: Path) -> list[dict[str, Any]]:
    frame = gpd.read_file(file_path)
    if frame.crs is None or frame.crs.to_epsg() != 4326:
        frame = frame.to_crs(epsg=4326)
    level_columns = LEVEL_MAP[country]
    records: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        geometry = row.geometry
        if geometry is None:
            continue
        names = [str(row.get(column) or "").strip() for column in level_columns]
        country_name = names[0] or country
        for level, name in enumerate(names):
            if not name:
                continue
            path = [country, *names[1 : level + 1]]
            records.append(
                {
                    "country_code": country,
                    "level": level,
                    "name": name if level > 0 else country_name,
                    "slug": slugify(path or [country, name]),
                    "parent_slug": slugify([country, *names[1:level]]) if level > 0 else None,
                    "geometry_wkt": geometry.wkt,
                    "bbox_wkt": geometry.envelope.wkt,
                    "area_km2": float(frame.loc[[_]].to_crs(epsg=3035).geometry.area.iloc[0] / 1_000_000),
                }
            )
    unique_by_slug: dict[str, dict[str, Any]] = {}
    for record in records:
        unique_by_slug.setdefault(record["slug"], record)
    return list(unique_by_slug.values())


async def import_gadm_records(pool: asyncpg.Pool, records: list[dict[str, Any]]) -> None:
    if not records:
        return
    async with pool.acquire() as conn:
        slug_to_id: dict[str, object] = {}
        ordered = sorted(records, key=lambda item: (item["level"], item["slug"]))
        for record in ordered:
            parent_id = slug_to_id.get(record["parent_slug"])
            row = await conn.fetchrow(
                """
                INSERT INTO zones (
                    name,
                    country_code,
                    level,
                    parent_id,
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
                    parent_id = EXCLUDED.parent_id,
                    geometry = EXCLUDED.geometry,
                    bbox = EXCLUDED.bbox,
                    area_km2 = EXCLUDED.area_km2,
                    updated_at = NOW()
                RETURNING id
                """,
                record["name"],
                record["country_code"],
                record["level"],
                parent_id,
                record["geometry_wkt"],
                record["bbox_wkt"],
                record["area_km2"],
                record["slug"],
            )
            slug_to_id[record["slug"]] = row["id"]


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--database-url", required=True)
    parser.add_argument("--country", required=True, choices=sorted(LEVEL_MAP))
    parser.add_argument("--file", required=True)
    args = parser.parse_args()

    pool = await asyncpg.create_pool(args.database_url, min_size=1, max_size=2)
    try:
        records = load_gadm_records(args.country, Path(args.file))
        await import_gadm_records(pool, records)
    finally:
        await pool.close()


if __name__ == "__main__":
    asyncio.run(main())
