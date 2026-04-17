from __future__ import annotations

from datetime import UTC, datetime

import pytest

from estategap_common.models.listing import RawListing

from estategap_spiders.config import Config
from estategap_spiders.spiders.base import BaseSpider


class FakeRedis:
    def __init__(self) -> None:
        self.sets: dict[str, set[str]] = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self.expiry: dict[str, int] = {}

    async def smembers(self, key: str) -> set[str]:
        return set(self.sets.get(key, set()))

    async def sadd(self, key: str, *values: str) -> None:
        self.sets.setdefault(key, set()).update(values)

    async def smismember(self, key: str, values: list[str]) -> list[bool]:
        members = self.sets.get(key, set())
        return [value in members for value in values]

    async def hset(self, key: str, field: str, value: str) -> None:
        self.hashes.setdefault(key, {})[field] = value

    async def hexists(self, key: str, field: str) -> bool:
        return field in self.hashes.get(key, {})

    async def expire(self, key: str, ttl: int) -> None:
        self.expiry[key] = ttl

    async def scard(self, key: str) -> int:
        return len(self.sets.get(key, set()))

    async def aclose(self) -> None:
        return None


class FakeJetStream:
    def __init__(self) -> None:
        self.messages: list[tuple[str, bytes]] = []

    async def publish(self, subject: str, payload: bytes) -> None:
        self.messages.append((subject, payload))


class FakeMessage:
    def __init__(self, data: bytes) -> None:
        self.data = data
        self.acked = False
        self.nak_calls: list[object] = []
        self.terminated = False

    async def ack(self) -> None:
        self.acked = True

    async def nak(self, delay=None) -> None:
        self.nak_calls.append(delay)

    async def term(self) -> None:
        self.terminated = True


def build_listing(external_id: str, zone: str, *, url: str | None = None) -> RawListing:
    return RawListing(
        external_id=external_id,
        portal="fixture",
        country_code="ES",
        raw_json={
            "price": 100_000_00,
            "currency": "EUR",
            "area_m2": 70.0,
            "rooms": 2,
            "bathrooms": 1,
            "photos": [],
            "listing_url": url or f"https://example.com/{external_id}",
            "zone_id": zone,
            "listing_type": "sale",
            "property_type": "residential",
        },
        scraped_at=datetime.now(UTC),
    )


class FixtureSpider(BaseSpider):
    COUNTRY = "ES"
    PORTAL = "fixture"

    async def scrape_search_page(self, zone: str, page: int) -> list[RawListing]:
        if page > 1:
            return []
        return [build_listing(f"{zone}-1", zone)]

    async def scrape_listing_detail(self, url: str) -> RawListing | None:
        external_id = url.rstrip("/").rsplit("/", 1)[-1]
        return build_listing(external_id, "detail", url=url)

    async def detect_new_listings(self, zone: str, since_ids: set[str]) -> list[str]:
        del since_ids
        return [f"https://example.com/{zone}-new"]


@pytest.fixture
def spider_config() -> Config:
    return Config(
        kafka_brokers="localhost:9092",
        kafka_topic_prefix="estategap.",
        kafka_max_retries=3,
        redis_url="redis://localhost:6379/0",
        proxy_manager_addr="localhost:50051",
        idealista_api_token="token",
        request_min_delay=0,
        request_max_delay=0,
        user_agent_seed=123,
    )


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def fake_js() -> FakeJetStream:
    return FakeJetStream()
