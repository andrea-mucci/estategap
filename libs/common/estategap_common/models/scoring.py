"""ScoringResult and SHAP attribution models."""

from __future__ import annotations

from decimal import Decimal
from enum import IntEnum
from uuid import UUID

from pydantic import AliasChoices, Field, field_validator

from ._base import AwareDatetime, EstateGapModel, validate_country_code


class DealTier(IntEnum):
    """Discrete deal quality buckets emitted by the scorer."""

    GREAT_DEAL = 1
    GOOD_DEAL = 2
    FAIR = 3
    OVERPRICED = 4


class ShapValue(EstateGapModel):
    """Top-N SHAP attribution value for a scored listing."""

    feature_name: str = Field(validation_alias=AliasChoices("feature_name", "feature"))
    value: float
    contribution: float = Field(
        default=0.0,
        validation_alias=AliasChoices("contribution", "shap_value"),
    )
    label: str = ""


class ShapFeatureEvent(EstateGapModel):
    """Event payload stored in JSONB and published onto NATS."""

    feature: str = Field(validation_alias=AliasChoices("feature", "feature_name"))
    value: float
    shap_value: float = Field(
        default=0.0,
        validation_alias=AliasChoices("shap_value", "contribution"),
    )
    label: str = ""


class ScoringResult(EstateGapModel):
    """ML scoring payload merged into a persisted listing."""

    listing_id: UUID
    country: str
    estimated_price: Decimal
    asking_price: Decimal | None = None
    deal_score: Decimal
    deal_tier: DealTier
    confidence_low: Decimal
    confidence_high: Decimal
    shap_features: list[ShapValue]
    comparable_ids: list[UUID] = Field(default_factory=list)
    model_version: str
    scoring_method: str = "ml"
    model_confidence: str = "full"
    scored_at: AwareDatetime

    @field_validator("country")
    @classmethod
    def _validate_country(cls, value: str) -> str:
        return validate_country_code(value)


class ScoredListingEvent(EstateGapModel):
    """Scored-listing event published after a DB update succeeds."""

    listing_id: UUID
    country_code: str
    estimated_price_eur: Decimal
    deal_score: Decimal
    deal_tier: DealTier
    confidence_low_eur: Decimal
    confidence_high_eur: Decimal
    model_version: str
    scoring_method: str = "ml"
    model_confidence: str = "full"
    scored_at: AwareDatetime
    shap_features: list[ShapFeatureEvent] = Field(default_factory=list)

    @field_validator("country_code")
    @classmethod
    def _validate_country_code(cls, value: str) -> str:
        return validate_country_code(value)


__all__ = [
    "DealTier",
    "ScoredListingEvent",
    "ScoringResult",
    "ShapFeatureEvent",
    "ShapValue",
]
