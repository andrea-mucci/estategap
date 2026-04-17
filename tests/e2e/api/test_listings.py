from __future__ import annotations

import pytest

from tests.e2e.helpers.assertions import assert_error_shape, assert_pagination
from tests.e2e.helpers.fixtures import SeededIDs, require_items


pytestmark = [pytest.mark.api]


@pytest.mark.asyncio
async def test_listings_support_filters_currency_and_top_deals(
    authed_client,
    seeded_ids: SeededIDs,
) -> None:
    pro = authed_client("pro")
    free = authed_client("free")
    basic = authed_client("basic")

    response = await pro.get("/api/v1/listings", params={"country": "ES", "limit": 5})
    payload = assert_pagination(response)
    require_items(payload["data"], "ES listings")

    first = payload["data"][0]
    city = first.get("city")
    if city:
        filtered = await pro.get("/api/v1/listings", params={"country": "ES", "city": city, "limit": 5})
        assert filtered.status_code == 200, filtered.text
        assert all(item.get("city") == city for item in filtered.json()["data"])

    price_filtered = await pro.get(
        "/api/v1/listings",
        params={"country": "ES", "min_price_eur": 100000, "max_price_eur": 1000000},
    )
    assert price_filtered.status_code == 200, price_filtered.text

    area_filtered = await pro.get(
        "/api/v1/listings",
        params={"country": "ES", "min_area_m2": 50, "max_area_m2": 500},
    )
    assert area_filtered.status_code == 200, area_filtered.text

    bedroom_filtered = await pro.get(
        "/api/v1/listings",
        params={"country": "ES", "min_bedrooms": 1},
    )
    assert bedroom_filtered.status_code == 200, bedroom_filtered.text

    portal_id = seeded_ids.portal_ids[0]
    portal_filtered = await pro.get(
        "/api/v1/listings",
        params={"country": "ES", "portal_id": portal_id, "sort_by": "price"},
    )
    assert portal_filtered.status_code == 200, portal_filtered.text

    usd_response = await pro.get(
        "/api/v1/listings",
        params={"country": "ES", "currency": "USD", "limit": 3},
    )
    assert usd_response.status_code == 200, usd_response.text
    assert usd_response.headers["X-Currency"] == "USD"

    top_deals = await pro.get("/api/v1/listings/top-deals", params={"country": "ES", "limit": 5})
    top_payload = assert_pagination(top_deals)
    require_items(top_payload["data"], "top deals")

    free_fr = await free.get("/api/v1/listings", params={"country": "FR", "limit": 5})
    assert free_fr.status_code == 200, free_fr.text
    assert free_fr.json()["meta"]["total_count"] == 0

    basic_it = await basic.get("/api/v1/listings", params={"country": "IT", "limit": 5})
    assert basic_it.status_code == 200, basic_it.text
    assert basic_it.json()["meta"]["total_count"] == 0


@pytest.mark.asyncio
async def test_listing_detail_known_and_unknown_ids(authed_client, seeded_ids: SeededIDs) -> None:
    client = authed_client("global")
    listing_id = require_items(seeded_ids.listing_ids_by_country["ES"], "ES listing ids")[0]

    detail_response = await client.get(f"/api/v1/listings/{listing_id}")
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["id"] == listing_id

    unknown_response = await client.get("/api/v1/listings/00000000-0000-0000-0000-000000000000")
    assert_error_shape(unknown_response, 404, message_contains="listing not found")
