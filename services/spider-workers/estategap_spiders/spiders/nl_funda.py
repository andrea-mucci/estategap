"""Funda portal spider."""

from __future__ import annotations

import asyncio
from time import monotonic

from estategap_common.models.listing import RawListing

from ..http_client import PermanentFailureError
from ._eu_utils import extract_external_id, now_utc
from .base import BaseSpider
from .nl_funda_parser import extract_nuxt_data, parse_listing


class FundaSpider(BaseSpider):
    COUNTRY = "NL"
    PORTAL = "funda"

    def __init__(self, config) -> None:
        super().__init__(config)
        self._last_request_started = 0.0

    async def scrape_search_page(self, zone: str, page: int) -> list[RawListing]:
        del zone
        html = await self._fetch_html_page(self._search_url(page))
        data = extract_nuxt_data(html)
        listings = data.get("listings") if isinstance(data.get("listings"), list) else []
        return [self._listing_from_payload(parse_listing(item)) for item in listings if isinstance(item, dict)]

    async def scrape_listing_detail(self, url: str) -> RawListing | None:
        html = await self._fetch_html_page(url)
        data = extract_nuxt_data(html)
        listing = data.get("listing")
        if not isinstance(listing, dict):
            return None
        payload = parse_listing(listing)
        payload["url"] = url
        return self._listing_from_payload(payload)

    async def detect_new_listings(self, zone: str, since_ids: set[str]) -> list[str]:
        del since_ids
        url_by_id = {
            listing.external_id: str(listing.raw_json.get("url") or listing.raw_json.get("source_url"))
            for listing in await self.scrape_search_page(zone, 1)
            if listing.raw_json.get("url") or listing.raw_json.get("source_url")
        }
        new_ids = await self._filter_new(self.redis, zone, set(url_by_id))
        return [url_by_id[item] for item in sorted(new_ids)]

    async def _fetch_html_page(self, url: str) -> str:
        await self._enforce_rate_limit()
        client = await self._ensure_http_client()
        response = await client.get(url)
        if response.status_code >= 400:
            raise PermanentFailureError(f"Funda returned {response.status_code}")
        return response.text

    async def _enforce_rate_limit(self) -> None:
        now = monotonic()
        elapsed = now - self._last_request_started
        if self._last_request_started and elapsed < 2.0:
            await asyncio.sleep(2.0 - elapsed)
        self._last_request_started = monotonic()

    def _listing_from_payload(self, payload: dict[str, object]) -> RawListing:
        url = str(payload.get("url") or "")
        return RawListing(
            external_id=extract_external_id(url),
            portal=self.PORTAL,
            country_code=self.COUNTRY,
            raw_json=payload,
            scraped_at=now_utc(),
        )

    def _search_url(self, page: int) -> str:
        base = self.search_url or "https://www.funda.nl/zoeken/koop"
        separator = "&" if "?" in base else "?"
        return f"{base}{separator}page={page}"


__all__ = ["FundaSpider"]
