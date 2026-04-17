from __future__ import annotations

import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

import pytest
from pydantic import ValidationError

from estategap_common.models import DealTier, ScoredListingEvent, ScoringResult


def _aware_datetime() -> datetime:
    return datetime(2026, 4, 17, 8, 0, tzinfo=timezone.utc)


def _scoring_payload() -> dict[str, object]:
    return {
        "listing_id": UUID("550e8400-e29b-41d4-a716-446655440000"),
        "country": "ES",
        "estimated_price": Decimal("420000"),
        "deal_score": Decimal("72.5"),
        "deal_tier": DealTier.GOOD_DEAL,
        "confidence_low": Decimal("395000"),
        "confidence_high": Decimal("445000"),
        "shap_features": [
            {"feature_name": "zone_price_median", "value": 15234.5},
            {"feature_name": "area_m2", "value": 8102.3},
        ],
        "model_version": "es-lgbm-v2.1.0",
        "scored_at": _aware_datetime(),
    }


def test_scoring_result_valid_payload() -> None:
    result = ScoringResult(**_scoring_payload())

    assert result.deal_tier is DealTier.GOOD_DEAL
    assert result.shap_features[0].feature_name == "zone_price_median"


def test_scoring_result_rejects_naive_datetime() -> None:
    payload = _scoring_payload()
    payload["scored_at"] = datetime(2026, 4, 17, 8, 0)

    with pytest.raises(ValidationError, match="timezone"):
        ScoringResult(**payload)


def test_deal_tier_serializes_as_int() -> None:
    payload = json.loads(ScoringResult(**_scoring_payload()).model_dump_json())

    assert payload["deal_tier"] == 2


def test_shap_feature_aliases_are_accepted() -> None:
    payload = _scoring_payload()
    payload["shap_features"] = [
        {
            "feature": "zone_price_median",
            "value": 15234.5,
            "shap_value": 1234.0,
            "label": "Zone median price pushes estimate up",
        }
    ]

    result = ScoringResult(**payload)

    assert result.shap_features[0].feature_name == "zone_price_median"
    assert result.shap_features[0].contribution == pytest.approx(1234.0)


def test_scored_listing_event_valid_payload() -> None:
    event = ScoredListingEvent(
        listing_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        country_code="ES",
        estimated_price_eur=Decimal("420000"),
        deal_score=Decimal("72.5"),
        deal_tier=DealTier.GOOD_DEAL,
        confidence_low_eur=Decimal("395000"),
        confidence_high_eur=Decimal("445000"),
        model_version="es-lgbm-v2.1.0",
        scored_at=_aware_datetime(),
        shap_features=[
            {
                "feature": "zone_price_median",
                "value": 15234.5,
                "shap_value": 1234.0,
                "label": "Zone median price pushes estimate up",
            }
        ],
    )

    assert event.country_code == "ES"
    assert event.shap_features[0].feature == "zone_price_median"
