"""MLflow logging helpers for training runs."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from estategap_ml.trainer.evaluate import Metrics


def log_training_run(
    run_name: str,
    params: dict[str, Any],
    metrics: Metrics,
    onnx_path: Path,
    fe_path: Path,
    feature_importances: dict[str, float],
    tracking_uri: str,
) -> None:
    """Persist a training run into MLflow."""

    import json

    import matplotlib.pyplot as plt
    import mlflow

    mlflow.set_tracking_uri(tracking_uri)
    mlflow.set_experiment("estategap-price-models")

    with mlflow.start_run(run_name=run_name):
        mlflow.log_params({key: value for key, value in params.items() if value is not None})
        mlflow.log_metrics(
            {
                "mape_national": metrics.mape_national,
                "mae_national": metrics.mae_national,
                "r2_national": metrics.r2_national,
                "n_train": metrics.n_train,
                "n_val": metrics.n_val,
                "n_test": metrics.n_test,
            }
        )
        for city, city_metrics in metrics.per_city.items():
            slug = city.lower().replace(" ", "_")
            for metric_name, metric_value in city_metrics.items():
                mlflow.log_metric(f"{metric_name}_{slug}", float(metric_value))
            if "mape" in city_metrics:
                mlflow.log_metric(f"mape_city_{slug}", float(city_metrics["mape"]))
        mlflow.log_artifact(str(onnx_path))
        mlflow.log_artifact(str(fe_path))

        with TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            chart_path = tmp_path / "feature_importance.png"
            names = list(feature_importances)
            values = [feature_importances[name] for name in names]
            if names:
                figure, axis = plt.subplots(figsize=(10, max(4, len(names) * 0.25)))
                axis.barh(names, values)
                axis.set_title("Feature importance")
                axis.set_xlabel("importance")
                figure.tight_layout()
                figure.savefig(chart_path)
                plt.close(figure)
                mlflow.log_artifact(str(chart_path))

            feature_names_path = tmp_path / "feature_names.json"
            feature_names_path.write_text(
                json.dumps({"feature_names": list(feature_importances)}, indent=2),
                encoding="utf-8",
            )
            mlflow.log_artifact(str(feature_names_path))
