"""Kafka consumer for scrape-cycle completion events."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg  # type: ignore[import-untyped]
import structlog
from estategap_common.broker import KafkaBroker, KafkaConfig, Message
from estategap_common.broker.kafka_lag import start_lag_poller
from pydantic import ValidationError
from structlog.contextvars import bind_contextvars, clear_contextvars

from estategap_common.models import ScrapeCycleEvent

from ..db.pool import create_pool
from .config import ChangeDetectorSettings
from .detector import Detector


LOGGER = structlog.get_logger(__name__)


class ChangeDetectorConsumer:
    """Subscribe to scrape cycle events and run change detection."""

    def __init__(
        self,
        settings: ChangeDetectorSettings,
        *,
        pool: asyncpg.Pool | None = None,
        broker: KafkaBroker | None = None,
        detector: Detector | None = None,
    ) -> None:
        self._settings = settings
        self._pool = pool
        self._broker = broker
        self._detector = detector or Detector(settings)
        self._owns_pool = pool is None
        self._owns_broker = broker is None
        self._last_event_at = datetime.now(UTC)
        self._fallback_task: asyncio.Task[None] | None = None

    async def run(self) -> None:
        if self._pool is None:
            self._pool = await create_pool(self._settings.database_url)
        if self._broker is None:
            self._broker = KafkaBroker(
                KafkaConfig(
                    brokers=self._settings.kafka_brokers,
                    topic_prefix=self._settings.kafka_topic_prefix,
                    max_retries=self._settings.kafka_max_retries,
                ),
                service_name="pipeline-change-detector",
            )
        consumer = await self._broker.create_consumer(
            ["scraper-cycle"],
            "estategap.pipeline-change-detector",
        )
        lag_task = asyncio.create_task(start_lag_poller(consumer, "estategap.pipeline-change-detector"))
        self._fallback_task = asyncio.create_task(self._fallback_loop())
        LOGGER.info(
            "change_detector_started",
            topic=self._broker.full_topic_name("scraper-cycle"),
            group="estategap.pipeline-change-detector",
        )
        try:
            await self._broker.consume(consumer, "estategap.pipeline-change-detector", self.handle_message)
        except asyncio.CancelledError:
            LOGGER.info("change_detector_cancelled")
            raise
        finally:
            lag_task.cancel()
            await asyncio.gather(lag_task, return_exceptions=True)
            await self.close()

    async def close(self) -> None:
        if self._fallback_task is not None:
            self._fallback_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._fallback_task
            self._fallback_task = None
        if self._owns_broker and self._broker is not None:
            await self._broker.stop()
        if self._owns_pool and self._pool is not None:
            await self._pool.close()

    async def handle_message(self, message: Message) -> None:
        clear_contextvars()
        try:
            event = ScrapeCycleEvent.model_validate_json(message.value)
        except ValidationError as exc:
            LOGGER.error("invalid_scrape_cycle_event", error=str(exc))
            return

        self._last_event_at = datetime.now(UTC)
        bind_contextvars(
            portal=event.portal,
            country=event.country,
            source_id=event.cycle_id,
            trace_id=self._trace_id(message, event.cycle_id),
        )
        if self._pool is None or self._broker is None:
            raise RuntimeError("ChangeDetectorConsumer is not fully initialised")
        try:
            await self._detector.run_cycle(event, self._pool, self._broker)
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("change_detector_cycle_failed", error=str(exc), cycle_id=event.cycle_id)
            raise

    async def _fallback_loop(self) -> None:
        while True:
            await asyncio.sleep(60)
            if datetime.now(UTC) - self._last_event_at < timedelta(hours=self._settings.fallback_interval_h):
                continue
            await self._run_fallback_cycles()
            self._last_event_at = datetime.now(UTC)

    async def _run_fallback_cycles(self) -> None:
        if self._pool is None or self._broker is None:
            return
        LOGGER.warning("change_detector_fallback_triggered", hours=self._settings.fallback_interval_h)
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT source, country
                FROM listings
                WHERE last_seen_at < NOW() - ($1::int * interval '1 hour')
                  AND status = 'active'
                """,
                self._settings.fallback_interval_h,
            )
        now = datetime.now(UTC)
        for row in rows:
            event = ScrapeCycleEvent(
                cycle_id=f"fallback-{row['country'].lower()}-{row['source']}-{int(now.timestamp())}",
                portal=row["source"],
                country=row["country"],
                completed_at=now,
                listing_ids=[],
            )
            await self._detector.run_cycle(event, self._pool, self._broker)

    @staticmethod
    def _trace_id(message: Message, fallback: str) -> str:
        return message.headers.get("trace_id") or message.headers.get("Trace-Id") or fallback


__all__ = ["ChangeDetectorConsumer"]
