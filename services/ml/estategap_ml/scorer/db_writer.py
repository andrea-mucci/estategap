"""Database write helpers for scorer results."""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from estategap_common.models import ScoringResult


def _shap_payload(result: ScoringResult) -> str:
    return json.dumps(
        [
            {
                "feature": value.feature_name,
                "value": value.value,
                "shap_value": value.contribution,
                "label": value.label,
            }
            for value in result.shap_features
        ]
    )


def _row(result: ScoringResult) -> tuple[Any, ...]:
    return (
        result.estimated_price,
        result.deal_score,
        int(result.deal_tier),
        result.confidence_low,
        result.confidence_high,
        result.model_version,
        result.scored_at,
        _shap_payload(result),
        list(result.comparable_ids),
        result.listing_id,
        result.country.upper(),
    )


async def write_scores(pool: Any, results: Sequence[ScoringResult]) -> None:
    """Persist a batch of scorer outputs back into the listings table."""

    if not results:
        return
    async with pool.acquire() as conn:
        await conn.executemany(
            """
            UPDATE listings
            SET
                estimated_price_eur = $1,
                deal_score = $2,
                deal_tier = $3,
                confidence_low_eur = $4,
                confidence_high_eur = $5,
                model_version = $6,
                scored_at = $7,
                shap_features = $8::jsonb,
                comparable_ids = $9::uuid[]
            WHERE id = $10
              AND country = $11
            """,
            [_row(result) for result in results],
        )


__all__ = ["write_scores"]
