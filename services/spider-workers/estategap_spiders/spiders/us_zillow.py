"""Zillow US spider implementation."""

from __future__ import annotations

import asyncio
import json
import re
from time import monotonic

from estategap_common.models.listing import RawListing

from ..browser import fetch_with_browser
from ..config import RATE_LIMITS
from ..http_client import ParseError, PermanentFailureError
from ._eu_utils import extract_external_id, now_utc
from .base import BaseSpider
from .us_zillow_parser import parse_listing_detail, parse_search_results


_NEXT_DATA_RE = re.compile(
    r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(?P<body>.*?)</script>',
    re.DOTALL,
)


class ZillowUSSpider(BaseSpider):
    COUNTRY = "US"
    PORTAL = "zillow"
    RATE_LIMIT_SECONDS = RATE_LIMITS["zillow"]
    REQUIRES_PLAYWRIGHT = True
    USE_RESIDENTIAL_PROXY = True

    def __init__(self, config) -> None:
        super().__init__(config)
        self._last_request_started = 0.0

    async def scrape_search_page(self, zone: str, page: int) -> list[RawListing]:
        del zone
        next_data = await self._fetch_next_data(self._search_url(page))
        return [self._listing_from_payload(item) for item in parse_search_results(next_data)]

    async def scrape_listing_detail(self, url: str) -> RawListing | None:
        next_data = await self._fetch_next_data(url)
        payload = parse_listing_detail(next_data)
        if not payload:
            return None
        payload.setdefault("source_url", url)
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

    async def _fetch_next_data(self, url: str) -> dict:
        await self._enforce_rate_limit()
        html = await fetch_with_browser(url, self.proxy_url or self.config.proxy_us_url)
        match = _NEXT_DATA_RE.search(html)
        if match is None:
            raise ParseError("Zillow __NEXT_DATA__ block not found")
        try:
            return json.loads(match.group("body"))
        except json.JSONDecodeError as exc:
            raise ParseError("Invalid Zillow __NEXT_DATA__ payload") from exc

    async def _enforce_rate_limit(self) -> None:
        now = monotonic()
        elapsed = now - self._last_request_started
        delay = getattr(self.config, "zillow_rate_limit_seconds", self.RATE_LIMIT_SECONDS)
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

    def _search_url(self, page: int) -> str:
        base = self.search_url or "https://www.zillow.com/homes/for_sale/"
        separator = "&" if "?" in base else "?"
        return f"{base}{separator}page={page}"


__all__ = ["ZillowUSSpider"]
