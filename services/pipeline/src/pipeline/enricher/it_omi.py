"""Italy OMI zone enricher."""

from __future__ import annotations

import re
from decimal import Decimal

import asyncpg  # type: ignore[import-untyped]
import structlog

from estategap_common.models import NormalizedListing

from .base import BaseEnricher, EnrichmentResult, register_enricher


LOGGER = structlog.get_logger(__name__)
POINT_RE = re.compile(r"^POINT\((?P<lon>-?\d+(?:\.\d+)?) (?P<lat>-?\d+(?:\.\d+)?)\)$")
OMI_TYPE_MAP = {
    "residential": {"abitazioni civili", "ville e villini", "abitazioni di tipo economico"},
    "commercial": {"negozi", "uffici"},
    "industrial": {"capannoni industriali"},
    "land": {"terreni edificabili"},
}


@register_enricher("IT")
class ItalyOMIEnricher(BaseEnricher):
    """Attach OMI price bands to Italian listings."""

    def __init__(self, *, pool: asyncpg.Pool | None = None) -> None:
        self._pool = pool

    async def enrich(self, listing: NormalizedListing) -> EnrichmentResult:
        if self._pool is None or listing.location_wkt is None:
            return EnrichmentResult(status="no_match")
        try:
            lon, lat = _parse_point(listing.location_wkt)
            tipologie = tuple(sorted(OMI_TYPE_MAP.get(listing.property_type or "", ())))
            async with self._pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT zona_omi, period, price_min, price_max
                    FROM omi_zones
                    WHERE geometry IS NOT NULL
                      AND ST_Within(
                        ST_SetSRID(ST_MakePoint($1, $2), 4326),
                        geometry
                      )
                      AND ($3::text[] IS NULL OR lower(tipologia) = ANY($3::text[]))
                    ORDER BY period DESC
                    LIMIT 1
                    """,
                    lon,
                    lat,
                    list(tipologie) if tipologie else None,
                )
            if row is None:
                return EnrichmentResult(status="no_match")
            price_min = _decimal(row["price_min"])
            price_max = _decimal(row["price_max"])
            updates: dict[str, object] = {
                "omi_zone_code": row["zona_omi"],
                "omi_price_min_eur_m2": price_min,
                "omi_price_max_eur_m2": price_max,
                "omi_period": row["period"],
            }
            if price_min is not None and price_max is not None and listing.built_area_m2 > 0:
                midpoint = (price_min + price_max) / Decimal("2")
                if midpoint > 0:
                    listing_price_m2 = listing.asking_price_eur / listing.built_area_m2
                    updates["price_vs_omi"] = (listing_price_m2 / midpoint).quantize(Decimal("0.0001"))
            return EnrichmentResult(status="completed", updates=updates)
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("omi_enrichment_failed", listing_id=str(listing.id), error=str(exc))
            return EnrichmentResult(status="failed", error=str(exc))


def _parse_point(value: str) -> tuple[float, float]:
    match = POINT_RE.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"Unsupported point value {value!r}")
    return float(match.group("lon")), float(match.group("lat"))


def _decimal(value: object) -> Decimal | None:
    if value in {None, ""}:
        return None
    return Decimal(str(value))


__all__ = ["ItalyOMIEnricher", "OMI_TYPE_MAP"]
