"""Idealista Spain spider implementation."""

from __future__ import annotations

import json
import re
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


def _extract_number(value: str | None) -> int | None:
    if not value:
        return None
    match = re.search(r"-?\d+", value.replace(".", "").replace(",", ""))
    return int(match.group()) if match else None


def _extract_float(value: str | None) -> float | None:
    if not value:
        return None
    cleaned = value.lower().replace("m²", "").replace("€", "")
    cleaned = re.sub(r"[^0-9,.\-]", "", cleaned)
    if not cleaned:
        return None
    if cleaned.count(",") == 1 and cleaned.count(".") > 1:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned and "." not in cleaned:
        cleaned = cleaned.replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _price_to_cents(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, str):
        numeric = _extract_float(value)
        return int(numeric * 100) if numeric is not None else None
    return int(float(value) * 100)


def _external_id_from_url(url: str) -> str:
    match = re.search(r"/(\d+)/?", url)
    return match.group(1) if match else url.rstrip("/").rsplit("/", 1)[-1]


def _base_search_url(search_url: str) -> str:
    return search_url or "https://www.idealista.com/venta-viviendas/madrid/"


class IdealistaSpider(BaseSpider):
    """Portal spider for Idealista Spain."""

    COUNTRY = "ES"
    PORTAL = "idealista"
    API_URL = "https://api.idealista.com/3.5/es/search"

    def __init__(self, config) -> None:
        super().__init__(config)
        self._api_token = config.idealista_api_token
        self._session_rotation_count = 0

    async def _fetch_api_page(
        self,
        zone: str,
        page: int,
        extra_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self._api_token:
            return {}
        client = await self._ensure_http_client(
            force_rotate=bool(self._session_rotation_count and self._session_rotation_count % self.config.session_rotation_every == 0),
        )
        self._session_rotation_count += 1
        payload: dict[str, Any] = {
            "numPage": page,
            "maxItems": 50,
            "zone": zone,
        }
        if extra_payload:
            payload.update(extra_payload)
        response = await client.post(
            self.API_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {self._api_token}",
                "User-Agent": "idealista/8.0.0 (Android 13)",
            },
        )
        if response.status_code in {401, 403}:
            self._api_token = ""
            return {}
        if response.status_code >= 400:
            raise PermanentFailureError(f"Idealista API returned {response.status_code}")
        return response.json()

    def _map_api_response(self, element: dict[str, Any], zone: str) -> RawListing:
        photos = [
            image.get("url")
            for image in element.get("multimedia", {}).get("images", [])
            if image.get("url")
        ]
        parking = element.get("parkingSpace", {})
        listing_url = element.get("url") or element.get("link")
        listing_url = urljoin("https://www.idealista.com", listing_url or "")
        external_id = str(
            element.get("propertyCode")
            or element.get("code")
            or _external_id_from_url(listing_url)
        )
        raw_json = {
            "price": _price_to_cents(element.get("price")),
            "currency": element.get("currency") or "EUR",
            "area_m2": _extract_float(str(element.get("size", ""))),
            "usable_area_m2": _extract_float(str(element.get("usableArea", ""))),
            "rooms": element.get("rooms"),
            "bathrooms": element.get("bathrooms"),
            "floor": _extract_number(str(element.get("floor"))),
            "total_floors": _extract_number(str(element.get("totalFloors"))),
            "has_elevator": element.get("hasLift"),
            "has_parking": parking.get("hasParkingSpace"),
            "parking_spaces": parking.get("parkingSpaceCount"),
            "has_terrace": element.get("hasTerrace"),
            "terrace_area_m2": _extract_float(str(element.get("terraceArea", ""))),
            "orientation": element.get("orientation"),
            "condition": element.get("status"),
            "year_built": element.get("constructionYear"),
            "energy_cert": (
                element.get("energyCertification", {})
                .get("energyConsumption", {})
                .get("rating")
            ),
            "energy_kwh": (
                element.get("energyCertification", {})
                .get("energyConsumption", {})
                .get("value")
            ),
            "latitude": element.get("latitude"),
            "longitude": element.get("longitude"),
            "photos": photos,
            "description": element.get("description"),
            "agent_name": element.get("contact", {}).get("agency", {}).get("name"),
            "agent_id": element.get("contact", {}).get("agency", {}).get("id"),
            "listing_url": listing_url,
            "zone_id": zone,
            "listing_type": element.get("operation") or "sale",
            "property_type": element.get("propertyType") or "residential",
            "context": element.get("suggestedTexts", {}).get("title"),
        }
        return RawListing(
            external_id=external_id,
            portal=self.PORTAL,
            country_code=self.COUNTRY,
            raw_json=raw_json,
            scraped_at=_now(),
        )

    async def _fetch_html_page(self, url: str) -> str:
        client = await self._ensure_http_client()
        response = await client.get(url)
        if client.is_blocked(response):
            return await fetch_with_browser(url, self.proxy_url)
        if response.status_code >= 400:
            raise PermanentFailureError(f"Idealista HTML returned {response.status_code}")
        return response.text

    def _parse_search_html(self, html: str, zone: str) -> list[RawListing]:
        selector = Selector(html)
        cards = selector.css(".item-info-container")
        if not cards:
            cards = selector.css("article.item")
        listings: list[RawListing] = []
        for card in cards:
            href = card.css("a.item-link::attr(href), a::attr(href)").get()
            if not href:
                continue
            listing_url = urljoin("https://www.idealista.com", href)
            listings.append(
                RawListing(
                    external_id=_external_id_from_url(listing_url),
                    portal=self.PORTAL,
                    country_code=self.COUNTRY,
                    raw_json={
                        "listing_url": listing_url,
                        "zone_id": zone,
                        "price": _price_to_cents(card.css(".item-price::text").get()),
                        "area_m2": _extract_float(" ".join(card.css(".item-detail-char::text").getall())),
                        "currency": "EUR",
                        "photos": [],
                        "listing_type": "sale",
                        "property_type": "residential",
                    },
                    scraped_at=_now(),
                ),
            )
        return listings

    def _parse_detail_html(self, html: str, url: str) -> RawListing:
        selector = Selector(html)
        description = " ".join(part.strip() for part in selector.css(".comment p::text, .adCommentsLanguage::text").getall() if part.strip()) or None
        feature_texts = [
            part.strip()
            for part in selector.css(".info-features span::text, .details-property_features span::text").getall()
            if part.strip()
        ]
        area = rooms = bathrooms = floor = None
        for feature in feature_texts:
            lower = feature.lower()
            if "m²" in lower and area is None:
                area = _extract_float(feature)
            elif ("hab" in lower or "room" in lower) and rooms is None:
                rooms = _extract_number(feature)
            elif "bañ" in lower and bathrooms is None:
                bathrooms = _extract_number(feature)
            elif "planta" in lower and floor is None:
                floor = _extract_number(feature)

        json_ld_blocks = selector.css('script[type="application/ld+json"]::text').getall()
        latitude = longitude = None
        for block in json_ld_blocks:
            try:
                data = json.loads(block)
            except json.JSONDecodeError:
                continue
            geo = data.get("geo") if isinstance(data, dict) else None
            if isinstance(geo, dict):
                latitude = geo.get("latitude")
                longitude = geo.get("longitude")
                break

        photos = selector.css('img[src*="idealista.com"]::attr(src), img::attr(src)').getall()
        price_text = " ".join(
            part.strip()
            for part in selector.css(".price-features__container *::text, .info-data-price *::text").getall()
            if part.strip()
        )
        title = selector.css("meta[property='og:title']::attr(content), title::text").get()
        agent_name = selector.css(".professional-name::text, .about-advertiser-name::text").get()

        return RawListing(
            external_id=_external_id_from_url(url),
            portal=self.PORTAL,
            country_code=self.COUNTRY,
            raw_json={
                "price": _price_to_cents(price_text),
                "currency": "EUR",
                "area_m2": area,
                "usable_area_m2": None,
                "rooms": rooms,
                "bathrooms": bathrooms,
                "floor": floor,
                "total_floors": None,
                "has_elevator": None,
                "has_parking": None,
                "parking_spaces": None,
                "has_terrace": None,
                "terrace_area_m2": None,
                "orientation": None,
                "condition": None,
                "year_built": None,
                "energy_cert": None,
                "energy_kwh": None,
                "latitude": latitude,
                "longitude": longitude,
                "photos": photos,
                "description": description,
                "agent_name": agent_name.strip() if agent_name else None,
                "agent_id": None,
                "listing_url": url,
                "zone_id": "",
                "listing_type": "sale",
                "property_type": "residential",
                "context": title.strip() if title else None,
            },
            scraped_at=_now(),
        )

    async def scrape_listing_detail(self, url: str) -> RawListing | None:
        html = await self._fetch_html_page(url)
        return self._parse_detail_html(html, url)

    async def scrape_search_page(self, zone: str, page: int) -> list[RawListing]:
        api_payload = await self._fetch_api_page(zone, page)
        elements = api_payload.get("elementList")
        if isinstance(elements, list):
            if not elements:
                return []
            return [self._map_api_response(element, zone) for element in elements]

        html = await self._fetch_html_page(self._search_url(page))
        listings = self._parse_search_html(html, zone)
        if not listings:
            return []
        detailed_listings: list[RawListing] = []
        for listing in listings:
            detail = await self.scrape_listing_detail(listing.raw_json["listing_url"])
            if detail is None:
                detailed_listings.append(listing)
                continue
            detail.raw_json["zone_id"] = zone
            detailed_listings.append(detail)
        return detailed_listings

    async def detect_new_listings(self, zone: str, since_ids: set[str]) -> list[str]:
        del since_ids
        url_by_id: dict[str, str] = {}
        api_payload_extra = {"order": "publicationDate", "sort": "desc"}
        for page in range(1, 4):
            api_payload = await self._fetch_api_page(zone, page, extra_payload=api_payload_extra)
            elements = api_payload.get("elementList")
            if isinstance(elements, list):
                for element in elements:
                    listing = self._map_api_response(element, zone)
                    url_by_id[listing.external_id] = listing.raw_json["listing_url"]
                continue

            html = await self._fetch_html_page(self._search_url(page, newest=True))
            for listing in self._parse_search_html(html, zone):
                url_by_id[listing.external_id] = listing.raw_json["listing_url"]

        new_ids = await self._filter_new(self.redis, zone, set(url_by_id))
        return [url_by_id[listing_id] for listing_id in sorted(new_ids)]

    def _search_url(self, page: int, *, newest: bool = False) -> str:
        parsed = urlparse(_base_search_url(self.search_url))
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["pagina"] = str(page)
        if newest:
            query["orden"] = "publicacion-desc"
        return urlunparse(parsed._replace(query=urlencode(query)))
