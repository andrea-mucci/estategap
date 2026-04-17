"""CLI entrypoint for the change-detector worker."""

from __future__ import annotations

import asyncio
import logging

import structlog

from ..metrics import start_metrics_server
from .config import ChangeDetectorSettings
from .consumer import ChangeDetectorConsumer


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
        service="change-detector",
        portal=None,
        country=None,
        source_id=None,
        trace_id=None,
    )


async def _run() -> None:
    settings = ChangeDetectorSettings()
    _configure_logging(settings.log_level)
    start_metrics_server(settings.metrics_port)
    await ChangeDetectorConsumer(settings).run()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
