"""Spain-specific cadastral enrichment via the Catastro INSPIRE WFS."""

from __future__ import annotations

import asyncio
import math
import re
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
import structlog

try:
    from lxml import etree
except ImportError:  # pragma: no cover - fallback for minimal environments
    import xml.etree.ElementTree as etree  # type: ignore[no-redef]

try:
    from shapely.geometry import MultiPolygon, Point, Polygon
except ImportError:  # pragma: no cover - fallback for minimal environments
    MultiPolygon = None  # type: ignore[assignment]
    Point = None  # type: ignore[assignment]
    Polygon = None  # type: ignore[assignment]

from estategap_common.models import NormalizedListing

from ..metrics import ENRICHER_CATASTRO_RATE_LIMIT_ACTIVE, ENRICHER_CATASTRO_REQUESTS_TOTAL
from .base import BaseEnricher, EnrichmentResult, register_enricher


LOGGER = structlog.get_logger(__name__)
CATASTRO_WFS_URL = "http://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx"
POINT_RE = re.compile(r"^POINT\((?P<lon>-?\d+(?:\.\d+)?) (?P<lat>-?\d+(?:\.\d+)?)\)$")
NS = {
    "cp": "http://inspire.jrc.ec.europa.eu/schemas/cp/4.0",
    "base": "http://inspire.jrc.ec.europa.eu/schemas/base/3.3",
    "bu-core2d": "http://inspire.jrc.ec.europa.eu/schemas/bu-core2d/4.0",
    "bu-base": "http://inspire.jrc.ec.europa.eu/schemas/bu-base/4.0",
    "gml": "http://www.opengis.net/gml/3.2",
}


@register_enricher("ES")
class SpainCatastroEnricher(BaseEnricher):
    """Lookup official cadastral fields for a Spanish listing."""

    _rate_limiter = asyncio.Semaphore(1)

    def __init__(
        self,
        *,
        rate_limit: float = 1.0,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._rate_limit = max(rate_limit, 1.0)
        self._client = client or httpx.AsyncClient(timeout=30.0)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def enrich(self, listing: NormalizedListing) -> EnrichmentResult:
        if listing.location_wkt is None:
            return EnrichmentResult(status="no_match")

        try:
            lon, lat = _parse_point(listing.location_wkt)
            response_text = await self._fetch_features(lon, lat)
            features = _extract_feature_records(response_text, lon=lon, lat=lat)
            if not features:
                return EnrichmentResult(status="no_match")
            record = features[0]
            official_area = _decimal_or_none(record.get("official_built_area_m2"))
            portal_area = listing.built_area_m2
            updates: dict[str, object] = {
                "cadastral_ref": record["cadastral_ref"],
                "official_built_area_m2": official_area,
                "building_geometry_wkt": record.get("building_geometry_wkt"),
            }
            year_built = record.get("year_built")
            if listing.year_built is None and year_built is not None:
                updates["year_built"] = year_built
            if official_area is not None and official_area > 0:
                discrepancy = abs(portal_area - official_area) / official_area > Decimal("0.10")
                updates["area_discrepancy_flag"] = discrepancy
            return EnrichmentResult(status="completed", updates=_strip_none_values(updates))
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("catastro_enrichment_failed", listing_id=str(listing.id), error=str(exc))
            return EnrichmentResult(status="failed", error=str(exc))

    async def _fetch_features(self, lon: float, lat: float) -> str:
        bbox = _build_bbox(lon, lat, radius_m=30.0)
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typeNames": "cp:CadastralParcel",
            "srsName": "urn:ogc:def:crs:EPSG::4326",
            "bbox": bbox,
        }
        async with self._rate_limiter:
            ENRICHER_CATASTRO_RATE_LIMIT_ACTIVE.set(1)
            try:
                response = await self._client.get(CATASTRO_WFS_URL, params=params)
                response.raise_for_status()
            except Exception:
                ENRICHER_CATASTRO_REQUESTS_TOTAL.labels(status="error").inc()
                raise
            finally:
                await asyncio.sleep(1.0 / self._rate_limit)
                ENRICHER_CATASTRO_RATE_LIMIT_ACTIVE.set(0)
        ENRICHER_CATASTRO_REQUESTS_TOTAL.labels(status="success").inc()
        return response.text


