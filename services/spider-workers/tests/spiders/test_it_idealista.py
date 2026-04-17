from __future__ import annotations

import json

import pytest

from estategap_spiders.spiders.it_idealista import IdealistaITSpider
from tests.spiders.conftest import read_fixture


@pytest.mark.asyncio
async def test_scrape_search_page_parses_italian_api_fields(spider_config) -> None:
    spider = IdealistaITSpider(spider_config)
    fixture = json.loads(read_fixture("it_idealista_search.json"))

    async def fake_fetch_api_page(zone: str, page: int, extra_payload=None) -> dict:
        del extra_payload
        assert zone == "milano"
        assert page == 1
        return fixture

    spider._fetch_api_page = fake_fetch_api_page  # type: ignore[method-assign]

    listings = await spider.scrape_search_page("milano", 1)

    assert len(listings) == 1
    payload = listings[0].raw_json
    assert payload["tipologiaImmobile"] == "appartamento"
    assert payload["statoImmobile"] == "buono"
    assert payload["riscaldamento"] == "autonomo"


@pytest.mark.asyncio
async def test_detect_new_listings_filters_seen_ids(spider_config, fake_redis) -> None:
    spider = IdealistaITSpider(spider_config)
    spider.redis = fake_redis
    fixture = json.loads(read_fixture("it_idealista_search.json"))

    async def fake_fetch_api_page(zone: str, page: int, extra_payload=None) -> dict:
        del zone, page, extra_payload
        return fixture

    spider._fetch_api_page = fake_fetch_api_page  # type: ignore[method-assign]
    await fake_redis.sadd("seen:idealista:it:milano", "IT-ID-1")

    urls = await spider.detect_new_listings("milano", set())

    assert urls == []

