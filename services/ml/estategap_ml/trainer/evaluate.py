"""Model evaluation helpers."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd
from sklearn.metrics import mean_absolute_error, r2_score


@dataclass(slots=True)
class Metrics:
    """Aggregate model-quality metrics."""

    mape_national: float
    mae_national: float
    r2_national: float
    per_city: dict[str, dict[str, float]]
    n_train: int = 0
    n_val: int = 0
    n_test: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    denominator = np.where(y_true == 0, 1.0, y_true)
    return float(np.mean(np.abs(y_true - y_pred) / np.abs(denominator)))


def evaluate_model(
    model: Any,
    X_test: np.ndarray,
    y_test: pd.Series | np.ndarray,
    city_labels: pd.Series,
) -> Metrics:
    """Compute global and per-city evaluation metrics."""

    y_true = np.asarray(y_test, dtype=float)
    predictions = np.asarray(model.predict(X_test), dtype=float)
    per_city: dict[str, dict[str, float]] = {}
    city_series = city_labels.fillna("other").astype(str)
    counts = city_series.value_counts()
    small_cities = counts[counts < 30].index
    grouped_labels = city_series.where(~city_series.isin(small_cities), "other")

    for city, indices in grouped_labels.groupby(grouped_labels).groups.items():
        idx = np.asarray(list(indices))
        per_city[city] = {
            "mape": _mape(y_true[idx], predictions[idx]),
            "mae": float(mean_absolute_error(y_true[idx], predictions[idx])),
            "r2": float(r2_score(y_true[idx], predictions[idx])),
        }

    return Metrics(
        mape_national=_mape(y_true, predictions),
        mae_national=float(mean_absolute_error(y_true, predictions)),
        r2_national=float(r2_score(y_true, predictions)),
        per_city=per_city,
        n_test=len(y_true),
    )
