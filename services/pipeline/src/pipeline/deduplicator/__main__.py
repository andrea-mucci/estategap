"""CLI entrypoint for the pipeline deduplicator worker."""

from __future__ import annotations

import asyncio
import logging

import structlog

from .config import DeduplicatorSettings
from .consumer import run


_NAME_TO_LEVEL: dict[str, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _configure_logging(level: str) -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            _NAME_TO_LEVEL.get(level.upper(), logging.INFO),
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    structlog.contextvars.bind_contextvars(
        service="deduplicator",
        portal=None,
        country=None,
        source_id=None,
        trace_id=None,
    )


def main() -> None:
    settings = DeduplicatorSettings()
    _configure_logging(settings.log_level)
    asyncio.run(run(settings))


if __name__ == "__main__":
    main()
