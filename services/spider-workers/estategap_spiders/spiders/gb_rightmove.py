"""Rightmove portal spider."""

from __future__ import annotations

import json
from typing import Any

from bs4 import BeautifulSoup
from parsel import Selector

from estategap_common.models.listing import RawListing

from ..http_client import PermanentFailureError
from ._eu_utils import clean_text, extract_external_id, extract_float, full_url, now_utc
from .base import BaseSpider
from .gb_rightmove_parser import parse_json_ld, parse_uk_fields


class RightmoveSpider(BaseSpider):
    COUNTRY = "GB"
    PORTAL = "rightmove"

    async def scrape_search_page(self, zone: str, page: int) -> list[RawListing]:
        del zone
        html = await self._fetch_html_page(self._search_url(page))
        return [self._listing_from_payload(item) for item in self._parse_search_html(html)]

    async def scrape_listing_detail(self, url: str) -> RawListing | None:
        html = await self._fetch_html_page(url)
        payload = self._parse_detail_html(html)
        if not payload:
            return None
        payload["url"] = url
        return self._listing_from_payload(payload)

    async def detect_new_listings(self, zone: str, since_ids: set[str]) -> list[str]:
        del since_ids
        listings = await self.scrape_search_page(zone, 1)
        url_by_id = {
            listing.external_id: str(listing.raw_json.get("url") or listing.raw_json.get("source_url"))
            for listing in listings
            if listing.raw_json.get("url") or listing.raw_json.get("source_url")
        }
        new_ids = await self._filter_new(self.redis, zone, set(url_by_id))
        return [url_by_id[item] for item in sorted(new_ids)]

    async def _fetch_html_page(self, url: str) -> str:
        client = await self._ensure_http_client()
        response = await client.get(url)
        if response.status_code >= 400:
            raise PermanentFailureError(f"Rightmove returned {response.status_code}")
        return response.text

    def _parse_search_html(self, html: str) -> list[dict[str, Any]]:
        selector = Selector(html)
        payloads: list[dict[str, Any]] = []
        for card in selector.css("article[data-listing], article.propertyCard"):
            raw = card.attrib.get("data-listing")
            payload: dict[str, Any] = {}
            if raw:
                try:
                    data = json.loads(raw)
                except json.JSONDecodeError:
                    data = {}
                if isinstance(data, dict):
                    payload = self._payload_from_card_data(data)
            if not payload:
                html_fragment = card.get()
                payload = self._parse_detail_html(html_fragment)
            if payload:
                payloads.append(payload)
        return payloads

    def _parse_detail_html(self, html: str) -> dict[str, Any]:
        soup = BeautifulSoup(html, "html.parser")
        payload = parse_json_ld(html)
        if not payload:
            return {}
        uk_fields = parse_uk_fields(soup)
        json_ld = payload.get("json_ld", {})
        address = json_ld.get("address") if isinstance(json_ld.get("address"), dict) else {}
        geo = json_ld.get("geo") if isinstance(json_ld.get("geo"), dict) else {}
        payload.update(
            {
                **uk_fields,
                "propertyType": clean_text(json_ld.get("@type") or soup.get("data-property-type")),
                "latitude": extract_float(geo.get("latitude")),
                "longitude": extract_float(geo.get("longitude")),
                "url": full_url("https://www.rightmove.co.uk", json_ld.get("url")),
                "description": clean_text(json_ld.get("description")),
                "address": clean_text(address.get("streetAddress")),
                "city": clean_text(address.get("addressLocality")),
                "region": clean_text(address.get("addressRegion")),
                "postalCode": clean_text(address.get("postalCode")),
            }
        )
        return payload

    def _payload_from_card_data(self, data: dict[str, Any]) -> dict[str, Any]:
        return {
            "json_ld": {
                "offers": {"price": data.get("price"), "priceCurrency": "GBP"},
                "numberOfRooms": data.get("rooms"),
                "floorSize": {"value": data.get("area")},
                "url": data.get("url"),
                "address": {
                    "streetAddress": data.get("address"),
                    "addressLocality": data.get("city"),
                    "addressRegion": data.get("region"),
                    "postalCode": data.get("postalCode"),
                },
                "@type": data.get("propertyType"),
                "description": data.get("description"),
            },
            "currency": "GBP",
            "propertyType": data.get("propertyType"),
            "councilTaxBand": data.get("councilTaxBand"),
            "epcRating": data.get("epcRating"),
            "energyRating": data.get("epcRating"),
            "tenure": data.get("tenure"),
            "leaseholdYearsRemaining": data.get("leaseholdYearsRemaining"),
            "latitude": extract_float(data.get("latitude")),
            "longitude": extract_float(data.get("longitude")),
            "url": full_url("https://www.rightmove.co.uk", data.get("url")),
            "description": clean_text(data.get("description")),
            "address": clean_text(data.get("address")),
            "city": clean_text(data.get("city")),
            "region": clean_text(data.get("region")),
            "postalCode": clean_text(data.get("postalCode")),
        }

    def _listing_from_payload(self, payload: dict[str, Any]) -> RawListing:
        url = str(payload.get("url") or "")
        return RawListing(
            external_id=extract_external_id(url),
            portal=self.PORTAL,
            country_code=self.COUNTRY,
            raw_json=payload,
            scraped_at=now_utc(),
        )

    def _search_url(self, page: int) -> str:
        base = self.search_url or "https://www.rightmove.co.uk/property-for-sale/find.html"
        separator = "&" if "?" in base else "?"
        return f"{base}{separator}index={(page - 1) * 24}"


__all__ = ["RightmoveSpider"]
