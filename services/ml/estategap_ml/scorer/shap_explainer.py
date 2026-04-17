"""SHAP explanation helpers for scorer results."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from typing import Any

import numpy as np

try:
    import shap
except ModuleNotFoundError:  # pragma: no cover - optional at import time
    shap = None  # type: ignore[assignment]

from estategap_common.models import ShapValue

from .feature_labels import render_label
from .metrics import SCORER_SHAP_ERRORS_TOTAL


class ShapExplainer:
    """Cache TreeExplainers per model version and render top-N labels."""

    def __init__(self, timeout_seconds: float = 2.0) -> None:
        self._timeout_seconds = timeout_seconds
        self._cache: dict[str, shap.TreeExplainer] = {}
        self._executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="scorer-shap")

    def invalidate(self, version_tag: str | None) -> None:
        """Invalidate a cached explainer after a model swap."""

        if version_tag:
            self._cache.pop(version_tag, None)

    def _get_explainer(self, bundle: Any) -> shap.TreeExplainer:
        if shap is None:  # pragma: no cover - runtime dependency
            msg = "shap is required to compute explanations."
            raise RuntimeError(msg)
        explainer = self._cache.get(bundle.version_tag)
        if explainer is None:
            explainer = shap.TreeExplainer(bundle.lgb_booster)
            self._cache[bundle.version_tag] = explainer
        return explainer

    def explain(
        self,
        bundle: Any,
        feature_vector: np.ndarray,
        *,
        limit: int = 5,
    ) -> list[ShapValue]:
        """Return the strongest absolute SHAP contributions for one feature vector."""

        future = self._executor.submit(self._explain_sync, bundle, np.asarray(feature_vector, dtype=float), limit)
        try:
            return future.result(timeout=self._timeout_seconds)
        except FuturesTimeoutError:
            SCORER_SHAP_ERRORS_TOTAL.labels(country=bundle.country_code).inc()
            return []
        except Exception:
            SCORER_SHAP_ERRORS_TOTAL.labels(country=bundle.country_code).inc()
            return []

    def _explain_sync(self, bundle: Any, feature_vector: np.ndarray, limit: int) -> list[ShapValue]:
        explainer = self._get_explainer(bundle)
        shap_values = explainer.shap_values(feature_vector.reshape(1, -1))
        if isinstance(shap_values, list):
            shap_values = shap_values[0]
        values = np.asarray(shap_values, dtype=float).reshape(-1)
        indices = np.argsort(np.abs(values))[::-1][:limit]
        feature_names = list(bundle.feature_names or [])
        if len(feature_names) < len(values):
            feature_names.extend(f"feature_{index}" for index in range(len(feature_names), len(values)))
        return [
            ShapValue(
                feature_name=feature_names[index],
                value=float(feature_vector[index]),
                contribution=float(values[index]),
                label=render_label(feature_names[index], float(feature_vector[index]), float(values[index])),
            )
            for index in indices
        ]


__all__ = ["ShapExplainer"]
