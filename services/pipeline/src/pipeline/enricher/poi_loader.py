"""Load OSM POIs into PostGIS for enrichment queries."""

from __future__ import annotations

import argparse
import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import asyncpg  # type: ignore[import-untyped]


INSERT_SQL = """
INSERT INTO pois (osm_id, country, category, name, location)
VALUES ($1, $2, $3, $4, ST_GeomFromText($5, 4326))
"""
CHUNK_SIZE = 500


@dataclass(slots=True)
class POIRow:
    osm_id: int
    country: str
    category: str
    name: str | None
    location_wkt: str


class _POIHandler:
    def __init__(self, country: str) -> None:
        self.country = country
        self.rows: list[POIRow] = []

    def node(self, node: Any) -> None:
        category = _classify_tags(getattr(node, "tags", {}))
        location = getattr(node, "location", None)
        if category is None or location is None or not location.valid():
            return
        name = node.tags.get("name") if "name" in node.tags else None
        self.rows.append(
            POIRow(
                osm_id=int(node.id),
                country=self.country,
                category=category,
                name=name,
                location_wkt=f"POINT({location.lon} {location.lat})",
            )
        )


async def _insert_rows(database_url: str, rows: list[POIRow]) -> None:
    pool = await asyncpg.create_pool(database_url, min_size=1, max_size=2, command_timeout=30)
    try:
        for start in range(0, len(rows), CHUNK_SIZE):
            batch = rows[start : start + CHUNK_SIZE]
            async with pool.acquire() as conn:
                await conn.executemany(
                    INSERT_SQL,
                    [
                        (row.osm_id, row.country, row.category, row.name, row.location_wkt)
                        for row in batch
                    ],
                )
            if (start + len(batch)) % 10_000 == 0:
                print(f"inserted={start + len(batch)}")
    finally:
        await pool.close()


def _classify_tags(tags: Any) -> str | None:
    amenity = tags.get("amenity")
    railway = tags.get("railway")
    aeroway = tags.get("aeroway")
    leisure = tags.get("leisure")
    natural = tags.get("natural")
    if amenity == "subway_entrance" or railway == "subway_station":
        return "metro"
    if railway == "station":
        return "train"
    if aeroway == "aerodrome":
        return "airport"
    if leisure == "park":
        return "park"
    if natural == "beach":
        return "beach"
    return None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Load OSM POIs into PostGIS")
    parser.add_argument("--pbf", required=True, type=Path)
    parser.add_argument("--country", required=True)
    parser.add_argument("--database-url", required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    try:
        import osmium
    except ImportError as exc:  # pragma: no cover - depends on optional runtime dependency
        raise SystemExit(f"pyosmium is required for poi_loader: {exc}") from exc

    handler = _POIHandler(country=args.country.upper())

    class Loader(osmium.SimpleHandler):  # type: ignore[misc, valid-type]
        def node(self, node: Any) -> None:
            handler.node(node)

    loader = Loader()
    loader.apply_file(str(args.pbf), locations=True)
    asyncio.run(_insert_rows(args.database_url, handler.rows))
    print(f"loaded={len(handler.rows)}")


if __name__ == "__main__":
    main()
