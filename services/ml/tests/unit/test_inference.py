from __future__ import annotations

from uuid import uuid4

import pytest

pytest.importorskip("numpy")
pytest.importorskip("pandas")

from estategap_common.models import DealTier
from estategap_ml.scorer.inference import score_listing

from tests.scorer_support import build_fake_bundle


@pytest.mark.parametrize(
    ("estimated", "asking", "expected_score", "expected_tier"),
    [
        (100.0, 80.0, 20.0, DealTier.GREAT_DEAL),
        (100.0, 90.0, 10.0, DealTier.GOOD_DEAL),
        (100.0, 102.0, -2.0, DealTier.FAIR),
        (100.0, 110.0, -10.0, DealTier.OVERPRICED),
    ],
)
def test_deal_score_calculation(
    estimated: float,
    asking: float,
    expected_score: float,
    expected_tier: DealTier,
) -> None:
    bundle = build_fake_bundle(point=estimated, q05=estimated * 0.9, q95=estimated * 1.1)
    result = score_listing(
        bundle,
        {
            "id": uuid4(),
            "country": "ES",
            "asking_price_eur": asking,
            "built_area_m2": 85,
            "bedrooms": 3,
        },
    )

    assert float(result.deal_score) == pytest.approx(expected_score)
    assert result.deal_tier is expected_tier


@pytest.mark.parametrize(
    ("asking", "expected_tier"),
    [
        (85.0, DealTier.GREAT_DEAL),
        (95.0, DealTier.GOOD_DEAL),
        (105.0, DealTier.FAIR),
        (106.0, DealTier.OVERPRICED),
    ],
)
def test_deal_tier_boundaries(asking: float, expected_tier: DealTier) -> None:
    bundle = build_fake_bundle(point=100.0, q05=90.0, q95=110.0)
    result = score_listing(
        bundle,
        {
            "id": uuid4(),
            "country": "ES",
            "asking_price_eur": asking,
            "built_area_m2": 85,
            "bedrooms": 3,
        },
    )

    assert result.deal_tier is expected_tier
