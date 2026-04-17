from __future__ import annotations

from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys

import pytest

pytest.importorskip("numpy")
pd = pytest.importorskip("pandas")

from estategap_ml.trainer.evaluate import Metrics
from estategap_ml.trainer import train as train_module


class _FakeFeatureEngineer:
    def __init__(self) -> None:
        self.training_dataset_ref_ = "dataset-ref"

    def fit(self, df):
        self._fit_rows = len(df.index)
        return self

    def transform(self, df):
        import numpy as np

        return np.asarray(
            [[float(row.get("asking_price_eur", 0.0)), float(row.get("built_area_m2", 0.0))] for _, row in df.iterrows()],
            dtype=float,
        )

    def get_feature_names_out(self) -> list[str]:
        return ["asking_price_eur", "built_area_m2"]


class _FakeDataset:
    def __init__(self, data, label) -> None:
        self.data = data
        self.label = label


class _FakeBooster:
    def __init__(self) -> None:
        self._saved = False

    def feature_importance(self):
        return [1.0, 0.5]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("mape_value", "expected_confidence"),
    [
        (0.12, "transfer"),
        (0.25, "insufficient_data"),
    ],
)
async def test_run_transfer_training_uses_init_model_and_sets_confidence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mape_value: float,
    expected_confidence: str,
) -> None:
    dataset = pd.DataFrame(
        [
            {"city": "Madrid", "asking_price_eur": 100_000, "built_area_m2": 50},
            {"city": "Madrid", "asking_price_eur": 120_000, "built_area_m2": 60},
            {"city": "Barcelona", "asking_price_eur": 140_000, "built_area_m2": 70},
            {"city": "Barcelona", "asking_price_eur": 160_000, "built_area_m2": 80},
        ]
    )
    fake_engineer = _FakeFeatureEngineer()
    calls: dict[str, object] = {}

    async def fake_export_training_data(country: str, dsn: str):
        assert country == "xx"
        assert dsn == "postgresql://unused"
        return dataset

    def fake_stratified_split(frame, stratify_col: str):
        assert stratify_col == "city"
        return frame.iloc[[0, 1]], frame.iloc[[2]], frame.iloc[[3]]

    async def fake_build_feature_engineer(country: str, config):
        assert country == "xx"
        return fake_engineer

    async def fake_version_tag(country: str, config):
        assert country == "xx"
        return "xx_national_v1", None

    async def fake_maybe_promote(**kwargs):
        calls["maybe_promote"] = kwargs
        return True

    def fake_export_pipeline_to_onnx(feature_engineer, lgb_model, version_tag: str, output_dir: Path) -> Path:
        path = output_dir / f"{version_tag}.onnx"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"onnx")
        return path

    def fake_log_training_run(**kwargs):
        calls["log_training_run"] = kwargs

    monkeypatch.setattr(train_module, "export_training_data", fake_export_training_data)
    monkeypatch.setattr(train_module, "stratified_split", fake_stratified_split)
    monkeypatch.setattr(train_module, "_build_feature_engineer", fake_build_feature_engineer)
    monkeypatch.setattr(train_module, "_version_tag_for_country", fake_version_tag)
    monkeypatch.setattr(train_module, "maybe_promote", fake_maybe_promote)
    monkeypatch.setattr(train_module, "export_pipeline_to_onnx", fake_export_pipeline_to_onnx)
    monkeypatch.setattr(train_module, "log_training_run", fake_log_training_run)
    monkeypatch.setattr(
        train_module,
        "evaluate_model",
        lambda **kwargs: Metrics(mape_national=mape_value, mae_national=1.0, r2_national=0.9, per_city={}),
    )

    fake_joblib = ModuleType("joblib")
    fake_joblib.dump = lambda obj, path: Path(path).write_bytes(b"joblib")

    fake_lightgbm = ModuleType("lightgbm")
    fake_lightgbm.Dataset = _FakeDataset

    def fake_train(params, dataset_train, init_model=None, num_boost_round=None):
        calls["train"] = {
            "params": params,
            "dataset": dataset_train,
            "init_model": init_model,
            "num_boost_round": num_boost_round,
        }
        return _FakeBooster()

    fake_lightgbm.train = fake_train

    monkeypatch.setitem(sys.modules, "joblib", fake_joblib)
    monkeypatch.setitem(sys.modules, "lightgbm", fake_lightgbm)

    base_booster = object()
    config = SimpleNamespace(
        database_url="postgresql://unused",
        local_artifact_dir=tmp_path,
        transfer_mape_max=0.20,
        transfer_base_country="ES",
        mlflow_tracking_uri="file:///tmp/mlruns",
        prometheus_pushgateway_url=None,
    )

    result = await train_module.run_transfer_training(
        "xx",
        spain_booster=base_booster,
        config=config,
        dry_run=True,
    )

    assert calls["train"]["init_model"] is base_booster
    assert calls["train"]["num_boost_round"] == 100
    assert calls["train"]["params"]["learning_rate"] == 0.01
    assert result.confidence == expected_confidence
    assert calls["maybe_promote"]["transfer_learned"] is True
    assert calls["maybe_promote"]["base_country"] == "ES"
