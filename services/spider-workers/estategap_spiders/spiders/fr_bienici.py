"""Bien'ici portal spider."""

from __future__ import annotations

from estategap_common.models.listing import RawListing

from ..http_client import PermanentFailureError
from ._eu_utils import extract_external_id, now_utc
from .base import BaseSpider
from .fr_bienici_parser import extract_preloaded_state, parse_listing


class BienIciSpider(BaseSpider):
    COUNTRY = "FR"
    PORTAL = "bienici"

    async def scrape_search_page(self, zone: str, page: int) -> list[RawListing]:
        del zone
        html = await self._fetch_html_page(self._search_url(page))
        state = extract_preloaded_state(html)
        listings = state.get("listings") if isinstance(state.get("listings"), list) else []
        return [self._listing_from_payload(parse_listing(item)) for item in listings if isinstance(item, dict)]

    async def scrape_listing_detail(self, url: str) -> RawListing | None:
        html = await self._fetch_html_page(url)
        state = extract_preloaded_state(html)
        item = state.get("listing")
        if not isinstance(item, dict):
            return None
        payload = parse_listing(item)
        payload["url"] = url
        return self._listing_from_payload(payload)

    async def detect_new_listings(self, zone: str, since_ids: set[str]) -> list[str]:
        del since_ids
        url_by_id: dict[str, str] = {}
        for listing in await self.scrape_search_page(zone, 1):
            url = str(listing.raw_json.get("url") or listing.raw_json.get("source_url") or "")
            if url:
                url_by_id[listing.external_id] = url
        new_ids = await self._filter_new(self.redis, zone, set(url_by_id))
        return [url_by_id[item] for item in sorted(new_ids)]

    async def _fetch_html_page(self, url: str) -> str:
        client = await self._ensure_http_client()
        response = await client.get(url)
        if response.status_code >= 400:
            raise PermanentFailureError(f"Bien'ici returned {response.status_code}")
        return response.text

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
        base = self.search_url or "https://www.bienici.com/recherche/achat/france"
        separator = "&" if "?" in base else "?"
        return f"{base}{separator}page={page}"


__all__ = ["BienIciSpider"]
