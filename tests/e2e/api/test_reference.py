from __future__ import annotations

import pytest


pytestmark = [pytest.mark.api]


@pytest.mark.asyncio
async def test_reference_endpoints_return_non_empty_payloads(authed_client) -> None:
    client = authed_client("global")

    countries = await client.get("/api/v1/countries")
    assert countries.status_code == 200, countries.text
    countries_payload = countries.json()
    assert countries_payload
    assert {"code", "name"}.issubset(countries_payload[0])

    portals = await client.get("/api/v1/portals")
    assert portals.status_code == 200, portals.text
    portals_payload = portals.json()
    assert portals_payload
    assert {"id", "name", "country_code"}.issubset(portals_payload[0])
