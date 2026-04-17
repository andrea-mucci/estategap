from __future__ import annotations

import asyncio

import pytest

from tests.e2e.helpers.assertions import assert_rate_limit_headers


pytestmark = [pytest.mark.api, pytest.mark.slow]


LIMITS = {
    "free": 30,
    "basic": 120,
    "pro": 300,
    "global": 600,
    "api": 1200,
}


@pytest.mark.asyncio
@pytest.mark.parametrize("tier,limit", LIMITS.items(), ids=list(LIMITS))
async def test_per_tier_rate_limits(authed_client, tier: str, limit: int) -> None:
    client = authed_client(tier)
    requests = [
        client.get("/api/v1/listings", params={"country": "ES", "limit": 1})
        for _ in range(limit + 2)
    ]
    responses = await asyncio.gather(*requests)
    okay = sum(1 for response in responses if response.status_code == 200)
    assert okay >= limit, [response.status_code for response in responses[-5:]]
    limited = next((response for response in responses if response.status_code == 429), None)
    assert limited is not None, [response.status_code for response in responses[-5:]]
    assert_rate_limit_headers(limited)
