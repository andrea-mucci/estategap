"""Immobiliare.it portal spider."""

from __future__ import annotations

import json
from typing import Any

from parsel import Selector

from estategap_common.models.listing import RawListing

from ..browser import fetch_with_browser
from ..http_client import PermanentFailureError
from ._eu_utils import extract_external_id, full_url, now_utc
from .base import BaseSpider
from .it_immobiliare_parser import parse_detail_page, parse_search_result


class ImmobiliareSpider(BaseSpider):
    COUNTRY = "IT"
    PORTAL = "immobiliare"
    BASE_URL = "https://www.immobiliare.it"
    API_BASE = "https://www.immobiliare.it/api/v1/search"

    def __init__(self, config) -> None:
        super().__init__(config)
        self._api_token = config.immobiliare_api_token

    async def scrape_search_page(self, zone: str, page: int) -> list[RawListing]:
        api_data = await self._fetch_api_page(zone, page)
        items = api_data.get("results")
        if isinstance(items, list) and items:
            return [self._listing_from_payload(parse_search_result(item)) for item in items]
        html = await self._fetch_html_page(self._search_url(page))
        listings = self._parse_search_html(html)
        return [self._listing_from_payload(payload) for payload in listings]

    async def scrape_listing_detail(self, url: str) -> RawListing | None:
        html = await self._fetch_html_page(url)
        payload = parse_detail_page(html)
        if not payload:
            return None
        payload["url"] = url
        return self._listing_from_payload(payload)

    async def detect_new_listings(self, zone: str, since_ids: set[str]) -> list[str]:
        del since_ids
        url_by_id: dict[str, str] = {}
        for page in range(1, 4):
            for listing in await self.scrape_search_page(zone, page):
                url = str(listing.raw_json.get("url") or listing.raw_json.get("source_url") or "")
                if url:
                    url_by_id[listing.external_id] = url
        new_ids = await self._filter_new(self.redis, zone, set(url_by_id))
        return [url_by_id[item] for item in sorted(new_ids)]

    async def _fetch_api_page(self, zone: str, page: int) -> dict[str, Any]:
        client = await self._ensure_http_client()
        headers = {"Accept": "application/json"}
        if self._api_token:
            headers["Authorization"] = f"Bearer {self._api_token}"
        response = await client.get(self.API_BASE, params={"zone": zone, "page": page}, headers=headers)
        if response.status_code in {401, 403}:
            return {}
        if response.status_code >= 400:
            raise PermanentFailureError(f"Immobiliare API returned {response.status_code}")
        try:
            payload = response.json()
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}

    async def _fetch_html_page(self, url: str) -> str:
        client = await self._ensure_http_client()
        response = await client.get(url)
        if client.is_blocked(response):
            return await fetch_with_browser(url, self.proxy_url)
        if response.status_code >= 400:
            raise PermanentFailureError(f"Immobiliare HTML returned {response.status_code}")
        return response.text

    def _parse_search_html(self, html: str) -> list[dict[str, Any]]:
        selector = Selector(html)
        payloads: list[dict[str, Any]] = []
        for card in selector.css("article[data-id], [data-listing]"):
            raw = card.attrib.get("data-listing")
            if raw:
                try:
                    item = json.loads(raw)
                except json.JSONDecodeError:
                    item = {}
                if isinstance(item, dict):
                    payloads.append(parse_search_result(item))
                    continue
            url = full_url(self.BASE_URL, card.attrib.get("data-url") or card.css("a::attr(href)").get())
            if url:
                payloads.append({"url": url})
        return payloads

    def _listing_from_payload(self, payload: dict[str, Any]) -> RawListing:
        url = str(payload.get("url") or "")
        return RawListing(
            external_id=extract_external_id(url, fallback=str(payload.get("id") or url)),
            portal=self.PORTAL,
            country_code=self.COUNTRY,
            raw_json=payload,
            scraped_at=now_utc(),
        )

    def _search_url(self, page: int) -> str:
        base = self.search_url or "https://www.immobiliare.it/vendita-case/roma/"
        separator = "&" if "?" in base else "?"
        return f"{base}{separator}pag={page}"


__all__ = ["ImmobiliareSpider"]
