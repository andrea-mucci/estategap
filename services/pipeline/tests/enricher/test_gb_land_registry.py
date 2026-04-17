from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from pipeline.enricher.gb_land_registry import UKLandRegistryEnricher
from tests.enricher.conftest import FakePool, listing_factory


@pytest.mark.asyncio
async def test_rapidfuzz_match_returns_most_recent_transaction() -> None:
    pool = FakePool(
        rows=[
            {
                "transaction_uid": "00000000-0000-0000-0000-000000000001",
                "price_gbp": 475000,
                "date_transfer": date(2024, 9, 20),
                "address_normalized": "21 baker st london nw1 6xe",
            }
        ]
    )
    enricher = UKLandRegistryEnricher(pool=pool)
    listing = listing_factory(
        country="GB",
        source="rightmove",
        postal_code="NW1 6XE",
        address="21 Baker Street",
        location_wkt="POINT(-0.1585 51.5237)",
        asking_price=Decimal("475000"),
        asking_price_eur=Decimal("555750"),
    )

    result = await enricher.enrich(listing)

    assert result.status == "completed"
    assert result.updates["uk_lr_match_count"] == 1
    assert result.updates["uk_lr_last_price_gbp"] == 475000
    assert result.updates["uk_lr_last_date"] == date(2024, 9, 20)


@pytest.mark.asyncio
async def test_no_match_for_unrecognized_address() -> None:
    pool = FakePool(
        rows=[
            {
                "transaction_uid": "00000000-0000-0000-0000-000000000001",
                "price_gbp": 475000,
                "date_transfer": date(2024, 9, 20),
                "address_normalized": "99 other road london nw1 6xe",
            }
        ]
    )
    enricher = UKLandRegistryEnricher(pool=pool)

    result = await enricher.enrich(
        listing_factory(country="GB", source="rightmove", postal_code="NW1 6XE", address="21 Baker Street")
    )

    assert result.status == "no_match"
    assert result.updates["uk_lr_match_count"] == 0

