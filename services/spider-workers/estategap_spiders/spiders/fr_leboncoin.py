"""LeBonCoin portal spider."""

from __future__ import annotations

from estategap_common.models.listing import RawListing

from ..browser import fetch_with_browser
from ._eu_utils import extract_external_id, now_utc
from .base import BaseSpider
from .fr_leboncoin_parser import parse_search_cards


class LeBonCoinSpider(BaseSpider):
    COUNTRY = "FR"
    PORTAL = "leboncoin"

    async def scrape_search_page(self, zone: str, page: int) -> list[RawListing]:
        del zone
        html = await self._fetch_html_page(self._search_url(page))
        return [self._listing_from_payload(payload) for payload in parse_search_cards(html)]

    async def scrape_listing_detail(self, url: str) -> RawListing | None:
        html = await self._fetch_html_page(url)
        payloads = parse_search_cards(html)
        if not payloads:
            return None
        payload = payloads[0]
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
        return await fetch_with_browser(url, self.proxy_url)

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
        base = self.search_url or "https://www.leboncoin.fr/recherche?category=9"
        separator = "&" if "?" in base else "?"
        return f"{base}{separator}page={page}"


__all__ = ["LeBonCoinSpider"]
