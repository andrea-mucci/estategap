"""Fotocasa Spain spider implementation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from parsel import Selector

from estategap_common.models.listing import RawListing

from ..browser import fetch_with_browser
from ..http_client import ParseError, PermanentFailureError
from .base import BaseSpider


def _now() -> datetime:
    return datetime.now(UTC)


def _price_to_cents(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, dict):
        value = value.get("amount")
    return int(float(value) * 100)


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    return float(value)


def _as_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _default_search_url(search_url: str) -> str:
    return search_url or "https://www.fotocasa.es/es/comprar/vivienda/madrid-capital/todas-las-zonas/l"


class FotocasaSpider(BaseSpider):
    """Portal spider for Fotocasa Spain."""

    COUNTRY = "ES"
    PORTAL = "fotocasa"

    def _extract_next_data(self, html: str) -> dict[str, Any]:
        payload = Selector(html).css("script#__NEXT_DATA__::text").get()
        if not payload:
            raise ParseError("missing __NEXT_DATA__ payload")
        try:
            return json.loads(payload)
        except json.JSONDecodeError as exc:
            raise ParseError("invalid __NEXT_DATA__ payload") from exc

    def _map_listing(self, raw: dict[str, Any], zone: str) -> RawListing:
        multimedia = raw.get("multimedia", {})
        listing_url = raw.get("detailUrl") or raw.get("url")
        listing_url = urljoin("https://www.fotocasa.es", listing_url or "")
        external_id = str(raw.get("id") or raw.get("propertyId") or listing_url.rstrip("/").rsplit("/", 1)[-1])
        return RawListing(
            external_id=external_id,
            portal=self.PORTAL,
            country_code=self.COUNTRY,
            raw_json={
                "price": _price_to_cents(raw.get("price")),
                "currency": "EUR",
                "area_m2": _as_float(raw.get("surface")),
                "usable_area_m2": _as_float(raw.get("usableSurface")),
                "rooms": _as_int(raw.get("rooms")),
                "bathrooms": _as_int(raw.get("bathrooms")),
                "floor": _as_int(raw.get("floor")),
                "total_floors": _as_int(raw.get("totalFloors")),
                "has_elevator": raw.get("hasLift"),
                "has_parking": raw.get("hasParking"),
                "parking_spaces": _as_int(raw.get("parkingSpaces")),
                "has_terrace": raw.get("hasTerrace"),
                "terrace_area_m2": _as_float(raw.get("terraceSurface")),
                "orientation": raw.get("orientation"),
                "condition": raw.get("condition"),
                "year_built": _as_int(raw.get("constructionYear")),
                "energy_cert": raw.get("energyCertificate", {}).get("energyRating"),
                "energy_kwh": raw.get("energyCertificate", {}).get("energyConsumption"),
                "latitude": raw.get("ubication", {}).get("latitude"),
                "longitude": raw.get("ubication", {}).get("longitude"),
                "photos": [image.get("url") for image in multimedia.get("images", []) if image.get("url")],
                "description": raw.get("description"),
                "agent_name": raw.get("agency", {}).get("name"),
                "agent_id": raw.get("agency", {}).get("id"),
                "listing_url": listing_url,
                "zone_id": zone,
                "listing_type": raw.get("transactionType") or "sale",
                "property_type": raw.get("propertyType") or "residential",
            },
            scraped_at=_now(),
        )

    async def _fetch_html_page(self, url: str) -> str:
        client = await self._ensure_http_client()
        response = await client.get(url)
        if client.is_blocked(response):
            return await fetch_with_browser(url, self.proxy_url)
        if response.status_code >= 400:
            raise PermanentFailureError(f"Fotocasa HTML returned {response.status_code}")
        return response.text

    async def scrape_search_page(self, zone: str, page: int) -> list[RawListing]:
        html = await self._fetch_html_page(self._search_url(page))
        data = self._extract_next_data(html)
        page_props = data.get("props", {}).get("pageProps", {})
        initial_props = page_props.get("initialProps", {})
        listings = initial_props.get("listings") or page_props.get("listings") or []
        total_pages = page_props.get("totalPages") or initial_props.get("totalPages") or 0
        if total_pages and page > int(total_pages):
            return []
        return [self._map_listing(item, zone) for item in listings]

    async def scrape_listing_detail(self, url: str) -> RawListing | None:
        html = await self._fetch_html_page(url)
        data = self._extract_next_data(html)
        page_props = data.get("props", {}).get("pageProps", {})
        real_estate = page_props.get("realEstate") or page_props.get("initialProps", {}).get("realEstate")
        if not isinstance(real_estate, dict):
            raise ParseError("missing realEstate payload")
        listing = self._map_listing(real_estate, "")
        listing.raw_json["listing_url"] = url
        return listing

    async def detect_new_listings(self, zone: str, since_ids: set[str]) -> list[str]:
        del since_ids
        url_by_id: dict[str, str] = {}
        for page in range(1, 4):
            html = await self._fetch_html_page(self._search_url(page, newest=True))
            data = self._extract_next_data(html)
            page_props = data.get("props", {}).get("pageProps", {})
            initial_props = page_props.get("initialProps", {})
            listings = initial_props.get("listings") or page_props.get("listings") or []
            for item in listings:
                listing = self._map_listing(item, zone)
                url_by_id[listing.external_id] = listing.raw_json["listing_url"]
        new_ids = await self._filter_new(self.redis, zone, set(url_by_id))
        return [url_by_id[listing_id] for listing_id in sorted(new_ids)]

    def _search_url(self, page: int, *, newest: bool = False) -> str:
        parsed = urlparse(_default_search_url(self.search_url))
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["page"] = str(page)
        if newest:
            query["sortType"] = "publicationDate"
            query["sortDirection"] = "desc"
        return urlunparse(parsed._replace(query=urlencode(query)))
