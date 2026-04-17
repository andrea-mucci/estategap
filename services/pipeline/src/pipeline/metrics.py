"""Shared Prometheus metrics for the pipeline workers."""

from __future__ import annotations

from prometheus_client import Counter, Histogram, start_http_server


PIPELINE_MESSAGES_PROCESSED = Counter(
    "pipeline_messages_processed_total",
    "Total pipeline messages that reached a terminal acknowledgement state.",
    labelnames=("service", "portal", "country"),
)

PIPELINE_MESSAGES_QUARANTINED = Counter(
    "pipeline_messages_quarantined_total",
    "Total pipeline messages written to quarantine.",
    labelnames=("service", "portal", "country"),
)

PIPELINE_BATCH_DURATION = Histogram(
    "pipeline_batch_duration_seconds",
    "Duration of normalizer batch flushes and deduplicator single-message processing.",
    labelnames=("service", "portal", "country"),
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5),
)

PIPELINE_DEDUP_MATCHES = Counter(
    "pipeline_dedup_matches_total",
    "Total deduplicator match decisions.",
    labelnames=("service", "portal", "country", "matched"),
)


def start_metrics_server(port: int) -> None:
    """Expose the Prometheus scrape endpoint for a worker."""

    start_http_server(port)


__all__ = [
    "PIPELINE_BATCH_DURATION",
    "PIPELINE_DEDUP_MATCHES",
    "PIPELINE_MESSAGES_PROCESSED",
    "PIPELINE_MESSAGES_QUARANTINED",
    "start_metrics_server",
]
