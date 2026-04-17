"""Prometheus metrics exposed by the spider workers."""

from __future__ import annotations

from prometheus_client import Counter, Histogram, start_http_server


LISTINGS_SCRAPED = Counter(
    "listings_scraped_total",
    "Total listings scraped by spider workers.",
    labelnames=("portal", "country"),
)

SCRAPE_ERRORS = Counter(
    "scrape_errors_total",
    "Total scrape errors observed by spider workers.",
    labelnames=("portal", "country", "error_type"),
)

SCRAPE_DURATION = Histogram(
    "scrape_duration_seconds",
    "End-to-end scrape duration in seconds.",
    labelnames=("portal", "country"),
    buckets=(10, 30, 60, 120, 300, 600, 1800),
)


def start_metrics_server(port: int) -> None:
    """Start the Prometheus scrape endpoint."""

    start_http_server(port)
