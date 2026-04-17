"""Training orchestration for the ML pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Any

import asyncpg
from estategap_ml import logger
from estategap_ml.config import Config
from estategap_ml.features.engineer import FeatureEngineer
from estategap_ml.features.zone_stats import fetch_zone_stats
from estategap_ml.trainer.data_export import export_training_data, stratified_split
from estategap_ml.trainer.evaluate import Metrics, evaluate_model
from estategap_ml.trainer.mlflow_logger import log_training_run
from estategap_ml.trainer.onnx_export import export_pipeline_to_onnx
from estategap_ml.trainer.registry import get_active_champion, maybe_promote, next_version_tag

try:
    from prometheus_client import CollectorRegistry, Counter, Gauge, push_to_gateway
except ModuleNotFoundError:  # pragma: no cover - local fallback when deps are absent
    CollectorRegistry = object  # type: ignore[assignment]

    class _MetricStub:
        def __init__(self, *args: object, **kwargs: object) -> None:
            return None

        def labels(self, *args: object, **kwargs: object) -> "_MetricStub":
            return self

        def inc(self, *args: object, **kwargs: object) -> None:
            return None

        def set(self, *args: object, **kwargs: object) -> None:
            return None

    Counter = Gauge = _MetricStub  # type: ignore[misc,assignment]

    def push_to_gateway(*args: object, **kwargs: object) -> None:
        return None


REGISTRY = CollectorRegistry() if CollectorRegistry is not object else None
ML_TRAINING_DURATION_SECONDS = Gauge(
    "ml_training_duration_seconds",
    "Latest training duration in seconds.",
    labelnames=["country"],
    registry=REGISTRY,
)
ML_TRAINING_MAPE_NATIONAL = Gauge(
    "ml_training_mape_national",
    "Latest national MAPE by country.",
    labelnames=["country"],
    registry=REGISTRY,
)
ML_MODEL_PROMOTED_TOTAL = Counter(
    "ml_model_promoted_total",
    "Total promoted models by country.",
    labelnames=["country"],
    registry=REGISTRY,
)


@dataclass(slots=True)
class TrainingResult:
    """Outcome of a country-level training run."""

    country: str
    version_tag: str
    metrics: Metrics
    promoted: bool
    onnx_path: Path
    feature_engineer_path: Path
    model: Any
    feature_engineer: FeatureEngineer
    previous_champion_tag: str | None = None
    transfer_learning: bool = False


def _target_series(df: Any) -> Any:
    if "final_price_eur" in df.columns:
        return df["final_price_eur"].fillna(df["asking_price_eur"]).astype(float)
    return df["asking_price_eur"].astype(float)


async def _version_tag_for_country(country: str, config: Config) -> tuple[str, str | None]:
    conn = await asyncpg.connect(config.database_url)
    try:
        champion = await get_active_champion(country=country, conn=conn)
        version_tag = await next_version_tag(country=country, city_scope="national", conn=conn)
        return version_tag, champion.version_tag if champion else None
    finally:
        await conn.close()


def _best_param_metrics(cv_result: dict[str, list[float]]) -> float:
    for key, values in cv_result.items():
        if key.endswith("mape-mean"):
            return float(values[-1])
    raise KeyError("Unable to find MAPE metric in LightGBM CV result.")


def _feature_importances(model: Any, feature_names: list[str]) -> dict[str, float]:
    import numpy as np

    importances = np.asarray(model.feature_importance(), dtype=float).reshape(-1)
    names = feature_names[: len(importances)]
    return {name: float(value) for name, value in zip(names, importances, strict=False)}


def _maybe_push_metrics(config: Config, country: str, metrics: Metrics) -> None:
    if not config.prometheus_pushgateway_url:
        return
    ML_TRAINING_MAPE_NATIONAL.labels(country=country).set(metrics.mape_national)
    push_to_gateway(
        config.prometheus_pushgateway_url,
        job="ml-trainer",
        registry=REGISTRY,
    )


async def run_training(country: str, config: Config, *, dry_run: bool = False) -> TrainingResult:
    """Train a full country model with Optuna tuning."""

    import joblib
    import lightgbm as lgb
    import numpy as np
    import optuna

    started = time.perf_counter()
    dataset = await export_training_data(country=country, dsn=config.database_url)
    train_df, val_df, test_df = stratified_split(dataset, stratify_col="city")
    stats = await fetch_zone_stats(country=country, dsn=config.database_url)
    feature_engineer = FeatureEngineer(
        zone_stats=stats.zone_stats,
        city_stats=stats.city_stats,
        country_stats=stats.country_stats,
    )
    X_train = feature_engineer.fit_transform(train_df)
    X_val = feature_engineer.transform(val_df)
    X_test = feature_engineer.transform(test_df)
    y_train = _target_series(train_df)
    y_val = _target_series(val_df)
    y_test = _target_series(test_df)

    version_tag, previous_champion_tag = await _version_tag_for_country(country=country, config=config)
    config.local_artifact_dir.mkdir(parents=True, exist_ok=True)
    study = optuna.create_study(
        direction="minimize",
        pruner=optuna.pruners.MedianPruner(),
        storage=f"sqlite:///{config.local_artifact_dir / f'optuna_{country.lower()}.db'}",
        study_name=f"{country.lower()}_training",
        load_if_exists=True,
    )

    dtrain = lgb.Dataset(X_train, label=y_train)

    def objective(trial: optuna.Trial) -> float:
        params = {
            "objective": "regression",
            "metric": "mape",
            "verbosity": -1,
            "num_threads": -1,
            "num_leaves": trial.suggest_int("num_leaves", 31, 255),
            "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            "n_estimators": trial.suggest_int("n_estimators", 100, 1000),
            "min_child_samples": trial.suggest_int("min_child_samples", 5, 100),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
        }
        cv_result = lgb.cv(
            params,
            dtrain,
            nfold=5,
            stratified=False,
            seed=42,
            callbacks=[lgb.early_stopping(50, verbose=False)],
        )
        metric = _best_param_metrics(cv_result)
        trial.set_user_attr("best_iteration", len(next(iter(cv_result.values()))))
        return metric

    study.optimize(objective, n_trials=config.optuna_n_trials)
    best_params = {
        **study.best_params,
        "objective": "regression",
        "metric": "mape",
        "verbosity": -1,
        "num_threads": -1,
    }
    best_iterations = int(study.best_trial.user_attrs.get("best_iteration", best_params.get("n_estimators", 200)))
    best_params["n_estimators"] = best_iterations

    X_train_val = np.concatenate([X_train, X_val], axis=0)
    y_train_val = np.concatenate([np.asarray(y_train, dtype=float), np.asarray(y_val, dtype=float)], axis=0)
    final_dataset = lgb.Dataset(X_train_val, label=y_train_val)
    model = lgb.train(best_params, final_dataset, num_boost_round=best_iterations)

    metrics = evaluate_model(model=model, X_test=X_test, y_test=y_test, city_labels=test_df["city"])
    metrics.n_train = len(train_df)
    metrics.n_val = len(val_df)
    metrics.n_test = len(test_df)

    onnx_path = export_pipeline_to_onnx(
        feature_engineer=feature_engineer,
        lgb_model=model,
        version_tag=version_tag,
        output_dir=config.local_artifact_dir,
    )
    feature_engineer_path = config.local_artifact_dir / f"{version_tag}_feature_engineer.joblib"
    joblib.dump(feature_engineer, feature_engineer_path)

    promoted = await maybe_promote(
        country=country,
        challenger_metrics=metrics,
        onnx_path=onnx_path,
        fe_path=feature_engineer_path,
        config=config,
        version_tag=version_tag,
        feature_names=feature_engineer.get_feature_names_out(),
        dataset_ref=feature_engineer.training_dataset_ref_,
        dry_run=dry_run,
    )
    if promoted:
        ML_MODEL_PROMOTED_TOTAL.labels(country=country).inc()
    ML_TRAINING_MAPE_NATIONAL.labels(country=country).set(metrics.mape_national)
    ML_TRAINING_DURATION_SECONDS.labels(country=country).set(time.perf_counter() - started)

    log_training_run(
        run_name=version_tag,
        params={**best_params, "transfer_learning": False},
        metrics=metrics,
        onnx_path=onnx_path,
        fe_path=feature_engineer_path,
        feature_importances=_feature_importances(model, feature_engineer.get_feature_names_out()),
        tracking_uri=config.mlflow_tracking_uri,
    )
    _maybe_push_metrics(config=config, country=country, metrics=metrics)
    logger.info(
        "training_completed",
        country=country,
        version_tag=version_tag,
        promoted=promoted,
        mape_national=metrics.mape_national,
    )
    return TrainingResult(
        country=country,
        version_tag=version_tag,
        metrics=metrics,
        promoted=promoted,
        onnx_path=onnx_path,
        feature_engineer_path=feature_engineer_path,
        model=model,
        feature_engineer=feature_engineer,
        previous_champion_tag=previous_champion_tag,
        transfer_learning=False,
    )


async def run_transfer_training(
    country: str,
    spain_booster: Any,
    feature_engineer: FeatureEngineer,
    config: Config,
    *,
    dry_run: bool = False,
) -> TrainingResult:
    """Fine-tune a smaller-market model from the Spain booster."""

    import joblib
    import lightgbm as lgb
    import numpy as np

    started = time.perf_counter()
    dataset = await export_training_data(country=country, dsn=config.database_url)
    train_df, val_df, test_df = stratified_split(dataset, stratify_col="city")
    X_train = feature_engineer.transform(train_df)
    X_val = feature_engineer.transform(val_df)
    X_test = feature_engineer.transform(test_df)
    y_train = _target_series(train_df)
    y_val = _target_series(val_df)
    y_test = _target_series(test_df)
    version_tag, previous_champion_tag = await _version_tag_for_country(country=country, config=config)

    params = {
        "objective": "regression",
        "metric": "mape",
        "verbosity": -1,
        "learning_rate": 0.01,
        "num_leaves": 63,
    }
    dataset_train = lgb.Dataset(
        data=np.concatenate([X_train, X_val], axis=0),
        label=np.concatenate([y_train, y_val], axis=0),
    )
    model = lgb.train(params, dataset_train, init_model=spain_booster, num_boost_round=200)
    metrics = evaluate_model(model=model, X_test=X_test, y_test=y_test, city_labels=test_df["city"])
    metrics.n_train = len(train_df)
    metrics.n_val = len(val_df)
    metrics.n_test = len(test_df)

    onnx_path = export_pipeline_to_onnx(
        feature_engineer=feature_engineer,
        lgb_model=model,
        version_tag=version_tag,
        output_dir=config.local_artifact_dir,
    )
    feature_engineer_path = config.local_artifact_dir / f"{version_tag}_feature_engineer.joblib"
    joblib.dump(feature_engineer, feature_engineer_path)
    promoted = await maybe_promote(
        country=country,
        challenger_metrics=metrics,
        onnx_path=onnx_path,
        fe_path=feature_engineer_path,
        config=config,
        version_tag=version_tag,
        feature_names=feature_engineer.get_feature_names_out(),
        dataset_ref=feature_engineer.training_dataset_ref_,
        dry_run=dry_run,
    )
    if promoted:
        ML_MODEL_PROMOTED_TOTAL.labels(country=country).inc()
    ML_TRAINING_MAPE_NATIONAL.labels(country=country).set(metrics.mape_national)
    ML_TRAINING_DURATION_SECONDS.labels(country=country).set(time.perf_counter() - started)
    log_training_run(
        run_name=version_tag,
        params={"learning_rate": 0.01, "n_estimators": 200, "transfer_learning": True},
        metrics=metrics,
        onnx_path=onnx_path,
        fe_path=feature_engineer_path,
        feature_importances=_feature_importances(model, feature_engineer.get_feature_names_out()),
        tracking_uri=config.mlflow_tracking_uri,
    )
    _maybe_push_metrics(config=config, country=country, metrics=metrics)
    return TrainingResult(
        country=country,
        version_tag=version_tag,
        metrics=metrics,
        promoted=promoted,
        onnx_path=onnx_path,
        feature_engineer_path=feature_engineer_path,
        model=model,
        feature_engineer=feature_engineer,
        previous_champion_tag=previous_champion_tag,
        transfer_learning=True,
    )
