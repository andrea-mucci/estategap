"""NATS consumer for scrape-cycle completion events."""

from __future__ import annotations

import asyncio
import contextlib
from datetime import UTC, datetime, timedelta
from typing import Any

import asyncpg  # type: ignore[import-untyped]
import nats
import structlog
from nats.aio.msg import Msg
from nats.js.api import AckPolicy, ConsumerConfig
from pydantic import ValidationError
from structlog.contextvars import bind_contextvars, clear_contextvars

from estategap_common.models import ScrapeCycleEvent

from ..db.pool import create_pool
from .config import ChangeDetectorSettings
from .detector import Detector


LOGGER = structlog.get_logger(__name__)
CYCLE_SUBJECT = "scraper.cycle.completed.*.*"


class ChangeDetectorConsumer:
    """Subscribe to scrape cycle events and run change detection."""

    def __init__(
        self,
        settings: ChangeDetectorSettings,
        *,
        pool: asyncpg.Pool | None = None,
        jetstream: Any | None = None,
        nats_client: Any | None = None,
        detector: Detector | None = None,
    ) -> None:
        self._settings = settings
        self._pool = pool
        self._jetstream = jetstream
        self._nats_client = nats_client
        self._detector = detector or Detector(settings)
        self._owns_pool = pool is None
        self._owns_nats = nats_client is None
        self._last_event_at = datetime.now(UTC)
        self._fallback_task: asyncio.Task[None] | None = None

    async def run(self) -> None:
        if self._pool is None:
            self._pool = await create_pool(self._settings.database_url)
        if self._nats_client is None:
            self._nats_client = await nats.connect(self._settings.nats_url)
        if self._jetstream is None:
            self._jetstream = self._nats_client.jetstream()
        await self._jetstream.subscribe(
            CYCLE_SUBJECT,
            durable="change-detector",
            manual_ack=True,
            cb=self.handle_message,
            config=ConsumerConfig(
                ack_policy=AckPolicy.EXPLICIT,
                max_deliver=3,
                ack_wait=120,
                max_ack_pending=10,
            ),
        )
        self._fallback_task = asyncio.create_task(self._fallback_loop())
        LOGGER.info("change_detector_started", subject=CYCLE_SUBJECT, durable="change-detector")
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            LOGGER.info("change_detector_cancelled")
            raise
        finally:
            await self.close()

    async def close(self) -> None:
        if self._fallback_task is not None:
            self._fallback_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._fallback_task
            self._fallback_task = None
        if self._owns_nats and self._nats_client is not None:
            await self._nats_client.close()
        if self._owns_pool and self._pool is not None:
            await self._pool.close()

    async def handle_message(self, message: Msg) -> None:
        clear_contextvars()
        try:
            event = ScrapeCycleEvent.model_validate_json(message.data)
        except ValidationError as exc:
            LOGGER.error("invalid_scrape_cycle_event", error=str(exc))
            await message.ack()
            return

        self._last_event_at = datetime.now(UTC)
        bind_contextvars(
            portal=event.portal,
            country=event.country,
            source_id=event.cycle_id,
            trace_id=self._trace_id(message, event.cycle_id),
        )
        if self._pool is None or self._jetstream is None:
            raise RuntimeError("ChangeDetectorConsumer is not fully initialised")
        try:
            await self._detector.run_cycle(event, self._pool, self._jetstream)
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("change_detector_cycle_failed", error=str(exc), cycle_id=event.cycle_id)
            await message.nak()
            raise
        await message.ack()

    async def _fallback_loop(self) -> None:
        while True:
            await asyncio.sleep(60)
            if datetime.now(UTC) - self._last_event_at < timedelta(hours=self._settings.fallback_interval_h):
                continue
            await self._run_fallback_cycles()
            self._last_event_at = datetime.now(UTC)

    async def _run_fallback_cycles(self) -> None:
        if self._pool is None or self._jetstream is None:
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
            await self._detector.run_cycle(event, self._pool, self._jetstream)

    @staticmethod
    def _trace_id(message: Msg, fallback: str) -> str:
        headers = getattr(message, "headers", None) or {}
        return headers.get("trace_id") or headers.get("Trace-Id") or fallback


__all__ = ["ChangeDetectorConsumer"]
