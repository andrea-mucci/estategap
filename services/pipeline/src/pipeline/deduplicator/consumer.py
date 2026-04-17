"""NATS consumer that assigns canonical ids to normalized listings."""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any

import nats
import structlog
from nats.aio.msg import Msg
from nats.js.api import AckPolicy, ConsumerConfig
from pydantic import ValidationError
from structlog.contextvars import bind_contextvars, clear_contextvars

from estategap_common.models import NormalizedListing

from ..db.pool import create_pool
from ..metrics import (
    PIPELINE_BATCH_DURATION,
    PIPELINE_DEDUP_MATCHES,
    PIPELINE_MESSAGES_PROCESSED,
    start_metrics_server,
)
from .config import DeduplicatorSettings
from .matcher import (
    filter_by_features,
    find_proximity_candidates,
    is_address_match,
    resolve_canonical_id,
)


LOGGER = structlog.get_logger(__name__)
_POINT_RE = re.compile(r"^POINT\((?P<lon>-?\d+(?:\.\d+)?) (?P<lat>-?\d+(?:\.\d+)?)\)$")


class DeduplicatorService:
    """Resolve canonical ids for normalized listing messages."""

    def __init__(self, settings: DeduplicatorSettings, pool: Any, jetstream: Any) -> None:
        self._settings = settings
        self._pool = pool
        self._jetstream = jetstream

    async def handle_message(self, message: Msg) -> None:
        """Process a single normalized listing message."""

        started = time.perf_counter()
        clear_contextvars()
        try:
            listing = NormalizedListing.model_validate_json(message.data)
        except ValidationError as exc:
            LOGGER.error("invalid_normalized_listing", error=str(exc))
            await message.ack()
            return

        bind_contextvars(
            portal=listing.source,
            country=listing.country,
            source_id=listing.source_id,
            trace_id=self._trace_id(message, listing.source_id),
        )

        matched = False
        try:
            if listing.location_wkt is None:
                listing.canonical_id = await resolve_canonical_id(
                    self._pool,
                    listing.id,
                    [],
                    country=listing.country,
                )
            else:
                lon, lat = _parse_point(listing.location_wkt)
                candidates = await find_proximity_candidates(
                    self._pool,
                    lon=lon,
                    lat=lat,
                    country=listing.country,
                    exclude_id=listing.id,
                    proximity_meters=self._settings.proximity_meters,
                )
                matched_candidates = [
                    candidate
                    for candidate in candidates
                    if filter_by_features(candidate, listing, self._settings.area_tolerance)
                    and is_address_match(candidate.address or "", listing.address or "", self._settings.address_threshold)
                ]
                matched = bool(matched_candidates)
                listing.canonical_id = await resolve_canonical_id(
                    self._pool,
                    listing.id,
                    matched_candidates,
                    country=listing.country,
                )

            await self._jetstream.publish(
                f"deduplicated.listings.{listing.country.lower()}",
                listing.model_dump_json().encode(),
            )
            await message.ack()
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("deduplicator_message_failed", error=str(exc))
            await message.nak()
            raise

        PIPELINE_MESSAGES_PROCESSED.labels(
            service="deduplicator",
            portal=listing.source,
            country=listing.country,
        ).inc()
        PIPELINE_DEDUP_MATCHES.labels(
            service="deduplicator",
            portal=listing.source,
            country=listing.country,
            matched=str(matched).lower(),
        ).inc()
        PIPELINE_BATCH_DURATION.labels(
            service="deduplicator",
            portal=listing.source,
            country=listing.country,
        ).observe(time.perf_counter() - started)

    @staticmethod
    def _trace_id(message: Msg, fallback: str) -> str:
        headers = getattr(message, "headers", None) or {}
        return headers.get("trace_id") or headers.get("Trace-Id") or fallback


async def run(settings: DeduplicatorSettings) -> None:
    """Start the long-running deduplicator worker."""

    start_metrics_server(settings.metrics_port)
    pool = await create_pool(settings.database_url)
    nc = await nats.connect(settings.nats_url)
    js = nc.jetstream()
    service = DeduplicatorService(settings=settings, pool=pool, jetstream=js)
    await js.subscribe(
        "normalized.listings.*",
        durable="deduplicator",
        stream="NORMALIZED_LISTINGS",
        manual_ack=True,
        cb=service.handle_message,
        config=ConsumerConfig(
            ack_policy=AckPolicy.EXPLICIT,
            max_deliver=3,
            ack_wait=60,
            max_ack_pending=50,
        ),
    )
    LOGGER.info("deduplicator_started", subject="normalized.listings.*", durable="deduplicator")
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        LOGGER.info("deduplicator_cancelled")
        raise
    finally:
        await nc.close()
        await pool.close()


def _parse_point(value: str) -> tuple[float, float]:
    match = _POINT_RE.fullmatch(value.strip())
    if match is None:
        raise ValueError(f"Unsupported POINT WKT {value!r}")
    return float(match.group("lon")), float(match.group("lat"))


__all__ = ["DeduplicatorService", "run"]
