from __future__ import annotations

import json

import pytest

from estategap_spiders.spiders.it_immobiliare import ImmobiliareSpider
from estategap_spiders.spiders.it_immobiliare_parser import parse_detail_page
from tests.spiders.conftest import read_fixture


def _completeness_ratio(payload: dict[str, object]) -> float:
    required = {
        "prezzo",
        "superficie",
        "locali",
        "bagni",
        "tipologia",
        "classeEnergetica",
        "latitudine",
        "longitudine",
        "url",
        "indirizzo",
    }
    present = sum(1 for key in required if payload.get(key) not in {None, ""})
    return present / len(required)


@pytest.mark.asyncio
async def test_scrape_search_page_parses_api_fixture(spider_config) -> None:
    spider = ImmobiliareSpider(spider_config)
    fixture = json.loads(read_fixture("it_immobiliare_search.json"))

    async def fake_fetch_api_page(zone: str, page: int) -> dict:
        assert zone == "roma"
        assert page == 1
        return fixture

    spider._fetch_api_page = fake_fetch_api_page  # type: ignore[method-assign]

    listings = await spider.scrape_search_page("roma", 1)

    assert len(listings) == 3
    assert listings[0].raw_json["tipologia"] == "appartamento"
    assert listings[1].raw_json["tipologia"] == "villa"
    assert listings[2].raw_json["tipologia"] == "ufficio"
    assert _completeness_ratio(listings[0].raw_json) >= 0.75


@pytest.mark.asyncio
async def test_scrape_search_page_uses_html_fallback(spider_config) -> None:
    spider = ImmobiliareSpider(spider_config)

    async def fake_fetch_api_page(zone: str, page: int) -> dict:
        del zone, page
        return {}

    async def fake_fetch_html_page(url: str) -> str:
        del url
        return """
        <html><body>
          <article data-listing='{"price": 250000, "surface": 85, "rooms": 4, "bathrooms": 2, "propertyType": "appartamento", "latitude": 41.9, "longitude": 12.4, "url": "/annunci/1001/", "address": "Via Roma 1", "city": "Roma", "province": "RM", "postalCode": "00100"}'></article>
        </body></html>
        """

    spider._fetch_api_page = fake_fetch_api_page  # type: ignore[method-assign]
    spider._fetch_html_page = fake_fetch_html_page  # type: ignore[method-assign]

    listings = await spider.scrape_search_page("roma", 1)

    assert len(listings) == 1
    assert listings[0].raw_json["url"] == "https://www.immobiliare.it/annunci/1001/"


def test_parse_detail_page_extracts_json_ld() -> None:
    payload = parse_detail_page(read_fixture("it_immobiliare_detail.html"))

    assert payload["prezzo"] == 25_000_000
    assert payload["locali"] == 4
    assert payload["codicePostale"] == "00100"
