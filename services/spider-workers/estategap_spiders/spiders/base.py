"""Base spider abstraction and shared Redis helpers."""

from __future__ import annotations

import inspect
from abc import ABC, abstractmethod
from typing import ClassVar
from uuid import uuid4

import redis.asyncio as redis
import structlog

from estategap_common.models.listing import RawListing

from ..config import Config
from ..http_client import HttpClient
from ..proxy_client import ProxyAssignment, ProxyClient


class BaseSpider(ABC):
    """Abstract base class for all country/portal spiders."""

    COUNTRY: ClassVar[str]
    PORTAL: ClassVar[str]

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if inspect.isabstract(cls):
            return
        country = getattr(cls, "COUNTRY", "")
        portal = getattr(cls, "PORTAL", "")
        if country and portal:
            from . import REGISTRY

            REGISTRY[(country.lower(), portal.lower())] = cls

    def __init__(self, config: Config) -> None:
        self.config = config
        self.redis = redis.from_url(config.redis_url, decode_responses=True)
        self.proxy_client = ProxyClient(config.proxy_manager_addr)
        self.logger = structlog.get_logger(type(self).__name__).bind(
            portal=self.PORTAL.lower(),
            country=self.COUNTRY.lower(),
        )
        self.search_url = ""
        self._http_client: HttpClient | None = None
        self._proxy_assignment: ProxyAssignment | None = None
        self._session_id = uuid4().hex

    @abstractmethod
    async def scrape_search_page(self, zone: str, page: int) -> list[RawListing]:
        """Scrape one search results page."""

    @abstractmethod
    async def scrape_listing_detail(self, url: str) -> RawListing | None:
        """Scrape a single listing detail page."""

    @abstractmethod
    async def detect_new_listings(self, zone: str, since_ids: set[str]) -> list[str]:
        """Return URLs for listings not yet seen in Redis."""

    async def close(self) -> None:
        if self._http_client is not None:
            await self._http_client.close()
            self._http_client = None
        await self.proxy_client.close()
        await self.redis.aclose()

    async def _ensure_http_client(self, *, force_rotate: bool = False) -> HttpClient:
        if self._http_client is None or force_rotate:
            if self._http_client is not None:
                await self._http_client.close()
            self._session_id = uuid4().hex
            self._proxy_assignment = await self.proxy_client.get_proxy(
                self.COUNTRY,
                self.PORTAL,
                self._session_id,
            )
            self._http_client = HttpClient(self._proxy_assignment.proxy_url, self.config)
        return self._http_client

    @property
    def proxy_url(self) -> str:
        return self._proxy_assignment.proxy_url if self._proxy_assignment is not None else ""

    async def _get_seen_ids(self, redis_client, zone: str) -> set[str]:
        values = await redis_client.smembers(self._seen_key(zone))
        return {str(value) for value in values}

    async def _mark_seen(self, redis_client, zone: str, ids: set[str]) -> None:
        if ids:
            await redis_client.sadd(self._seen_key(zone), *sorted(ids))

    async def _filter_new(self, redis_client, zone: str, candidate_ids: set[str]) -> set[str]:
        if not candidate_ids:
            return set()
        ordered_ids = sorted(candidate_ids)
        results = await redis_client.smismember(self._seen_key(zone), ordered_ids)
        return {candidate_id for candidate_id, exists in zip(ordered_ids, results, strict=True) if not exists}

    def _seen_key(self, zone: str) -> str:
        return f"seen:{self.PORTAL.lower()}:{self.COUNTRY.lower()}:{zone}"
