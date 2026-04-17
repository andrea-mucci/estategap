"""Shared Prometheus metrics for the pipeline workers."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram, start_http_server


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

ENRICHER_LISTINGS_TOTAL = Counter(
    "enricher_listings_total",
    "Total listings processed by the enricher service.",
    labelnames=("country", "status"),
)

ENRICHER_CATASTRO_REQUESTS_TOTAL = Counter(
    "enricher_catastro_requests_total",
    "Total Catastro requests issued by outcome.",
    labelnames=("status",),
)

ENRICHER_CATASTRO_RATE_LIMIT_ACTIVE = Gauge(
    "enricher_catastro_rate_limit_active",
    "Whether the Catastro rate-limiter semaphore is currently held.",
)

ENRICHER_DURATION_SECONDS = Histogram(
    "enricher_duration_seconds",
    "Duration of per-listing enricher processing.",
    labelnames=("country",),
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10, 30),
)

CHANGE_DETECTOR_CYCLES_TOTAL = Counter(
    "change_detector_cycles_total",
    "Total change-detection cycles processed.",
    labelnames=("country", "portal"),
)

CHANGE_DETECTOR_PRICE_CHANGES_TOTAL = Counter(
    "change_detector_price_changes_total",
    "Total listing price changes recorded by country.",
    labelnames=("country",),
)

CHANGE_DETECTOR_DELISTINGS_TOTAL = Counter(
    "change_detector_delistings_total",
    "Total listings marked as delisted by country.",
    labelnames=("country",),
)

CHANGE_DETECTOR_RELISTINGS_TOTAL = Counter(
    "change_detector_relistings_total",
    "Total listings restored to active by country.",
    labelnames=("country",),
)


def start_metrics_server(port: int) -> None:
    """Expose the Prometheus scrape endpoint for a worker."""

    start_http_server(port)


__all__ = [
    "CHANGE_DETECTOR_CYCLES_TOTAL",
    "CHANGE_DETECTOR_DELISTINGS_TOTAL",
    "CHANGE_DETECTOR_PRICE_CHANGES_TOTAL",
    "CHANGE_DETECTOR_RELISTINGS_TOTAL",
    "ENRICHER_CATASTRO_RATE_LIMIT_ACTIVE",
    "ENRICHER_CATASTRO_REQUESTS_TOTAL",
    "ENRICHER_DURATION_SECONDS",
    "ENRICHER_LISTINGS_TOTAL",
    "PIPELINE_BATCH_DURATION",
    "PIPELINE_DEDUP_MATCHES",
    "PIPELINE_MESSAGES_PROCESSED",
    "PIPELINE_MESSAGES_QUARANTINED",
    "start_metrics_server",
]
