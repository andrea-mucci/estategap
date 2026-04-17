from __future__ import annotations

import asyncio

import pytest


pytestmark = [pytest.mark.concurrency]


@pytest.mark.asyncio
async def test_two_users_can_search_concurrently(authed_client) -> None:
    pro = authed_client("pro")
    global_user = authed_client("global")

    first, second = await asyncio.gather(
        pro.get("/api/v1/listings", params={"country": "ES", "limit": 5}),
        global_user.get("/api/v1/listings", params={"country": "ES", "limit": 5}),
    )
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    assert first.json()["meta"]["total_count"] == second.json()["meta"]["total_count"]
