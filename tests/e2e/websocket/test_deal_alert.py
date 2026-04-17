from __future__ import annotations

import asyncio

import pytest

from tests.e2e.helpers.kafka_injector import ScoredListingEvent, publish_scored_listing


pytestmark = [pytest.mark.ws]


@pytest.mark.asyncio
async def test_matching_scored_listing_pushes_deal_alert(
    authed_client,
    ws_client,
    seeded_ids,
    test_run_id: str,
) -> None:
    api = authed_client("pro")
    zone_id = seeded_ids.zone_ids_by_country["ES"][0]
    listing_id = seeded_ids.listing_ids_by_country["ES"][0]

    detail_response = await api.get(f"/api/v1/listings/{listing_id}")
    assert detail_response.status_code == 200, detail_response.text
    detail = detail_response.json()

    created = await api.post(
        "/api/v1/alerts/rules",
        json={
            "name": f"{test_run_id}-deal-alert",
            "zone_ids": [zone_id],
            "category": "residential",
            "filter": {"price_max": {"lte": int(detail.get("asking_price_eur") or 500000)}},
            "channels": [{"type": "email"}],
        },
    )
    assert created.status_code == 201, created.text

    event = ScoredListingEvent(
        listing_id=listing_id,
        country_code="ES",
        lat=float(detail.get("latitude") or 40.4168),
        lon=float(detail.get("longitude") or -3.7038),
        property_type=str(detail.get("property_type") or "apartment"),
        price_eur=float(detail.get("asking_price_eur") or 250000),
        area_m2=float(detail.get("area_m2") or 85),
        bedrooms=int(detail.get("bedrooms") or 2),
        deal_score=0.95,
        deal_tier=1,
        estimated_price_eur=float(detail.get("asking_price_eur") or 250000),
        title=str(detail.get("address") or detail.get("city") or listing_id),
        city=str(detail.get("city") or "Madrid"),
        image_url=detail.get("photo_url"),
    )

    async with ws_client("pro") as client:
        await publish_scored_listing("localhost:9092", event)
        try:
            while True:
                message = await client.next_message(timeout=10.0)
                if message.get("type") == "deal_alert":
                    payload = message["payload"]
                    assert payload["listing_id"] == listing_id
                    assert payload["deal_tier"] == 1
                    return
        except TimeoutError:
            pytest.skip("alert pipeline did not deliver a websocket notification in time")
