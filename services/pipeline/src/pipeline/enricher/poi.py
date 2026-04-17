"""POI distance lookup using PostGIS with an Overpass fallback."""

from __future__ import annotations

import math
import re
from typing import Any

import asyncpg  # type: ignore[import-untyped]
import httpx

try:
    from cachetools import TTLCache
except ImportError:  # pragma: no cover - fallback for minimal environments
    TTLCache = None  # type: ignore[assignment]

from estategap_common.models import NormalizedListing


POINT_RE = re.compile(r"^POINT\((?P<lon>-?\d+(?:\.\d+)?) (?P<lat>-?\d+(?:\.\d+)?)\)$")
POI_CATEGORY_FIELDS: dict[str, str] = {
    "metro": "dist_metro_m",
    "train": "dist_train_m",
    "airport": "dist_airport_m",
    "park": "dist_park_m",
    "beach": "dist_beach_m",
}
OVERPASS_SELECTORS: dict[str, str] = {
    "metro": '(node["amenity"="subway_entrance"](around:5000,{lat},{lon});node["railway"="subway_station"](around:5000,{lat},{lon}););',
    "train": 'node["railway"="station"](around:5000,{lat},{lon});',
    "airport": 'node["aeroway"="aerodrome"](around:5000,{lat},{lon});',
    "park": 'node["leisure"="park"](around:5000,{lat},{lon});',
    "beach": 'node["natural"="beach"](around:5000,{lat},{lon});',
}

DISTANCE_SQL = """
SELECT
    ST_Distance(ST_GeomFromText($1, 4326)::geography, location::geography)::int AS dist_m
FROM pois
WHERE country = $2
  AND category = $3
ORDER BY location <-> ST_GeomFromText($1, 4326)
LIMIT 1
"""


class POIDistanceCalculator:
    """Resolve nearest-category distances for a listing."""

    def __init__(
        self,
        *,
        pool: asyncpg.Pool,
        overpass_url: str,
        overpass_cache: Any | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._pool = pool
        self._overpass_url = overpass_url
        self._cache = overpass_cache or _build_cache()
        self._client = client or httpx.AsyncClient(timeout=30.0)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def calculate(self, listing: NormalizedListing) -> dict[str, int | None]:
        defaults = {field_name: None for field_name in POI_CATEGORY_FIELDS.values()}
        if listing.location_wkt is None:
            return defaults

        lon, lat = _parse_point(listing.location_wkt)
        results: dict[str, int | None] = {}
        async with self._pool.acquire() as conn:
            for category, field_name in POI_CATEGORY_FIELDS.items():
                row = await conn.fetchrow(DISTANCE_SQL, listing.location_wkt, listing.country, category)
                if row is not None and row["dist_m"] is not None:
                    results[field_name] = int(row["dist_m"])
                    continue
                results[field_name] = await self._overpass_fallback(lat, lon, category)
        return results

    async def _overpass_fallback(self, lat: float, lon: float, category: str) -> int | None:
        cache_key = (round(lat, 3), round(lon, 3), category)
        cached = self._cache.get(cache_key)
        if cached is not None or cache_key in self._cache:
            return cached

        selector = OVERPASS_SELECTORS[category].format(lat=lat, lon=lon)
        query = f"[out:json];{selector}out center;"
        try:
            response = await self._client.post(self._overpass_url, content=query)
            response.raise_for_status()
            payload = response.json()
            nearest = min(
                (
                    _haversine_m(lat, lon, point_lat, point_lon)
                    for point_lat, point_lon in _iter_overpass_points(payload)
                ),
                default=None,
            )
        except Exception:  # noqa: BLE001
            nearest = None
        self._cache[cache_key] = nearest
        return nearest


def _parse_point(value: str) -> tuple[float, float]:
    match = POINT_RE.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"Unsupported POINT WKT {value!r}")
    return float(match.group("lon")), float(match.group("lat"))


def _iter_overpass_points(payload: dict[str, Any]) -> list[tuple[float, float]]:
    points: list[tuple[float, float]] = []
    for element in payload.get("elements", []):
        if "lat" in element and "lon" in element:
            points.append((float(element["lat"]), float(element["lon"])))
            continue
        center = element.get("center")
        if isinstance(center, dict) and "lat" in center and "lon" in center:
            points.append((float(center["lat"]), float(center["lon"])))
    return points


def _build_cache() -> Any:
    if TTLCache is None:
        return {}
    return TTLCache(maxsize=1024, ttl=300)


def _haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    radius_m = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(delta_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return int(radius_m * c)


__all__ = ["POIDistanceCalculator"]
