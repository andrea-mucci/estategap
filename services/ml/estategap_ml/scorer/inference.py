"""Core inference logic for the scorer service."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd

from estategap_common.models import DealTier, ScoringResult

from .metrics import SCORER_INFERENCE_DURATION_SECONDS
from .shap_explainer import ShapExplainer


DEAL_TIER_THRESHOLDS = {
    DealTier.GREAT_DEAL: Decimal("15"),
    DealTier.GOOD_DEAL: Decimal("5"),
    DealTier.FAIR: Decimal("-5"),
}


def _row_to_dict(listing_row: Any) -> dict[str, Any]:
    if isinstance(listing_row, dict):
        return dict(listing_row)
    return dict(listing_row.items()) if hasattr(listing_row, "items") else dict(listing_row)


def _country(listing_row: dict[str, Any]) -> str:
    country = listing_row.get("country") or listing_row.get("country_code")
    return str(country or "").lower()


def _to_decimal(value: Any) -> Decimal:
    return Decimal(str(float(value))).quantize(Decimal("0.01"))


def _deal_tier(deal_score: Decimal) -> DealTier:
    if deal_score >= DEAL_TIER_THRESHOLDS[DealTier.GREAT_DEAL]:
        return DealTier.GREAT_DEAL
    if deal_score >= DEAL_TIER_THRESHOLDS[DealTier.GOOD_DEAL]:
        return DealTier.GOOD_DEAL
    if deal_score >= DEAL_TIER_THRESHOLDS[DealTier.FAIR]:
        return DealTier.FAIR
    return DealTier.OVERPRICED


def run_onnx(session: Any, feature_matrix: np.ndarray) -> np.ndarray:
    """Execute one ONNX session against the provided feature matrix."""

    input_name = session.get_inputs()[0].name
    outputs = session.run(None, {input_name: np.asarray(feature_matrix, dtype=np.float32)})
    return np.asarray(outputs[0], dtype=np.float32).reshape(-1)


def score_listing(
    bundle: Any,
    listing_row: Any,
    *,
    shap_explainer: ShapExplainer | None = None,
    mode: str = "ondemand",
) -> ScoringResult:
    """Score one listing with point and quantile models."""

    row = _row_to_dict(listing_row)
    country = _country(row)
    asking_price_raw = row.get("asking_price_eur") or row.get("asking_price") or 0
    asking_price = _to_decimal(asking_price_raw)

    started = perf_counter()
    feature_matrix = bundle.feature_engineer.transform(pd.DataFrame([row]))
    estimated_raw = float(run_onnx(bundle.session_point, feature_matrix)[0])
    q05_raw = float(run_onnx(bundle.session_q05, feature_matrix)[0])
    q95_raw = float(run_onnx(bundle.session_q95, feature_matrix)[0])
    SCORER_INFERENCE_DURATION_SECONDS.labels(country=country, mode=mode).observe(perf_counter() - started)

    estimated_price = _to_decimal(estimated_raw)
    confidence_low = _to_decimal(min(q05_raw, q95_raw))
    confidence_high = _to_decimal(max(q05_raw, q95_raw))
    if estimated_price == 0:
        deal_score = Decimal("0.00")
    else:
        deal_score = ((estimated_price - asking_price) / estimated_price * Decimal("100")).quantize(
            Decimal("0.01")
        )
    deal_tier = _deal_tier(deal_score)
    shap_features = []
    if shap_explainer is not None and deal_tier in {DealTier.GREAT_DEAL, DealTier.GOOD_DEAL}:
        shap_features = shap_explainer.explain(bundle, feature_matrix.reshape(-1))

    return ScoringResult(
        listing_id=row["id"],
        country=country,
        estimated_price=estimated_price,
        asking_price=asking_price,
        deal_score=deal_score,
        deal_tier=deal_tier,
        confidence_low=confidence_low,
        confidence_high=confidence_high,
        shap_features=shap_features,
        model_version=bundle.version_tag,
        scored_at=datetime.now(tz=UTC),
    )


__all__ = ["DEAL_TIER_THRESHOLDS", "run_onnx", "score_listing"]
