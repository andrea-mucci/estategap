"""Fixture-backed spider used when test mode disables live scraping."""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from typing import Any

import boto3

from estategap_common.models.listing import RawListing

from ..config import Config
from .base import BaseSpider


class FixtureSpider(BaseSpider):
    """Load static listing fixtures from MinIO and emit them as raw listings."""

    COUNTRY = "fixture"
    PORTAL = "fixture"

    def __init__(self, config: Config, *, country: str, portal: str) -> None:
        self.COUNTRY = country.strip().upper()
        self.PORTAL = portal.strip().lower()
        self._fixture_cache: list[dict[str, Any]] | None = None
        self._s3_client: Any | None = None
        super().__init__(config)

    async def scrape_search_page(self, zone: str, page: int) -> list[RawListing]:
        if page > 1:
            return []
        listings = await self._load_fixtures()
        return [self._to_raw_listing(listing) for listing in listings if self._matches_zone(listing, zone)]

    async def scrape_listing_detail(self, url: str) -> RawListing | None:
        listings = await self._load_fixtures()
        target = url.strip().rstrip("/")
        for listing in listings:
            source_url = str(listing.get("source_url", "")).strip().rstrip("/")
            source_id = str(listing.get("source_id", "")).strip()
            if target in {source_url, source_id, source_url.rsplit("/", 1)[-1]}:
                return self._to_raw_listing(listing)
        return None

    async def detect_new_listings(self, zone: str, since_ids: set[str]) -> list[str]:
        listings = await self._load_fixtures()
        urls: list[str] = []
        for listing in listings:
            source_id = str(listing.get("source_id", "")).strip()
            if source_id in since_ids:
                continue
            if not self._matches_zone(listing, zone):
                continue
            source_url = str(listing.get("source_url", "")).strip()
            if source_url:
                urls.append(source_url)
        return urls

    async def _load_fixtures(self) -> list[dict[str, Any]]:
        if self._fixture_cache is not None:
            return self._fixture_cache
        payload = await asyncio.to_thread(self._read_fixture_payload)
        data = json.loads(payload)
        if not isinstance(data, list):
            raise ValueError("fixture listing payload must be a list")
        self._fixture_cache = [item for item in data if isinstance(item, dict)]
        return self._fixture_cache

    def _read_fixture_payload(self) -> str:
        response = self._client().get_object(
            Bucket=self.config.fixture_minio_bucket,
            Key=f"listings/{self.COUNTRY.lower()}.json",
        )
        body = response["Body"]
        try:
            return body.read().decode("utf-8")
        finally:
            body.close()

    def _client(self) -> Any:
        if self._s3_client is None:
            self._s3_client = boto3.client(
                "s3",
                endpoint_url=self.config.minio_endpoint,
                aws_access_key_id=self.config.minio_access_key,
                aws_secret_access_key=self.config.minio_secret_key,
            )
        return self._s3_client

    def _matches_zone(self, listing: dict[str, Any], zone: str) -> bool:
        normalized_zone = zone.strip().lower().replace("-", " ")
        if normalized_zone in {"", "default"}:
            return True
        haystacks = [
            str(listing.get("zone_id", "")),
            str(listing.get("district", "")),
            str(listing.get("city", "")),
            str(listing.get("address", "")),
        ]
        return any(normalized_zone in value.lower().replace("-", " ") for value in haystacks)

    def _to_raw_listing(self, listing: dict[str, Any]) -> RawListing:
        scraped_at = self._parse_timestamp(str(listing.get("updated_at", "")))
        payload = dict(listing)
        payload["country"] = self.COUNTRY
        payload["portal"] = self.PORTAL
        return RawListing(
            external_id=str(listing.get("source_id") or listing.get("id") or ""),
            portal=self.PORTAL,
            country_code=self.COUNTRY,
            raw_json=payload,
            scraped_at=scraped_at,
        )

    @staticmethod
    def _parse_timestamp(value: str) -> datetime:
        if value:
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                pass
        return datetime.now(tz=UTC)
