"""Kafka-driven enrichment worker."""

from __future__ import annotations

import asyncio
import contextlib
import time
from datetime import UTC, datetime
from typing import Any

import asyncpg  # type: ignore[import-untyped]
import structlog
from estategap_common.broker import KafkaBroker, KafkaConfig, Message
from estategap_common.broker.kafka_lag import start_lag_poller
from pydantic import ValidationError
from structlog.contextvars import bind_contextvars, clear_contextvars

from estategap_common.models import NormalizedListing

from ..db.pool import create_pool
from ..metrics import ENRICHER_DURATION_SECONDS, ENRICHER_LISTINGS_TOTAL
from .base import BaseEnricher, EnrichmentResult, get_registered_enrichers
from .catastro import SpainCatastroEnricher
from .config import EnricherSettings
from .poi import POIDistanceCalculator


LOGGER = structlog.get_logger(__name__)


class EnricherService:
    """Consume deduplicated listings and enrich them before republishing."""

    def __init__(
        self,
        settings: EnricherSettings,
        *,
        pool: asyncpg.Pool | None = None,
        broker: KafkaBroker | None = None,
        poi_calculator: POIDistanceCalculator | None = None,
    ) -> None:
        self._settings = settings
        self._pool = pool
        self._broker = broker
        self._poi_calculator = poi_calculator
        self._owns_pool = pool is None
        self._owns_broker = broker is None
        self._enrichers_by_country: dict[str, list[BaseEnricher]] = {}

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
                service_name="pipeline-enricher",
            )
        if self._poi_calculator is None:
            self._poi_calculator = POIDistanceCalculator(
                pool=self._pool,
                overpass_url=self._settings.overpass_url,
            )
        consumer = await self._broker.create_consumer(["normalized-listings"], "estategap.pipeline-enricher")
        lag_task = asyncio.create_task(start_lag_poller(consumer, "estategap.pipeline-enricher"))
        LOGGER.info(
            "enricher_started",
            topic=self._broker.full_topic_name("normalized-listings"),
            group="estategap.pipeline-enricher",
        )
        try:
            await self._broker.consume(consumer, "estategap.pipeline-enricher", self.handle_message)
        except asyncio.CancelledError:
            LOGGER.info("enricher_cancelled")
            raise
        finally:
            lag_task.cancel()
            await asyncio.gather(lag_task, return_exceptions=True)
            await self.close()

    async def close(self) -> None:
        for enrichers in self._enrichers_by_country.values():
            for enricher in enrichers:
                aclose = getattr(enricher, "aclose", None)
                if callable(aclose):
                    with contextlib.suppress(Exception):
                        await aclose()
        self._enrichers_by_country.clear()
        if self._poi_calculator is not None and hasattr(self._poi_calculator, "aclose"):
            with contextlib.suppress(Exception):
                await self._poi_calculator.aclose()
        if self._owns_broker and self._broker is not None:
            await self._broker.stop()
        if self._owns_pool and self._pool is not None:
            await self._pool.close()

    async def handle_message(self, message: Message) -> None:
        started = time.perf_counter()
        clear_contextvars()
        try:
            listing = NormalizedListing.model_validate_json(message.value)
        except ValidationError as exc:
            LOGGER.error("invalid_enrichment_listing", error=str(exc))
            return

        bind_contextvars(
            portal=listing.source,
            country=listing.country,
            source_id=listing.source_id,
            trace_id=self._trace_id(message, listing.source_id),
        )

        try:
            _, status = await self.process_listing(listing)
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("enricher_message_failed", error=str(exc), listing_id=str(listing.id))
            raise

        ENRICHER_LISTINGS_TOTAL.labels(country=listing.country, status=status).inc()
        ENRICHER_DURATION_SECONDS.labels(country=listing.country).observe(
            time.perf_counter() - started
        )

    async def process_listing(self, listing: NormalizedListing) -> tuple[NormalizedListing, str]:
        if self._pool is None or self._broker is None or self._poi_calculator is None:
            raise RuntimeError("EnricherService is not fully initialised")

        country = listing.country.upper()
        enrichers = self._get_or_create_enrichers(country)
        results = await asyncio.gather(*(enricher.enrich(listing) for enricher in enrichers))
        updates: dict[str, object] = {}
        for result in results:
            updates.update(result.updates)
        poi_updates = await self._poi_calculator.calculate(listing)
        updates.update({key: value for key, value in poi_updates.items() if value is not None})
        status = _resolve_overall_status(results, poi_updates)
        updates["enrichment_status"] = status
        updates["enrichment_attempted_at"] = datetime.now(UTC)
        await self._apply_updates(listing_id=listing.id, country=listing.country, updates=updates)
        enriched_listing = listing.model_copy(update=updates)
        await self._broker.publish(
            "enriched-listings",
            listing.country.upper(),
            enriched_listing.model_dump_json().encode(),
        )
        return enriched_listing, status

    def _get_or_create_enrichers(self, country: str) -> list[BaseEnricher]:
        if country not in self._enrichers_by_country:
            enrichers: list[BaseEnricher] = []
            for enricher_cls in get_registered_enrichers(country):
                if enricher_cls is SpainCatastroEnricher:
                    enrichers.append(
                        enricher_cls(rate_limit=self._settings.catastro_rate_limit)  # type: ignore[misc]
                    )
                else:
                    try:
                        enrichers.append(enricher_cls(pool=self._pool))  # type: ignore[misc]
                    except TypeError:
                        enrichers.append(enricher_cls())  # type: ignore[misc]
            self._enrichers_by_country[country] = enrichers
        return self._enrichers_by_country[country]

    async def _apply_updates(
        self,
        *,
        listing_id: object,
        country: str,
        updates: dict[str, object],
    ) -> None:
        if self._pool is None:
            raise RuntimeError("Pool is not initialised")
        if not updates:
            return
        assignments: list[str] = []
        values: list[object] = [listing_id, country]
        for key, value in updates.items():
            values.append(value)
            assignments.append(f"{key} = ${len(values)}")
        assignments.append("updated_at = NOW()")
        sql = f"UPDATE listings SET {', '.join(assignments)} WHERE id = $1 AND country = $2"
        async with self._pool.acquire() as conn:
            await conn.execute(sql, *values)

    @staticmethod
    def _trace_id(message: Message, fallback: str) -> str:
        return message.headers.get("trace_id") or message.headers.get("Trace-Id") or fallback


def _resolve_overall_status(
    results: list[EnrichmentResult],
    poi_updates: dict[str, int | None],
) -> str:
    statuses = [result.status for result in results]
    any_updates = any(result.updates for result in results) or any(
        value is not None for value in poi_updates.values()
    )
    if not statuses:
        return "completed" if any_updates else "no_match"
    if any(status == "failed" for status in statuses):
        return "partial" if any_updates or any(status != "failed" for status in statuses) else "failed"
    if all(status == "no_match" for status in statuses):
        return "partial" if any(value is not None for value in poi_updates.values()) else "no_match"
    if any(status in {"partial", "no_match"} for status in statuses):
        return "partial"
    return "completed"


__all__ = ["EnricherService"]
