from __future__ import annotations

import json

import pytest

from estategap_spiders.spiders.es_fotocasa import FotocasaSpider


def listing_payload(listing_id: int) -> dict:
    return {
        "id": listing_id,
        "price": {"amount": 210000 + listing_id},
        "surface": 82.0,
        "usableSurface": 76.0,
        "rooms": 3,
        "bathrooms": 2,
        "floor": 4,
        "hasLift": True,
        "hasParking": True,
        "hasTerrace": True,
        "ubication": {"latitude": 41.3851, "longitude": 2.1734},
        "multimedia": {"images": [{"url": "https://img.example/foto.jpg"}]},
        "description": "Sunny apartment",
        "agency": {"name": "Fotocasa Agency", "id": "agency-1"},
        "energyCertificate": {"energyRating": "A", "energyConsumption": 32.5},
        "detailUrl": f"/es/comprar/vivienda/barcelona/{listing_id}/d",
        "transactionType": "sale",
        "propertyType": "residential",
    }


def next_data(listings: list[dict], *, total_pages: int = 3, detail: dict | None = None) -> str:
    payload = {
        "props": {
            "pageProps": {
                "totalPages": total_pages,
                "initialProps": {"listings": listings, "totalPages": total_pages},
            },
        },
    }
    if detail is not None:
        payload["props"]["pageProps"]["realEstate"] = detail
    return (
        "<html><body><script id=\"__NEXT_DATA__\" type=\"application/json\">"
        + json.dumps(payload)
        + "</script></body></html>"
    )


def test_extract_next_data_parses_json(spider_config) -> None:
    spider = FotocasaSpider(spider_config)
    data = spider._extract_next_data(next_data([listing_payload(1)]))

    assert data["props"]["pageProps"]["totalPages"] == 3


def test_map_listing_maps_fotocasa_fields(spider_config) -> None:
    spider = FotocasaSpider(spider_config)
    listing = spider._map_listing(listing_payload(1), "barcelona")

    assert listing.external_id == "1"
    assert listing.raw_json["price"] == 21_000_100
    assert listing.raw_json["area_m2"] == 82.0
    assert listing.raw_json["has_elevator"] is True
    assert listing.raw_json["latitude"] == 41.3851
    assert listing.raw_json["agent_name"] == "Fotocasa Agency"


@pytest.mark.asyncio
async def test_scrape_search_page_returns_empty_list_when_beyond_total_pages(spider_config, monkeypatch) -> None:
    spider = FotocasaSpider(spider_config)

    async def fake_fetch_html_page(url: str) -> str:
        del url
        return next_data([], total_pages=1)

    monkeypatch.setattr(spider, "_fetch_html_page", fake_fetch_html_page)

    listings = await spider.scrape_search_page("barcelona", 2)

    assert listings == []


@pytest.mark.asyncio
async def test_scrape_listing_detail_merges_detail_fields(spider_config, monkeypatch) -> None:
    spider = FotocasaSpider(spider_config)
    detail = listing_payload(10)

    async def fake_fetch_html_page(url: str) -> str:
        del url
        return next_data([detail], detail=detail)

    monkeypatch.setattr(spider, "_fetch_html_page", fake_fetch_html_page)

    listing = await spider.scrape_listing_detail("https://www.fotocasa.es/detail")

    assert listing is not None
    assert listing.raw_json["description"] == "Sunny apartment"
    assert listing.raw_json["photos"] == ["https://img.example/foto.jpg"]
    assert listing.raw_json["energy_cert"] == "A"
