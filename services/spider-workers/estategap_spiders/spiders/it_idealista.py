"""Idealista Italy portal spider."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlencode

from estategap_common.models.listing import RawListing

from ..browser import fetch_with_browser
from ..http_client import PermanentFailureError
from ._eu_utils import extract_external_id, now_utc
from .base import BaseSpider
from .it_idealista_parser import parse_api_response, parse_detail_page


class IdealistaITSpider(BaseSpider):
    COUNTRY = "IT"
    PORTAL = "idealista"
    API_URL = "https://api.idealista.com/3.5/it/search"

    def __init__(self, config) -> None:
        super().__init__(config)
        self._api_token = config.idealista_it_api_token or config.idealista_api_token

    async def scrape_search_page(self, zone: str, page: int) -> list[RawListing]:
        api_data = await self._fetch_api_page(zone, page)
        elements = api_data.get("elementList")
        if isinstance(elements, list) and elements:
            return [self._listing_from_payload(parse_api_response(item)) for item in elements]
        html = await self._fetch_html_page(self._search_url(page))
        detail = parse_detail_page(html)
        return [self._listing_from_payload(detail)] if detail else []

    async def scrape_listing_detail(self, url: str) -> RawListing | None:
        html = await self._fetch_html_page(url)
        payload = parse_detail_page(html)
        if not payload:
            return None
        payload["url"] = url
        return self._listing_from_payload(payload)

    async def detect_new_listings(self, zone: str, since_ids: set[str]) -> list[str]:
        del since_ids
        newest_payload = await self._fetch_api_page(zone, 1, extra_payload={"order": "publicationDate", "sort": "desc"})
        elements = newest_payload.get("elementList")
        if not isinstance(elements, list):
            return []
        url_by_id: dict[str, str] = {}
        for item in elements:
            payload = parse_api_response(item)
            url = str(payload.get("url") or "")
            if url:
                url_by_id[self._listing_from_payload(payload).external_id] = url
        new_ids = await self._filter_new(self.redis, zone, set(url_by_id))
        return [url_by_id[item] for item in sorted(new_ids)]

    async def _fetch_api_page(
        self,
        zone: str,
        page: int,
        *,
        extra_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self._api_token:
            return {}
        client = await self._ensure_http_client()
        payload: dict[str, Any] = {"numPage": page, "maxItems": 50, "zone": zone}
        if extra_payload:
            payload.update(extra_payload)
        response = await client.post(
            self.API_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {self._api_token}",
                "User-Agent": "idealista/8.0.0 (Android 14)",
            },
        )
        if response.status_code in {401, 403}:
            return {}
        if response.status_code >= 400:
            raise PermanentFailureError(f"Idealista IT API returned {response.status_code}")
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
            raise PermanentFailureError(f"Idealista IT HTML returned {response.status_code}")
        return response.text

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
        base = self.search_url or "https://www.idealista.it/vendita-case/roma/"
        separator = "&" if "?" in base else "?"
        return f"{base}{separator}{urlencode({'pagina': page})}"


__all__ = ["IdealistaITSpider"]
