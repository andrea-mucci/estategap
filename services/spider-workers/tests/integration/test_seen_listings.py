from __future__ import annotations

import pytest
import redis.asyncio as redis

from estategap_spiders.spiders.base import BaseSpider


testcontainers = pytest.importorskip("testcontainers.redis")


class SeenSpider(BaseSpider):
    COUNTRY = "ES"
    PORTAL = "seen-fixture"

    def __init__(self, config) -> None:
        super().__init__(config)
        self._runs = 0

    async def scrape_search_page(self, zone: str, page: int):
        return []

    async def scrape_listing_detail(self, url: str):
        return None

    async def detect_new_listings(self, zone: str, since_ids: set[str]) -> list[str]:
        del since_ids
        self._runs += 1
        upper_bound = 5 if self._runs == 1 else 6
        ids = {str(index) for index in range(1, upper_bound + 1)}
        new_ids = await self._filter_new(self.redis, zone, ids)
        return [f"https://example.com/{listing_id}" for listing_id in sorted(new_ids)]


@pytest.mark.asyncio
async def test_seen_listing_tracking(spider_config) -> None:
    container = testcontainers.RedisContainer("redis:7-alpine")
    try:
        container.start()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Docker is not available for Redis integration test: {exc}")
    try:
        redis_url = container.get_connection_url()
        config = spider_config.model_copy(update={"redis_url": redis_url})
        spider = SeenSpider(config)
        zone = "madrid-centro"

        first_urls = await spider.detect_new_listings(zone, set())
        await spider._mark_seen(spider.redis, zone, {url.rsplit("/", 1)[-1] for url in first_urls})

        second_urls = await spider.detect_new_listings(zone, set())
        await spider._mark_seen(spider.redis, zone, {url.rsplit("/", 1)[-1] for url in second_urls})

        redis_client = redis.from_url(redis_url, decode_responses=True)
        seen_key = f"seen:{spider.PORTAL.lower()}:{spider.COUNTRY.lower()}:{zone}"
        assert len(first_urls) == 5
        assert await redis_client.scard(seen_key) == 6
        assert second_urls == ["https://example.com/6"]

        await redis_client.aclose()
        await spider.close()
    finally:
        container.stop()
