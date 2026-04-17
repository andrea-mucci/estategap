"""SeLoger portal spider."""

from __future__ import annotations

from estategap_common.models.listing import RawListing

from ..browser import fetch_with_browser
from ..http_client import PermanentFailureError
from ._eu_utils import extract_external_id, now_utc
from .base import BaseSpider
from .fr_seloger_parser import parse_json_ld, parse_search_page


class SeLogerSpider(BaseSpider):
    COUNTRY = "FR"
    PORTAL = "seloger"

    async def scrape_search_page(self, zone: str, page: int) -> list[RawListing]:
        html = await self._fetch_html_page(self._search_url(page))
        listings: list[RawListing] = []
        for item in parse_search_page(html):
            url = item.get("url")
            if not url:
                continue
            detail = await self.scrape_listing_detail(str(url))
            if detail is not None:
                listings.append(detail)
        return listings

    async def scrape_listing_detail(self, url: str) -> RawListing | None:
        html = await self._fetch_html_page(url)
        payload = parse_json_ld(html)
        if not payload:
            return None
        payload["url"] = url
        return RawListing(
            external_id=extract_external_id(url),
            portal=self.PORTAL,
            country_code=self.COUNTRY,
            raw_json=payload,
            scraped_at=now_utc(),
        )

    async def detect_new_listings(self, zone: str, since_ids: set[str]) -> list[str]:
        del since_ids
        html = await self._fetch_html_page(self._search_url(1))
        url_by_id = {
            extract_external_id(str(item["url"])): str(item["url"])
            for item in parse_search_page(html)
            if item.get("url")
        }
        new_ids = await self._filter_new(self.redis, zone, set(url_by_id))
        return [url_by_id[item] for item in sorted(new_ids)]

    async def _fetch_html_page(self, url: str) -> str:
        return await fetch_with_browser(url, self.proxy_url)

    def _search_url(self, page: int) -> str:
        base = self.search_url or "https://www.seloger.com/list.htm?projects=2&types=1"
        separator = "&" if "?" in base else "?"
        return f"{base}{separator}page={page}"


__all__ = ["SeLogerSpider"]
