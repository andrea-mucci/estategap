from __future__ import annotations

import pytest

from estategap_spiders.spiders.es_idealista import IdealistaSpider


def sample_api_element(index: int) -> dict:
    return {
        "propertyCode": f"ID-{index}",
        "price": 350000 + index,
        "currency": "EUR",
        "size": 95.5,
        "rooms": 3,
        "bathrooms": 2,
        "floor": "3ª planta",
        "hasLift": True,
        "parkingSpace": {"hasParkingSpace": True, "parkingSpaceCount": 1},
        "hasTerrace": True,
        "orientation": "south",
        "status": "good",
        "constructionYear": 2004,
        "energyCertification": {"energyConsumption": {"rating": "B", "value": 72.4}},
        "latitude": 40.4168,
        "longitude": -3.7038,
        "multimedia": {"images": [{"url": "https://img.example/1.jpg"}]},
        "description": "Bright flat",
        "suggestedTexts": {"title": "Flat in Madrid"},
        "contact": {"agency": {"name": "Agency", "id": "agency-1"}},
        "url": f"/inmueble/{1000 + index}/",
        "propertyType": "residential",
        "operation": "sale",
    }


SEARCH_HTML = """
<html>
  <body>
    <article class="item">
      <div class="item-info-container">
        <a class="item-link" href="/inmueble/123456/"></a>
        <span class="item-price">350.000 €</span>
        <span class="item-detail-char">95 m²</span>
      </div>
    </article>
  </body>
</html>
"""


DETAIL_HTML = """
<html>
  <head>
    <meta property="og:title" content="Flat in Madrid" />
    <script type="application/ld+json">
      {"geo": {"latitude": 40.4168, "longitude": -3.7038}}
    </script>
  </head>
  <body>
    <div class="price-features__container"><span>350.000 €</span></div>
    <div class="info-features">
      <span>95 m²</span>
      <span>3 hab.</span>
      <span>2 baños</span>
      <span>Planta 3ª</span>
    </div>
    <div class="comment"><p>Bright flat</p></div>
    <div class="professional-name">Agency</div>
    <img src="https://img3.idealista.com/1.jpg" />
  </body>
</html>
"""


def test_map_api_response_maps_non_null_fields(spider_config) -> None:
    spider = IdealistaSpider(spider_config)
    listing = spider._map_api_response(sample_api_element(1), "madrid-centro")

    assert listing.external_id == "ID-1"
    assert listing.raw_json["price"] == 35_000_100
    assert listing.raw_json["area_m2"] == 95.5
    assert listing.raw_json["rooms"] == 3
    assert listing.raw_json["bathrooms"] == 2
    assert listing.raw_json["latitude"] == 40.4168
    assert listing.raw_json["photos"] == ["https://img.example/1.jpg"]
    assert listing.raw_json["agent_name"] == "Agency"


def test_parse_search_html_returns_listing_urls(spider_config) -> None:
    spider = IdealistaSpider(spider_config)
    listings = spider._parse_search_html(SEARCH_HTML, "madrid-centro")

    assert [listing.raw_json["listing_url"] for listing in listings] == [
        "https://www.idealista.com/inmueble/123456/",
    ]


@pytest.mark.asyncio
async def test_scrape_search_page_returns_empty_list_when_api_empty(spider_config, monkeypatch) -> None:
    spider = IdealistaSpider(spider_config)

    async def fake_fetch_api_page(zone, page, extra_payload=None) -> dict:
        del zone, page, extra_payload
        return {"elementList": []}

    monkeypatch.setattr(spider, "_fetch_api_page", fake_fetch_api_page)

    listings = await spider.scrape_search_page("madrid-centro", 1)

    assert listings == []


def test_scrape_listing_detail_extracts_gps(spider_config) -> None:
    spider = IdealistaSpider(spider_config)
    listing = spider._parse_detail_html(DETAIL_HTML, "https://www.idealista.com/inmueble/123456/")

    assert listing.raw_json["latitude"] == 40.4168
    assert listing.raw_json["longitude"] == -3.7038
