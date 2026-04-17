"""Realtor.com US spider implementation."""

from __future__ import annotations

import asyncio
import re
from time import monotonic

from estategap_common.models.listing import RawListing

from ..config import RATE_LIMITS
from ..http_client import PermanentFailureError
from ._eu_utils import clean_text, extract_external_id, full_url, load_json_ld_blocks, now_utc
from .base import BaseSpider
from .us_realtor_parser import parse_json_ld, parse_window_data


_DETAIL_LINK_RE = re.compile(r'href=["\'](?P<url>/realestateandhomes-detail/[^"\']+)["\']')


class RealtorComUSSpider(BaseSpider):
    COUNTRY = "US"
    PORTAL = "realtor_com"
    RATE_LIMIT_SECONDS = RATE_LIMITS["realtor_com"]

    def __init__(self, config) -> None:
        super().__init__(config)
        self._last_request_started = 0.0

    async def scrape_search_page(self, zone: str, page: int) -> list[RawListing]:
        del zone
        html = await self._fetch_html(self._search_url(page))
        listings: list[RawListing] = []
        for url in sorted(set(_DETAIL_LINK_RE.findall(html))):
            listings.append(
                self._listing_from_payload(
                    {
                        "source_url": full_url("https://www.realtor.com", url),
                        "property_type": "residential",
                    }
                )
            )
        if listings:
            return listings
        for block in load_json_ld_blocks(html):
            payload = parse_json_ld([block])
            if payload:
                listings.append(self._listing_from_payload(payload))
        return listings

    async def scrape_listing_detail(self, url: str) -> RawListing | None:
        html = await self._fetch_html(url)
        payload = parse_json_ld(load_json_ld_blocks(html))
        payload.update({key: value for key, value in parse_window_data(html).items() if value is not None})
        if not payload:
            return None
        payload.setdefault("source_url", url)
        payload.setdefault("property_type", "residential")
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

    async def _fetch_html(self, url: str) -> str:
        await self._enforce_rate_limit()
        client = await self._ensure_http_client()
        response = await client.get(url)
        if response.status_code >= 400:
            raise PermanentFailureError(f"Realtor.com returned {response.status_code}")
        return response.text

    async def _enforce_rate_limit(self) -> None:
        now = monotonic()
        elapsed = now - self._last_request_started
        delay = getattr(self.config, "realtor_rate_limit_seconds", self.RATE_LIMIT_SECONDS)
        if self._last_request_started and elapsed < delay:
            await asyncio.sleep(delay - elapsed)
        self._last_request_started = monotonic()

    def _listing_from_payload(self, payload: dict[str, object]) -> RawListing:
        source_url = str(payload.get("source_url") or "")
        external_id = str(
            payload.get("mls_id")
            or payload.get("external_id")
            or extract_external_id(source_url, fallback=source_url)
        )
        return RawListing(
            external_id=external_id,
            portal=self.PORTAL,
            country_code=self.COUNTRY,
            raw_json=payload,
            scraped_at=now_utc(),
        )

    def _search_url(self, page: int) -> str:
        base = self.search_url or "https://www.realtor.com/realestateandhomes-search/New-York_NY"
        separator = "&" if "?" in base else "?"
        return f"{base}{separator}pg={page}"


__all__ = ["RealtorComUSSpider"]
