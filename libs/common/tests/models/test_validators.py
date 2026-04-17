from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from estategap_common.models import DealTier, NormalizedListing, ScoringResult, User
from estategap_common.models._base import validate_country_code, validate_currency_code


def _aware_datetime() -> datetime:
    return datetime(2026, 4, 17, 8, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(("value", "expected"), [("ES", "ES"), ("US", "US")])
def test_validate_country_code_accepts_valid_values(value: str, expected: str) -> None:
    assert validate_country_code(value) == expected


@pytest.mark.parametrize("value", ["XX", "es"])
def test_validate_country_code_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError, match="Unsupported ISO 3166-1 alpha-2 code"):
        validate_country_code(value)


@pytest.mark.parametrize(("value", "expected"), [("EUR", "EUR"), ("USD", "USD")])
def test_validate_currency_code_accepts_valid_values(value: str, expected: str) -> None:
    assert validate_currency_code(value) == expected


@pytest.mark.parametrize("value", ["ZZZ", "eur"])
def test_validate_currency_code_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError, match="Unsupported ISO 4217 alpha-3 code"):
        validate_currency_code(value)


@pytest.mark.parametrize(
    ("factory", "expected_error"),
    [
        (
            lambda: NormalizedListing(
                id=uuid4(),
                country="ES",
                source="idealista",
                source_id="listing-123",
                source_url="https://www.idealista.com/inmueble/listing-123/",
                asking_price=Decimal("450000"),
                currency="EUR",
                asking_price_eur=Decimal("450000"),
                built_area_m2=Decimal("80"),
                first_seen_at=datetime(2026, 4, 17, 8, 0),
                last_seen_at=_aware_datetime(),
            ),
            "timezone",
        ),
        (
            lambda: ScoringResult(
                listing_id=UUID("550e8400-e29b-41d4-a716-446655440000"),
                country="ES",
                estimated_price=Decimal("420000"),
                deal_score=Decimal("72.5"),
                deal_tier=DealTier.GOOD_DEAL,
                confidence_low=Decimal("395000"),
                confidence_high=Decimal("445000"),
                shap_features=[{"feature_name": "area_m2", "value": 8102.3}],
                model_version="es-lgbm-v2.1.0",
                scored_at=datetime(2026, 4, 17, 8, 0),
            ),
            "timezone",
        ),
        (
            lambda: User(
                id=uuid4(),
                email="user@example.com",
                created_at=datetime(2026, 4, 17, 8, 0),
                updated_at=_aware_datetime(),
            ),
            "timezone",
        ),
    ],
)
def test_aware_datetime_fields_reject_naive_values(factory, expected_error: str) -> None:
    with pytest.raises(ValidationError, match=expected_error):
        factory()