def _parse_point(value: str) -> tuple[float, float]:
    match = POINT_RE.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"Unsupported POINT WKT {value!r}")
    return float(match.group("lon")), float(match.group("lat"))


def _build_bbox(lon: float, lat: float, *, radius_m: float) -> str:
    lat_delta = radius_m / 111_320.0
    cos_lat = math.cos(math.radians(lat))
    lon_delta = radius_m / (111_320.0 * cos_lat if abs(cos_lat) > 1e-9 else 111_320.0)
    return ",".join(
        (
            str(lon - lon_delta),
            str(lat - lat_delta),
            str(lon + lon_delta),
            str(lat + lat_delta),
            "urn:ogc:def:crs:EPSG::4326",
        )
    )


def _extract_feature_records(xml_text: str, *, lon: float, lat: float) -> list[dict[str, object]]:
    root = etree.fromstring(xml_text.encode())
    features = root.xpath(".//cp:CadastralParcel", namespaces=NS)
    parsed: list[tuple[float, dict[str, object]]] = []
    listing_point = Point(lon, lat) if Point is not None else None
    for feature in features:
        cadastral_ref = _xpath_text(feature, ".//cp:inspireId//base:localId/text()")
        if cadastral_ref is None:
            continue
        geometry_wkt, distance = _geometry_to_wkt(feature, listing_point=listing_point)
        area_value = _xpath_text(feature, ".//cp:areaValue/text()")
        year_text = _xpath_text(feature, ".//bu-base:yearOfConstruction/text()")
        year_built = int(year_text) if year_text and year_text.isdigit() else None
        parsed.append(
            (
                distance,
                {
                    "cadastral_ref": cadastral_ref,
                    "official_built_area_m2": _decimal_or_none(area_value),
                    "year_built": year_built,
                    "building_geometry_wkt": geometry_wkt,
                },
            )
        )
    parsed.sort(key=lambda item: item[0])
    return [item[1] for item in parsed]


def _xpath_text(node: Any, expression: str) -> str | None:
    results = node.xpath(expression, namespaces=NS)
    if not results:
        return None
    value = results[0]
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    text = str(value).strip()
    return text or None


def _geometry_to_wkt(node: Any, *, listing_point: Any) -> tuple[str | None, float]:
    pos_lists = node.xpath(".//cp:geometry//gml:posList/text()", namespaces=NS)
    if not pos_lists or Polygon is None:
        return None, float("inf")
    polygons: list[Any] = []
    for pos_list in pos_lists:
        coordinates = _parse_pos_list(pos_list)
        if len(coordinates) < 3:
            continue
        polygon = Polygon(coordinates)
        if not polygon.is_valid:
            polygon = polygon.buffer(0)
        polygons.append(polygon)
    if not polygons:
        return None, float("inf")
    geometry = polygons[0] if len(polygons) == 1 else MultiPolygon(polygons)
    distance = geometry.centroid.distance(listing_point) if listing_point is not None else float("inf")
    return geometry.wkt, distance


def _parse_pos_list(value: str) -> list[tuple[float, float]]:
    numbers = [float(part) for part in value.split()]
    if len(numbers) % 2 != 0:
        raise ValueError("Invalid GML posList length")
    return [(numbers[index], numbers[index + 1]) for index in range(0, len(numbers), 2)]


def _decimal_or_none(value: object) -> Decimal | None:
    if value in {None, ""}:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _strip_none_values(payload: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in payload.items() if value is not None}


__all__ = ["NS", "SpainCatastroEnricher"]
