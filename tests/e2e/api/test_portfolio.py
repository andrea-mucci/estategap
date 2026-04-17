from __future__ import annotations

import pytest

from tests.e2e.helpers.fixtures import prefixed_name


pytestmark = [pytest.mark.api]


def _portfolio_payload(address: str) -> dict[str, object]:
    return {
        "address": address,
        "country": "ES",
        "purchase_price": 250000,
        "purchase_currency": "EUR",
        "purchase_date": "2024-01-15",
        "monthly_rental_income": 1450,
        "area_m2": 92,
        "property_type": "residential",
        "notes": "Created by E2E suite",
    }


@pytest.mark.asyncio
async def test_portfolio_create_list_update_and_delete(authed_client, test_run_id: str) -> None:
    owner = authed_client("pro")
    other = authed_client("global")

    created = await owner.post(
        "/api/v1/portfolio/properties",
        json=_portfolio_payload(prefixed_name(test_run_id, "portfolio-address")),
    )
    assert created.status_code == 201, created.text
    property_id = created.json()["id"]

    listed = await owner.get("/api/v1/portfolio/properties")
    assert listed.status_code == 200, listed.text
    assert any(item["id"] == property_id for item in listed.json()["properties"])

    updated = await owner.put(
        f"/api/v1/portfolio/properties/{property_id}",
        json={**_portfolio_payload(prefixed_name(test_run_id, "portfolio-address-updated")), "notes": "Updated"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["notes"] == "Updated"

    forbidden = await other.delete(f"/api/v1/portfolio/properties/{property_id}")
    assert forbidden.status_code == 403, forbidden.text

    deleted = await owner.delete(f"/api/v1/portfolio/properties/{property_id}")
    assert deleted.status_code == 204, deleted.text
