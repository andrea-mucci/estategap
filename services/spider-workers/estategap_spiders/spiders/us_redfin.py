"""Redfin US spider implementation."""

from __future__ import annotations

import asyncio
import re
from time import monotonic
from typing import Any

from estategap_common.models.listing import RawListing

from ..config import RATE_LIMITS
from ..http_client import PermanentFailureError
from ._eu_utils import clean_text, extract_external_id, extract_float, extract_int, now_utc
from .base import BaseSpider
from .us_redfin_parser import parse_above_fold, parse_school_data
from .us_utils import sqft_to_m2


_PROPERTY_ID_RE = re.compile(r"/home/(?P<id>\d+)(?:/|$)")


class RedfinUSSpider(BaseSpider):
    COUNTRY = "US"
    PORTAL = "redfin"
    RATE_LIMIT_SECONDS = RATE_LIMITS["redfin"]

    def __init__(self, config) -> None:
        super().__init__(config)
        self._last_request_started = 0.0

    async def scrape_search_page(self, zone: str, page: int) -> list[RawListing]:
        del zone
        payload = await self._fetch_json(self._search_api_url(page))
        results = payload.get("payload", {}).get("searchResults") or payload.get("searchResults") or []
        listings: list[RawListing] = []
        for item in results:
            if not isinstance(item, dict):
                continue
            area_sqft = extract_float(item.get("sqFt"))
            raw = {
                "external_id": clean_text(item.get("id") or item.get("propertyId")),
                "source_url": str(item.get("url") or ""),
                "price_usd_cents": extract_int(item.get("price")) * 100 if item.get("price") is not None else None,
                "currency": "USD",
                "area_sqft": area_sqft,
                "area_m2": sqft_to_m2(area_sqft),
                "bedrooms": extract_int(item.get("beds")),
                "bathrooms": extract_float(item.get("baths")),
                "property_type": clean_text(item.get("propertyType")),
                "lat": extract_float(item.get("lat")),
                "lon": extract_float(item.get("lng")),
                "address": clean_text(item.get("streetLine")),
                "city": clean_text(item.get("city")),
                "region": clean_text(item.get("state")),
                "postal_code": clean_text(item.get("zip")),
                "images_count": len(item.get("photos") or []),
            }
            listings.append(self._listing_from_payload(raw))
        return listings

    async def scrape_listing_detail(self, url: str) -> RawListing | None:
        property_id = self._extract_property_id(url)
        if property_id is None:
            return None
        above_fold = await self._fetch_json(self._detail_api_url(property_id))
        schools_payload = await self._fetch_json(self._schools_api_url(property_id))
        payload = parse_above_fold(
            {
                **above_fold,
                "payload": {
                    **(above_fold.get("payload") if isinstance(above_fold.get("payload"), dict) else {}),
                    "schoolsData": schools_payload.get("payload", {}).get("schools")
                    or schools_payload.get("schools")
                    or [],
                },
            }
        )
        payload.setdefault("source_url", url)
        school_data = schools_payload.get("payload", {}).get("schools") or schools_payload.get("schools") or []
        if isinstance(school_data, list):
            payload["school_rating"] = parse_school_data([item for item in school_data if isinstance(item, dict)])
        return self._listing_from_payload(payload)

    async def detect_new_listings(self, zone: str, since_ids: set[str]) -> list[str]:
        del since_ids
        url_by_id = {
            listing.external_id: str(listing.raw_json.get("source_url") or "")
            for listing in await self.scrape_search_page(zone, 1)
            if listing.raw_json.get("source_url")
        }
        new_ids = await self._filter_new(self.redis, zone, set(url_by_id))
        return [url_by_id[item] for item in sorted(new_ids)]

    async def _fetch_json(self, url: str) -> dict[str, Any]:
        await self._enforce_rate_limit()
        client = await self._ensure_http_client()
        response = await client.get(url)
        if response.status_code >= 400:
            raise PermanentFailureError(f"Redfin returned {response.status_code}")
        return response.json()

    async def _enforce_rate_limit(self) -> None:
        now = monotonic()
        elapsed = now - self._last_request_started
        delay = getattr(self.config, "redfin_rate_limit_seconds", self.RATE_LIMIT_SECONDS)
        if self._last_request_started and elapsed < delay:
            await asyncio.sleep(delay - elapsed)
        self._last_request_started = monotonic()

    def _listing_from_payload(self, payload: dict[str, object]) -> RawListing:
        source_url = str(payload.get("source_url") or "")
        external_id = str(payload.get("external_id") or extract_external_id(source_url, fallback=source_url))
        return RawListing(
            external_id=external_id,
            portal=self.PORTAL,
            country_code=self.COUNTRY,
            raw_json=payload,
            scraped_at=now_utc(),
        )

    def _search_api_url(self, page: int) -> str:
        if self.search_url:
            separator = "&" if "?" in self.search_url else "?"
            return f"{self.search_url}{separator}page_number={page}"
        return (
            "https://www.redfin.com/stingray/api/gis"
            f"?al=1&market=newyork&num_homes=20&page_number={page}&region_type=6&sp=true&status=9&uipt=1,2"
        )

    def _detail_api_url(self, property_id: str) -> str:
        return f"https://www.redfin.com/stingray/api/home/details/aboveTheFold?propertyId={property_id}&accessLevel=3"

    def _schools_api_url(self, property_id: str) -> str:
        return f"https://www.redfin.com/stingray/api/home/details/schoolsData?propertyId={property_id}"

    @staticmethod
    def _extract_property_id(url: str) -> str | None:
        match = _PROPERTY_ID_RE.search(url)
        if match is not None:
            return match.group("id")
        query_match = re.search(r"propertyId=(?P<id>\d+)", url)
        return query_match.group("id") if query_match else None


__all__ = ["RedfinUSSpider"]
