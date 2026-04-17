from __future__ import annotations

import asyncio

import pytest

from tests.e2e.helpers.fixtures import prefixed_name


pytestmark = [pytest.mark.concurrency]


def _portfolio_payload(address: str) -> dict[str, object]:
    return {
        "address": address,
        "country": "ES",
        "purchase_price": 240000,
        "purchase_currency": "EUR",
        "purchase_date": "2023-10-01",
        "monthly_rental_income": 1200,
        "area_m2": 80,
        "property_type": "residential",
    }


@pytest.mark.asyncio
async def test_portfolio_update_and_listing_read_can_run_together(
    authed_client,
    seeded_ids,
    test_run_id: str,
) -> None:
    owner = authed_client("pro")
    reader = authed_client("global")
    listing_id = seeded_ids.listing_ids_by_country["ES"][0]

    created = await owner.post(
        "/api/v1/portfolio/properties",
        json=_portfolio_payload(prefixed_name(test_run_id, "crm-concurrency")),
    )
    assert created.status_code == 201, created.text
    property_id = created.json()["id"]

    update_response, detail_response = await asyncio.gather(
        owner.put(
            f"/api/v1/portfolio/properties/{property_id}",
            json={**_portfolio_payload(prefixed_name(test_run_id, "crm-concurrency-updated")), "notes": "Concurrent update"},
        ),
        reader.get(f"/api/v1/listings/{listing_id}"),
    )
    assert update_response.status_code == 200, update_response.text
    assert detail_response.status_code == 200, detail_response.text
