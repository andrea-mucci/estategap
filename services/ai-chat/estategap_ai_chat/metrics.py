"""Prometheus metrics for the AI chat service."""

from __future__ import annotations

try:
    from prometheus_client import Counter, Histogram, start_http_server
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

    Counter = Histogram = _MetricStub

    def start_http_server(*args: object, **kwargs: object) -> None:
        return None


AI_CHAT_CONVERSATIONS_TOTAL = Counter(
    "ai_chat_conversations_total",
    "Conversations started by subscription tier.",
    labelnames=["tier"],
)
AI_CHAT_TURNS_TOTAL = Counter(
    "ai_chat_turns_total",
    "Completed chat turns by provider.",
    labelnames=["provider"],
)
AI_CHAT_LLM_LATENCY_SECONDS = Histogram(
    "ai_chat_llm_latency_seconds",
    "LLM latency until the first token is streamed.",
    labelnames=["provider"],
)
AI_CHAT_CRITERIA_PARSE_ERRORS_TOTAL = Counter(
    "ai_chat_criteria_parse_errors_total",
    "Criteria JSON extraction or validation failures.",
)
AI_CHAT_FALLBACK_ACTIVATIONS_TOTAL = Counter(
    "ai_chat_fallback_activations_total",
    "Fallback provider activations.",
)
AI_CHAT_SUBSCRIPTION_REJECTIONS_TOTAL = Counter(
    "ai_chat_subscription_rejections_total",
    "Requests rejected because the subscription tier exceeded its limits.",
)


def start_metrics_server(port: int) -> None:
    """Start the Prometheus HTTP exporter."""

    start_http_server(port)


__all__ = [
    "AI_CHAT_CONVERSATIONS_TOTAL",
    "AI_CHAT_CRITERIA_PARSE_ERRORS_TOTAL",
    "AI_CHAT_FALLBACK_ACTIVATIONS_TOTAL",
    "AI_CHAT_LLM_LATENCY_SECONDS",
    "AI_CHAT_SUBSCRIPTION_REJECTIONS_TOTAL",
    "AI_CHAT_TURNS_TOTAL",
    "start_metrics_server",
]
