"""Kafka publisher helpers for ML scoring events."""

from __future__ import annotations

from typing import Any

from estategap_common.broker import KafkaBroker
from estategap_common.models import ScoredListingEvent, ShapFeatureEvent


def build_scored_listing_event(result: Any) -> ScoredListingEvent:
    """Translate a scoring result into the shared event model."""

    return ScoredListingEvent(
        listing_id=result.listing_id,
        country_code=result.country.upper(),
        estimated_price_eur=result.estimated_price,
        deal_score=result.deal_score,
        deal_tier=result.deal_tier,
        confidence_low_eur=result.confidence_low,
        confidence_high_eur=result.confidence_high,
        model_version=result.model_version,
        scoring_method=result.scoring_method,
        model_confidence=result.model_confidence,
        scored_at=result.scored_at,
        shap_features=[
            ShapFeatureEvent(
                feature=value.feature_name,
                value=value.value,
                shap_value=value.contribution,
                label=value.label,
            )
            for value in result.shap_features
        ],
    )


async def publish_scored_listing(broker: KafkaBroker, result: Any) -> None:
    """Publish a scored-listing event to Kafka."""

    event = build_scored_listing_event(result)
    await broker.publish(
        "scored-listings",
        result.country.upper(),
        event.model_dump_json().encode("utf-8"),
    )


__all__ = ["build_scored_listing_event", "publish_scored_listing"]
