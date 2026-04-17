"""Zone statistics loading helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

import asyncpg


@dataclass(slots=True)
class ZoneStats:
    """Spatial aggregates used by the feature engineer."""

    zone_id: UUID | None
    median_price_m2: float
    listing_density: int
    avg_income: float | None = None


@dataclass(slots=True)
class ZoneStatsSnapshot:
    """All fallback layers required by the feature engineer."""

    zone_stats: dict[UUID, ZoneStats]
    city_stats: dict[str, ZoneStats]
    country_stats: ZoneStats


def _to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    return float(value)


async def fetch_zone_stats(country: str, dsn: str) -> ZoneStatsSnapshot:
    """Load zone, city, and country fallback statistics for one country."""

    country_code = country.upper()
    conn = await asyncpg.connect(dsn)
    try:
        zone_rows = await conn.fetch(
            """
            SELECT
                z.id AS zone_id,
                COALESCE(zs.median_price_m2_eur, 0) AS median_price_m2,
                COALESCE(zs.active_listings, zs.listing_count, 0) AS listing_density
            FROM zones z
            LEFT JOIN zone_statistics zs ON zs.zone_id = z.id
            WHERE z.country_code = $1
            """,
            country_code,
        )
        city_rows = await conn.fetch(
            """
            SELECT
                LOWER(COALESCE(city, 'unknown')) AS city_key,
                COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price_per_m2_eur), 0) AS median_price_m2,
                COUNT(*)::INTEGER AS listing_density
            FROM listings
            WHERE country = $1
              AND city IS NOT NULL
              AND price_per_m2_eur IS NOT NULL
            GROUP BY LOWER(city)
            """,
            country_code,
        )
        country_row = await conn.fetchrow(
            """
            SELECT
                COALESCE(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY price_per_m2_eur), 0) AS median_price_m2,
                COUNT(*)::INTEGER AS listing_density
            FROM listings
            WHERE country = $1
              AND price_per_m2_eur IS NOT NULL
            """,
            country_code,
        )
    finally:
        await conn.close()

    zone_stats = {
        row["zone_id"]: ZoneStats(
            zone_id=row["zone_id"],
            median_price_m2=_to_float(row["median_price_m2"]),
            listing_density=int(row["listing_density"] or 0),
            avg_income=None,
        )
        for row in zone_rows
        if row["zone_id"] is not None
    }
    city_stats = {
        row["city_key"]: ZoneStats(
            zone_id=None,
            median_price_m2=_to_float(row["median_price_m2"]),
            listing_density=int(row["listing_density"] or 0),
            avg_income=None,
        )
        for row in city_rows
    }
    country_stats = ZoneStats(
        zone_id=None,
        median_price_m2=_to_float(country_row["median_price_m2"] if country_row else 0),
        listing_density=int(country_row["listing_density"] if country_row else 0),
        avg_income=None,
    )
    return ZoneStatsSnapshot(
        zone_stats=zone_stats,
        city_stats=city_stats,
        country_stats=country_stats,
    )
