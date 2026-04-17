"""ScoringResult and SHAP attribution models."""

from __future__ import annotations

from decimal import Decimal
from enum import IntEnum
from uuid import UUID

from pydantic import field_validator

from ._base import AwareDatetime, EstateGapModel, validate_country_code


class DealTier(IntEnum):
    """Discrete deal quality buckets emitted by the scorer."""

    GREAT_DEAL = 1
    GOOD_DEAL = 2
    FAIR = 3
    OVERPRICED = 4


class ShapValue(EstateGapModel):
    """Top-N SHAP attribution value for a scored listing."""

    feature_name: str
    value: float


class ScoringResult(EstateGapModel):
    """ML scoring payload merged into a persisted listing."""

    listing_id: UUID
    country: str
    estimated_price: Decimal
    deal_score: Decimal
    deal_tier: DealTier
    confidence_low: Decimal
    confidence_high: Decimal
    shap_features: list[ShapValue]
    model_version: str
    scored_at: AwareDatetime

    @field_validator("country")
    @classmethod
    def _validate_country(cls, value: str) -> str:
        return validate_country_code(value)


__all__ = ["DealTier", "ScoringResult", "ShapValue"]
