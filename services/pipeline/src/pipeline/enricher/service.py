"""NATS-driven enrichment worker."""

from __future__ import annotations

import asyncio
import contextlib
import time
from datetime import UTC, datetime
from typing import Any

import asyncpg  # type: ignore[import-untyped]
import nats
import structlog
from nats.aio.msg import Msg
from nats.js.api import AckPolicy, ConsumerConfig
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
DEDUPLICATED_SUBJECT = "deduplicated.listings.*"


class EnricherService:
    """Consume deduplicated listings and enrich them before republishing."""

    def __init__(
        self,
        settings: EnricherSettings,
        *,
        pool: asyncpg.Pool | None = None,
        jetstream: Any | None = None,
        nats_client: Any | None = None,
        poi_calculator: POIDistanceCalculator | None = None,
    ) -> None:
        self._settings = settings
        self._pool = pool
        self._jetstream = jetstream
        self._nats_client = nats_client
        self._poi_calculator = poi_calculator
        self._owns_pool = pool is None
        self._owns_nats = nats_client is None
        self._enrichers_by_country: dict[str, list[BaseEnricher]] = {}

    async def run(self) -> None:
        if self._pool is None:
            self._pool = await create_pool(self._settings.database_url)
        if self._nats_client is None:
            self._nats_client = await nats.connect(self._settings.nats_url)
        if self._jetstream is None:
            self._jetstream = self._nats_client.jetstream()
        if self._poi_calculator is None:
            self._poi_calculator = POIDistanceCalculator(
                pool=self._pool,
                overpass_url=self._settings.overpass_url,
            )
        await self._jetstream.subscribe(
            DEDUPLICATED_SUBJECT,
            durable="enricher",
            manual_ack=True,
            cb=self.handle_message,
            config=ConsumerConfig(
                ack_policy=AckPolicy.EXPLICIT,
                max_deliver=5,
                ack_wait=60,
                max_ack_pending=100,
            ),
        )
        LOGGER.info("enricher_started", subject=DEDUPLICATED_SUBJECT, durable="enricher")
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            LOGGER.info("enricher_cancelled")
            raise
        finally:
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
        if self._owns_nats and self._nats_client is not None:
            await self._nats_client.close()
        if self._owns_pool and self._pool is not None:
            await self._pool.close()

    async def handle_message(self, message: Msg) -> None:
        started = time.perf_counter()
        clear_contextvars()
        try:
            listing = NormalizedListing.model_validate_json(message.data)
        except ValidationError as exc:
            LOGGER.error("invalid_enrichment_listing", error=str(exc))
            await message.ack()
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
            await message.nak()
            raise

        await message.ack()
        ENRICHER_LISTINGS_TOTAL.labels(country=listing.country, status=status).inc()
        ENRICHER_DURATION_SECONDS.labels(country=listing.country).observe(
            time.perf_counter() - started
        )

    async def process_listing(self, listing: NormalizedListing) -> tuple[NormalizedListing, str]:
        if self._pool is None or self._jetstream is None or self._poi_calculator is None:
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
        await self._jetstream.publish(
            f"listings.enriched.{listing.country.lower()}",
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
                    enrichers.append(enricher_cls())
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
    def _trace_id(message: Msg, fallback: str) -> str:
        headers = getattr(message, "headers", None) or {}
        return headers.get("trace_id") or headers.get("Trace-Id") or fallback


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
