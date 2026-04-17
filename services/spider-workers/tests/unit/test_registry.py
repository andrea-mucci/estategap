from __future__ import annotations

from estategap_spiders.spiders import REGISTRY, get_spider
from estategap_spiders.spiders.base import BaseSpider


def test_spider_registry_autoregisters_subclasses() -> None:
    class TestSpider(BaseSpider):
        COUNTRY = "ES"
        PORTAL = "test"

        async def scrape_search_page(self, zone: str, page: int):
            return []

        async def scrape_listing_detail(self, url: str):
            return None

        async def detect_new_listings(self, zone: str, since_ids: set[str]):
            return []

    assert REGISTRY[("es", "test")] is TestSpider
    assert get_spider("es", "test") is TestSpider
    assert get_spider("es", "unknown") is None
    assert get_spider("ES", "TEST") is TestSpider
