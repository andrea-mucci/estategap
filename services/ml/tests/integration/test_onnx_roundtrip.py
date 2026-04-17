from __future__ import annotations

from uuid import uuid4

import numpy as np
import pytest

pytest.importorskip("lightgbm")
pytest.importorskip("onnxruntime")
pytest.importorskip("onnxmltools")
pytest.importorskip("pandas")
pytest.importorskip("sklearn")

import lightgbm as lgb
import pandas as pd

from estategap_ml.features.engineer import FeatureEngineer
from estategap_ml.features.zone_stats import ZoneStats
from estategap_ml.trainer.onnx_export import OnnxSelfTestError, export_pipeline_to_onnx


def _training_frame(rows: int = 200) -> pd.DataFrame:
    data = []
    zone_id = uuid4()
    for idx in range(rows):
        data.append(
            {
                "country": "es",
                "city": "Madrid",
                "zone_id": zone_id,
                "lat": 40.4 + idx * 0.0001,
                "lon": -3.7,
                "asking_price_eur": 250000 + idx * 1000,
                "final_price_eur": 245000 + idx * 1000,
                "price_per_m2_eur": 3000 + idx,
                "built_area_m2": 70 + (idx % 5),
                "usable_area_m2": 65 + (idx % 4),
                "bedrooms": 2 + (idx % 3),
                "bathrooms": 1 + (idx % 2),
                "floor_number": 2 + (idx % 4),
                "total_floors": 7,
                "has_lift": True,
                "parking_spaces": idx % 2,
                "property_type": "apartment",
                "property_category": "residential",
                "energy_cert": "B",
                "condition": "good",
                "building_year": 2005,
                "community_fees_eur": 90,
                "photo_count": 8,
                "listed_at": "2025-06-15T00:00:00Z",
                "dist_metro_m": 300,
                "dist_train_m": 700,
                "dist_beach_m": 10000,
            }
        )
    return pd.DataFrame(data)


def test_export_pipeline_to_onnx_round_trip(tmp_path) -> None:
    frame = _training_frame()
    zone_id = frame.loc[0, "zone_id"]
    engineer = FeatureEngineer(
        zone_stats={zone_id: ZoneStats(zone_id=zone_id, median_price_m2=3200, listing_density=10)},
        city_stats={"madrid": ZoneStats(zone_id=None, median_price_m2=3000, listing_density=15)},
        country_stats=ZoneStats(zone_id=None, median_price_m2=2800, listing_density=20),
    )
    X = engineer.fit_transform(frame)
    y = frame["final_price_eur"].astype(float)
    dataset = lgb.Dataset(X, label=y)
    model = lgb.train({"objective": "regression", "metric": "l2", "verbosity": -1}, dataset, num_boost_round=25)

    path = export_pipeline_to_onnx(engineer, model, "es_national_v1", tmp_path)

    assert path.exists()


def test_export_pipeline_to_onnx_raises_on_self_test_mismatch(tmp_path, monkeypatch) -> None:
    frame = _training_frame()
    zone_id = frame.loc[0, "zone_id"]
    engineer = FeatureEngineer(
        zone_stats={zone_id: ZoneStats(zone_id=zone_id, median_price_m2=3200, listing_density=10)},
        city_stats={"madrid": ZoneStats(zone_id=None, median_price_m2=3000, listing_density=15)},
        country_stats=ZoneStats(zone_id=None, median_price_m2=2800, listing_density=20),
    )
    X = engineer.fit_transform(frame)
    y = frame["final_price_eur"].astype(float)
    dataset = lgb.Dataset(X, label=y)
    model = lgb.train({"objective": "regression", "metric": "l2", "verbosity": -1}, dataset, num_boost_round=10)

    import onnxruntime as ort

    original_session = ort.InferenceSession

    class _FakeSession:
        def __init__(self, *args, **kwargs) -> None:
            self._real = original_session(*args, **kwargs)

        def get_inputs(self):
            return self._real.get_inputs()

        def run(self, output_names, inputs):
            output = self._real.run(output_names, inputs)[0]
            return [output + 5.0]

    monkeypatch.setattr(ort, "InferenceSession", _FakeSession)
    with pytest.raises(OnnxSelfTestError):
        export_pipeline_to_onnx(engineer, model, "es_national_v1", tmp_path)
