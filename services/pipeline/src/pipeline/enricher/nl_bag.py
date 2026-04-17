"""Netherlands BAG enricher backed by the PDOK WFS API."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from typing import Any

import httpx
import structlog

try:
    from lxml import etree
except ImportError:  # pragma: no cover
    import xml.etree.ElementTree as etree  # type: ignore[no-redef]

from estategap_common.models import NormalizedListing

from .base import BaseEnricher, EnrichmentResult, register_enricher


LOGGER = structlog.get_logger(__name__)
PDOK_WFS_URL = "https://service.pdok.nl/lv/bag/wfs/v2_0"
NS = {
    "wfs": "http://www.opengis.net/wfs/2.0",
    "bag": "http://bag.geonovum.nl",
    "gml": "http://www.opengis.net/gml/3.2",
}


@register_enricher("NL")
class NetherlandsBAGEnricher(BaseEnricher):
    """Attach official BAG building data to Dutch listings."""

    _semaphore = asyncio.Semaphore(10)

    def __init__(self, *, pool=None, client: httpx.AsyncClient | None = None) -> None:
        del pool
        self._client = client or httpx.AsyncClient(timeout=30.0)
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def enrich(self, listing: NormalizedListing) -> EnrichmentResult:
        if listing.bag_id is None and (listing.address is None or listing.postal_code is None):
            return EnrichmentResult(status="no_match")
        try:
            xml_text = await self._fetch_feature(listing)
            record = _parse_bag_feature(xml_text)
            if record is None:
                return EnrichmentResult(status="no_match")
            updates = {
                "bag_id": record.get("bag_id") or listing.bag_id,
                "year_built": record.get("year_built"),
                "official_area_m2": record.get("official_area_m2"),
                "building_geometry_wkt": record.get("building_geometry_wkt"),
            }
            return EnrichmentResult(
                status="completed",
                updates={key: value for key, value in updates.items() if value is not None},
            )
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("bag_enrichment_failed", listing_id=str(listing.id), error=str(exc))
            return EnrichmentResult(status="failed", error=str(exc))

    async def _fetch_feature(self, listing: NormalizedListing) -> str:
        if listing.bag_id:
            cql = f"identificatie='{listing.bag_id}'"
        else:
            address = str(listing.address or "").replace("'", "''")
            postcode = str(listing.postal_code or "").replace("'", "''")
            cql = f"postcode='{postcode}' AND openbareruimtenaam ILIKE '%{address}%'"
        params = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "GetFeature",
            "typenames": "bag:pand",
            "outputFormat": "application/gml+xml; version=3.2",
            "cql_filter": cql,
        }
        async with self._semaphore:
            response = await self._client.get(PDOK_WFS_URL, params=params)
            response.raise_for_status()
            return response.text


def _parse_bag_feature(xml_text: str) -> dict[str, Any] | None:
    root = etree.fromstring(xml_text.encode())
    members = root.xpath(".//wfs:member", namespaces=NS)
    if not members:
        return None
    member = members[0]
    bag_id = _xpath_text(member, ".//bag:identificatie/text()")
    year_built = _xpath_text(member, ".//bag:bouwjaar/text()")
    area_text = _xpath_text(member, ".//bag:oppervlakte/text()")
    geometry_wkt = _geometry_to_wkt(member)
    return {
        "bag_id": bag_id,
        "year_built": int(year_built) if year_built and year_built.isdigit() else None,
        "official_area_m2": Decimal(str(area_text)) if area_text else None,
        "building_geometry_wkt": geometry_wkt,
    }


def _xpath_text(node: Any, expression: str) -> str | None:
    results = node.xpath(expression, namespaces=NS)
    if not results:
        return None
    text = str(results[0]).strip()
    return text or None


def _geometry_to_wkt(node: Any) -> str | None:
    pos_list = _xpath_text(node, ".//gml:posList/text()")
    if pos_list is None:
        return None
    numbers = [float(value) for value in pos_list.split()]
    if len(numbers) < 6 or len(numbers) % 2 != 0:
        return None
    coords = [f"{numbers[i]} {numbers[i + 1]}" for i in range(0, len(numbers), 2)]
    return f"POLYGON(({', '.join(coords)}))"


__all__ = ["NS", "NetherlandsBAGEnricher", "PDOK_WFS_URL"]
