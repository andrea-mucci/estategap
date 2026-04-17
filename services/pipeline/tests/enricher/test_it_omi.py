from __future__ import annotations

from decimal import Decimal

import pytest

from pipeline.enricher.it_omi import ItalyOMIEnricher
from tests.enricher.conftest import FakePool, listing_factory


@pytest.mark.asyncio
async def test_zone_match_computes_price_vs_omi() -> None:
    pool = FakePool(
        row={
            "zona_omi": "B1",
            "period": "2024-H2",
            "price_min": Decimal("3500"),
            "price_max": Decimal("4500"),
        }
    )
    enricher = ItalyOMIEnricher(pool=pool)
    listing = listing_factory(
        country="IT",
        source="immobiliare",
        asking_price=Decimal("360000"),
        asking_price_eur=Decimal("360000"),
        built_area_m2=Decimal("90"),
        location_wkt="POINT(12.4964 41.9028)",
    )

    result = await enricher.enrich(listing)

    assert result.status == "completed"
    assert result.updates["omi_zone_code"] == "B1"
    assert result.updates["price_vs_omi"] == Decimal("1.0000")


@pytest.mark.asyncio
async def test_no_match_when_listing_outside_all_zones() -> None:
    enricher = ItalyOMIEnricher(pool=FakePool(row=None))

    result = await enricher.enrich(listing_factory(country="IT", source="immobiliare"))

    assert result.status == "no_match"

