from __future__ import annotations

import pytest

from tests.e2e.helpers.assertions import assert_error_shape


pytestmark = [pytest.mark.api]


@pytest.mark.asyncio
async def test_subscription_me_checkout_and_portal(authed_client) -> None:
    free = authed_client("free")

    me_response = await free.get("/api/v1/subscriptions/me")
    assert me_response.status_code == 200, me_response.text
    assert "tier" in me_response.json()

    checkout_response = await free.post(
        "/api/v1/subscriptions/checkout",
        json={"tier": "basic", "billing_period": "monthly"},
    )
    if checkout_response.status_code == 500:
        pytest.skip("Stripe checkout is not configured in this local environment")
    assert checkout_response.status_code == 200, checkout_response.text
    assert checkout_response.json()["checkout_url"]

    portal_response = await free.post("/api/v1/subscriptions/portal", json={})
    if portal_response.status_code == 500:
        pytest.skip("Stripe portal is not configured in this local environment")
    assert portal_response.status_code in (200, 400), portal_response.text


@pytest.mark.asyncio
async def test_subscription_rejects_invalid_payloads(authed_client) -> None:
    client = authed_client("free")

    invalid_tier = await client.post(
        "/api/v1/subscriptions/checkout",
        json={"tier": "free", "billing_period": "monthly"},
    )
    assert_error_shape(invalid_tier, 400)

    invalid_period = await client.post(
        "/api/v1/subscriptions/checkout",
        json={"tier": "basic", "billing_period": "weekly"},
    )
    assert_error_shape(invalid_period, 400)
