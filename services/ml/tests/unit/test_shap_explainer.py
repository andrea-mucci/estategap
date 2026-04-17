from __future__ import annotations

import time
from types import SimpleNamespace

import pytest

pytest.importorskip("numpy")

import numpy as np

from estategap_ml.scorer import shap_explainer as shap_module
from estategap_ml.scorer.shap_explainer import ShapExplainer

from tests.scorer_support import build_fake_bundle


def test_explainer_cache_reuses_same_object(monkeypatch) -> None:
    class FakeTreeExplainer:
        created = 0

        def __init__(self, booster: object) -> None:
            type(self).created += 1

        def shap_values(self, matrix: np.ndarray) -> np.ndarray:
            return np.asarray([[1.2, -0.5, 0.1]], dtype=float)

    monkeypatch.setattr(shap_module, "shap", SimpleNamespace(TreeExplainer=FakeTreeExplainer))
    explainer = ShapExplainer(timeout_seconds=0.1)
    bundle = build_fake_bundle(feature_names=["asking_price_eur", "built_area_m2", "bedrooms"])

    first = explainer.explain(bundle, np.asarray([200000.0, 85.0, 3.0], dtype=float))
    second = explainer.explain(bundle, np.asarray([200000.0, 85.0, 3.0], dtype=float))

    assert FakeTreeExplainer.created == 1
    assert [item.feature_name for item in first] == [item.feature_name for item in second]
    assert len(first) == 3


def test_timeout_returns_empty(monkeypatch) -> None:
    explainer = ShapExplainer(timeout_seconds=0.01)
    bundle = build_fake_bundle()

    def slow_explain(*args: object, **kwargs: object) -> list[object]:
        time.sleep(0.05)
        return []

    monkeypatch.setattr(explainer, "_explain_sync", slow_explain)

    assert explainer.explain(bundle, np.asarray([1.0, 2.0, 3.0], dtype=float)) == []
