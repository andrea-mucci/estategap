from __future__ import annotations

import pytest

from tests.e2e.helpers.fixtures import SeededIDs, prefixed_name, require_items


pytestmark = [pytest.mark.api]


def _alert_payload(name: str, zone_id: str) -> dict[str, object]:
    return {
        "name": name,
        "zone_ids": [zone_id],
        "category": "residential",
        "filter": {
            "price_max": {"lte": 500000},
            "bedrooms": {"gte": 2},
        },
        "channels": [{"type": "email"}],
    }


@pytest.mark.asyncio
async def test_alert_rule_crud_and_history(authed_client, seeded_ids: SeededIDs, test_run_id: str) -> None:
    pro = authed_client("pro")
    other = authed_client("global")
    zone_id = require_items(seeded_ids.zone_ids_by_country["ES"], "ES zone ids")[0]

    created = await pro.post(
        "/api/v1/alerts/rules",
        json=_alert_payload(prefixed_name(test_run_id, "rule"), zone_id),
    )
    assert created.status_code == 201, created.text
    rule = created.json()
    assert rule["zone_ids"] == [zone_id]

    listed = await pro.get("/api/v1/alerts/rules", params={"page": 1, "page_size": 20})
    assert listed.status_code == 200, listed.text
    assert any(item["id"] == rule["id"] for item in listed.json()["data"])

    updated = await pro.put(
        f"/api/v1/alerts/rules/{rule['id']}",
        json={"name": prefixed_name(test_run_id, "updated-rule")},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["name"].endswith("updated-rule")

    forbidden = await other.put(
        f"/api/v1/alerts/rules/{rule['id']}",
        json={"name": prefixed_name(test_run_id, "forbidden")},
    )
    assert forbidden.status_code in (403, 404), forbidden.text

    history = await pro.get("/api/v1/alerts/history")
    assert history.status_code == 200, history.text
    assert isinstance(history.json()["data"], list)

    deleted = await pro.delete(f"/api/v1/alerts/rules/{rule['id']}")
    assert deleted.status_code == 204, deleted.text


@pytest.mark.asyncio
async def test_free_tier_cannot_create_alert_rules(authed_client, seeded_ids: SeededIDs, test_run_id: str) -> None:
    free = authed_client("free")
    zone_id = require_items(seeded_ids.zone_ids_by_country["ES"], "ES zone ids")[0]
    response = await free.post(
        "/api/v1/alerts/rules",
        json=_alert_payload(prefixed_name(test_run_id, "free-rule"), zone_id),
    )
    assert response.status_code == 403, response.text
    payload = response.json()
    assert payload["code"] == "TIER_NOT_PERMITTED"
