"""France DVF transaction enricher."""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

import asyncpg  # type: ignore[import-untyped]
import structlog

from estategap_common.models import NormalizedListing

from .base import BaseEnricher, EnrichmentResult, register_enricher


LOGGER = structlog.get_logger(__name__)
POINT_RE = re.compile(r"^POINT\((?P<lon>-?\d+(?:\.\d+)?) (?P<lat>-?\d+(?:\.\d+)?)\)$")


@register_enricher("FR")
class FranceDVFEnricher(BaseEnricher):
    """Enrich French listings with nearby transaction medians."""

    def __init__(self, *, pool: asyncpg.Pool | None = None) -> None:
        self._pool = pool

    async def enrich(self, listing: NormalizedListing) -> EnrichmentResult:
        if listing.location_wkt is None or self._pool is None:
            return EnrichmentResult(status="no_match")
        try:
            lon, lat = _parse_point(listing.location_wkt)
            rows = await self._fetch_rows(lon=lon, lat=lat)
            rows = _filter_rows_by_property_type(rows, listing.property_type)
            if not rows:
                return EnrichmentResult(status="no_match", updates={"dvf_nearby_count": 0})
            median_price = _median_price_m2(rows)
            updates: dict[str, object] = {"dvf_nearby_count": len(rows)}
            if median_price is not None:
                updates["dvf_median_price_m2"] = median_price
            return EnrichmentResult(status="completed", updates=updates)
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("dvf_enrichment_failed", listing_id=str(listing.id), error=str(exc))
            return EnrichmentResult(status="failed", error=str(exc))

    async def _fetch_rows(self, *, lon: float, lat: float) -> list[dict[str, object]]:
        if self._pool is None:
            return []
        async with self._pool.acquire() as conn:
            records = await conn.fetch(
                """
                SELECT date_mutation, valeur_fonciere, surface_reelle_bati, type_local
                FROM dvf_transactions
                WHERE geom IS NOT NULL
                  AND ST_DWithin(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint($1, $2), 4326)::geography,
                    200
                  )
                ORDER BY date_mutation DESC
                LIMIT 10
                """,
                lon,
                lat,
            )
        return [dict(record) for record in records]


def _parse_point(value: str) -> tuple[float, float]:
    match = POINT_RE.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"Unsupported point value {value!r}")
    return float(match.group("lon")), float(match.group("lat"))


def _filter_rows_by_property_type(
    rows: list[dict[str, object]],
    property_type: str | None,
) -> list[dict[str, object]]:
    if property_type is None:
        return rows[:5]
    allowed = {
        "residential": {"appartement", "maison"},
        "commercial": {"local", "bureau", "dépendance"},
        "industrial": {"dépendance", "atelier"},
        "land": {"terrain"},
    }.get(property_type, set())
    if not allowed:
        return rows[:5]
    filtered = [
        row
        for row in rows
        if str(row.get("type_local", "")).strip().lower() in allowed
    ]
    return filtered[:5]


def _median_price_m2(rows: list[dict[str, object]]) -> Decimal | None:
    prices: list[Decimal] = []
    for row in rows:
        price = row.get("valeur_fonciere")
        surface = row.get("surface_reelle_bati")
        if price in {None, ""} or surface in {None, "", 0}:
            continue
        prices.append((Decimal(str(price)) / Decimal(str(surface))).quantize(Decimal("0.01")))
    if not prices:
        return None
    prices.sort()
    middle = len(prices) // 2
    if len(prices) % 2:
        return prices[middle]
    return ((prices[middle - 1] + prices[middle]) / Decimal("2")).quantize(Decimal("0.01"))


__all__ = ["FranceDVFEnricher"]
