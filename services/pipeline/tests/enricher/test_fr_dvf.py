from __future__ import annotations

from datetime import date
from decimal import Decimal

import pytest

from pipeline.enricher.fr_dvf import FranceDVFEnricher
from tests.enricher.conftest import FakePool, listing_factory


@pytest.mark.asyncio
async def test_spatial_match_returns_median_price() -> None:
    pool = FakePool(
        rows=[
            {"date_mutation": date(2025, 3, 1), "valeur_fonciere": 580000, "surface_reelle_bati": 80, "type_local": "Appartement"},
            {"date_mutation": date(2024, 2, 1), "valeur_fonciere": 600000, "surface_reelle_bati": 100, "type_local": "Appartement"},
        ]
    )
    enricher = FranceDVFEnricher(pool=pool)

    result = await enricher.enrich(listing_factory())

    assert result.status == "completed"
    assert result.updates["dvf_nearby_count"] == 2
    assert result.updates["dvf_median_price_m2"] == Decimal("6625.00")


@pytest.mark.asyncio
async def test_no_match_when_no_rows_within_radius() -> None:
    enricher = FranceDVFEnricher(pool=FakePool(rows=[]))

    result = await enricher.enrich(listing_factory())

    assert result.status == "no_match"
    assert result.updates["dvf_nearby_count"] == 0

