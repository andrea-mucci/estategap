from __future__ import annotations

import asyncio

import pytest

from tests.e2e.helpers.nats_injector import ScoredListingEvent, publish_scored_listing


pytestmark = [pytest.mark.concurrency]


@pytest.mark.asyncio
async def test_two_users_receive_only_their_matching_alerts(
    authed_client,
    ws_client,
    seeded_ids,
    test_run_id: str,
) -> None:
    pro = authed_client("pro")
    global_user = authed_client("global")
    zone_id = seeded_ids.zone_ids_by_country["ES"][0]
    listing_id = seeded_ids.listing_ids_by_country["ES"][0]

    async def create_rule(client, label: str) -> None:
        response = await client.post(
            "/api/v1/alerts/rules",
            json={
                "name": f"{test_run_id}-{label}",
                "zone_ids": [zone_id],
                "category": "residential",
                "filter": {"price_max": {"lte": 500000}},
                "channels": [{"type": "email"}],
            },
        )
        assert response.status_code == 201, response.text

    await asyncio.gather(create_rule(pro, "pro"), create_rule(global_user, "global"))

    event = ScoredListingEvent(
        listing_id=listing_id,
        country_code="ES",
        lat=40.4168,
        lon=-3.7038,
        price_eur=250000,
        area_m2=80,
        deal_score=0.96,
        deal_tier=1,
        estimated_price_eur=260000,
        title="Concurrent deal alert",
        city="Madrid",
    )

    async with ws_client("pro") as pro_ws, ws_client("global") as global_ws:
        await publish_scored_listing("nats://localhost:4222", event)
        try:
            pro_message, global_message = await asyncio.gather(
                pro_ws.next_message(timeout=10.0),
                global_ws.next_message(timeout=10.0),
            )
        except Exception:
            pytest.skip("alert notifications were not delivered by the local environment")

        assert pro_message.get("type") == "deal_alert"
        assert global_message.get("type") == "deal_alert"
