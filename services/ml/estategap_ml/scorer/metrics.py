"""Prometheus metrics for the scorer service."""

from __future__ import annotations

try:
    from prometheus_client import Counter, Gauge, Histogram, start_http_server
except ModuleNotFoundError:  # pragma: no cover - local fallback when deps are absent
    class _MetricStub:
        def __init__(self, *args: object, **kwargs: object) -> None:
            return None

        def labels(self, *args: object, **kwargs: object) -> "_MetricStub":
            return self

        def observe(self, *args: object, **kwargs: object) -> None:
            return None

        def inc(self, *args: object, **kwargs: object) -> None:
            return None

        def set(self, *args: object, **kwargs: object) -> None:
            return None

    Counter = Gauge = Histogram = _MetricStub  # type: ignore[misc,assignment]

    def start_http_server(*args: object, **kwargs: object) -> None:
        return None


SCORER_INFERENCE_DURATION_SECONDS = Histogram(
    "scorer_inference_duration_seconds",
    "Inference time from feature transform through model execution.",
    labelnames=["country", "mode"],
)
SCORER_BATCH_SIZE = Histogram(
    "scorer_batch_size",
    "Number of listings flushed in one NATS scoring batch.",
    labelnames=["country"],
)
SCORER_ACTIVE_MODEL_VERSION = Gauge(
    "scorer_active_model_version",
    "Currently loaded scorer model version.",
    labelnames=["country", "version"],
)
SCORER_SHAP_ERRORS_TOTAL = Counter(
    "scorer_shap_errors_total",
    "SHAP computations that timed out or failed.",
    labelnames=["country"],
)
SCORER_MODEL_RELOAD_TOTAL = Counter(
    "scorer_model_reload_total",
    "Successful scorer model hot reloads.",
    labelnames=["country"],
)
SCORER_COMPARABLES_CACHE_HIT_RATIO = Gauge(
    "scorer_comparables_cache_hit_ratio",
    "Rolling comparable-cache hit ratio.",
)

__all__ = [
    "SCORER_ACTIVE_MODEL_VERSION",
    "SCORER_BATCH_SIZE",
    "SCORER_COMPARABLES_CACHE_HIT_RATIO",
    "SCORER_INFERENCE_DURATION_SECONDS",
    "SCORER_MODEL_RELOAD_TOTAL",
    "SCORER_SHAP_ERRORS_TOTAL",
    "start_http_server",
]
