from __future__ import annotations

import pytest

from tests.e2e.helpers.assertions import assert_error_shape, assert_pagination
from tests.e2e.helpers.fixtures import SeededIDs, prefixed_name, require_items


pytestmark = [pytest.mark.api]


def _custom_zone_payload(name: str) -> dict[str, object]:
    return {
        "name": name,
        "type": "custom",
        "country": "ES",
        "geometry": {
            "type": "Polygon",
            "coordinates": [
                [
                    [-3.71, 40.41],
                    [-3.70, 40.41],
                    [-3.70, 40.42],
                    [-3.71, 40.42],
                    [-3.71, 40.41],
                ]
            ],
        },
    }


@pytest.mark.asyncio
async def test_zone_list_detail_stats_compare_and_create(
    authed_client,
    seeded_ids: SeededIDs,
    test_run_id: str,
) -> None:
    client = authed_client("global")

    list_response = await client.get("/api/v1/zones", params={"country": "ES", "limit": 5})
    payload = assert_pagination(list_response)
    zone_ids = require_items(seeded_ids.zone_ids_by_country["ES"], "ES zone ids")
    zone_id = zone_ids[0]

    detail_response = await client.get(f"/api/v1/zones/{zone_id}")
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["id"] == zone_id

    stats_response = await client.get(f"/api/v1/zones/{zone_id}/stats")
    assert stats_response.status_code == 200, stats_response.text

    analytics_response = await client.get(f"/api/v1/zones/{zone_id}/analytics")
    assert analytics_response.status_code == 200, analytics_response.text

    distribution_response = await client.get(f"/api/v1/zones/{zone_id}/price-distribution")
    assert distribution_response.status_code == 200, distribution_response.text

    geometry_response = await client.get(f"/api/v1/zones/{zone_id}/geometry")
    assert geometry_response.status_code == 200, geometry_response.text

    compare_ids = ",".join(zone_ids[:2]) if len(zone_ids) > 1 else zone_id
    compare_response = await client.get("/api/v1/zones/compare", params={"ids": compare_ids})
    assert compare_response.status_code == 200, compare_response.text
    assert compare_response.json()["zones"]

    created = await client.post(
        "/api/v1/zones",
        json=_custom_zone_payload(prefixed_name(test_run_id, "zone")),
    )
    assert created.status_code == 201, created.text
    assert created.json()["type"] == "custom"


@pytest.mark.asyncio
async def test_zone_unknown_and_invalid_payloads(authed_client) -> None:
    client = authed_client("global")

    unknown = await client.get("/api/v1/zones/00000000-0000-0000-0000-000000000000")
    assert_error_shape(unknown, 404, message_contains="zone not found")

    bad_create = await client.post(
        "/api/v1/zones",
        json={"name": "", "type": "bad", "country": "ESP", "geometry": {}},
    )
    assert_error_shape(bad_create, 400)
