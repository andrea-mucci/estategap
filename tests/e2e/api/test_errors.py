from __future__ import annotations

import pytest

from tests.e2e.helpers.assertions import assert_error_shape, assert_rate_limit_headers


pytestmark = [pytest.mark.api]


@pytest.mark.asyncio
async def test_common_error_shapes(authed_client) -> None:
    guest = authed_client("free")
    free = authed_client("free")
    basic = authed_client("basic")

    bad_request = await free.get("/api/v1/listings", params={"sort_by": "unsupported"})
    assert_error_shape(bad_request, 400)

    unauthorized = await guest.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid"})
    assert_error_shape(unauthorized, 401)

    forbidden = await basic.get("/api/v1/admin/system/health")
    assert_error_shape(forbidden, 403)

    not_found = await free.get("/api/v1/listings/00000000-0000-0000-0000-000000000000")
    assert_error_shape(not_found, 404)

    conflict_email = "conflict-e2e@example.test"
    first_register = await guest.post(
        "/api/v1/auth/register",
        json={"email": conflict_email, "password": "secret12345"},
    )
    assert first_register.status_code in (201, 409), first_register.text
    second_register = await guest.post(
        "/api/v1/auth/register",
        json={"email": conflict_email, "password": "secret12345"},
    )
    assert_error_shape(second_register, 409)


@pytest.mark.asyncio
async def test_rate_limited_error_shape(authed_client) -> None:
    client = authed_client("free")
    responses = [
        await client.get("/api/v1/listings", params={"country": "ES", "limit": 1})
        for _ in range(35)
    ]
    limited = next(response for response in responses if response.status_code == 429)
    payload = assert_error_shape(limited, 429)
    assert "rate limit" in payload["error"].lower()
    assert_rate_limit_headers(limited)
