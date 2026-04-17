"""Batching NATS consumer that normalizes raw portal listings."""

from __future__ import annotations

import asyncio
import contextlib
import hashlib
import json
import time
from decimal import Decimal
from typing import Any
from uuid import uuid4

import nats
import structlog
from nats.aio.msg import Msg
from nats.js.api import AckPolicy, ConsumerConfig
from pydantic import ValidationError
from structlog.contextvars import bind_contextvars, clear_contextvars

from estategap_common.models import ListingStatus, NormalizedListing, PropertyCategory, RawListing

from ..db.pool import create_pool
from ..metrics import (
    PIPELINE_BATCH_DURATION,
    PIPELINE_MESSAGES_PROCESSED,
    PIPELINE_MESSAGES_QUARANTINED,
    start_metrics_server,
)
from .config import NormalizerSettings
from .mapper import PortalMapper
from .writer import ListingWriter, QuarantineRecord


LOGGER = structlog.get_logger(__name__)


class NormalizerService:
    """Coordinate batching, normalization, persistence, and re-publishing."""

    def __init__(
        self,
        settings: NormalizerSettings,
        mapper: PortalMapper,
        writer: ListingWriter,
        jetstream: Any,
    ) -> None:
        self._settings = settings
        self._mapper = mapper
        self._writer = writer
        self._jetstream = jetstream
        self._batch: list[Msg] = []
        self._batch_lock = asyncio.Lock()
        self._flush_task: asyncio.Task[None] | None = None

    async def handle_message(self, message: Msg) -> None:
        """Queue a message for batch processing."""

        batch: list[Msg] | None = None
        async with self._batch_lock:
            self._batch.append(message)
            if len(self._batch) >= self._settings.batch_size:
                batch = self._take_batch_locked()
                if self._flush_task is not None:
                    self._flush_task.cancel()
                    self._flush_task = None
            elif self._flush_task is None:
                self._flush_task = asyncio.create_task(self._flush_after_timeout())
                return
            else:
                return

        if batch is not None:
            await self._process_batch(batch)

    async def close(self) -> None:
        """Flush any outstanding messages and stop the timeout task."""

        if self._flush_task is not None:
            self._flush_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._flush_task
            self._flush_task = None
        async with self._batch_lock:
            batch = self._take_batch_locked()
        if batch:
            await self._process_batch(batch)

    async def _flush_after_timeout(self) -> None:
        try:
            await asyncio.sleep(self._settings.batch_timeout)
            async with self._batch_lock:
                self._flush_task = None
                batch = self._take_batch_locked()
            if batch:
                await self._process_batch(batch)
        except asyncio.CancelledError:
            raise

    def _take_batch_locked(self) -> list[Msg]:
        batch = list(self._batch)
        self._batch.clear()
        return batch

    async def _process_batch(self, messages: list[Msg]) -> None:
        started = time.perf_counter()
        exchange_rates = await self._writer.load_exchange_rates()
        valid_rows: list[tuple[Msg, NormalizedListing]] = []
        batch_portal = "unknown"
        batch_country = "unknown"

        for message in messages:
            clear_contextvars()
            payload: dict[str, Any] | None = None
            try:
                payload = json.loads(message.data)
            except json.JSONDecodeError as exc:
                await self._quarantine_and_ack(
                    message=message,
                    portal="unknown",
                    country="unknown",
                    record=QuarantineRecord(
                        source="unknown",
                        source_id=None,
                        country=None,
                        portal=None,
                        reason="invalid_json",
                        error_detail=str(exc),
                        raw_payload={"raw_message": message.data.decode("utf-8", errors="replace")},
                    ),
                )
                continue

            try:
                raw = RawListing.model_validate(payload)
            except ValidationError as exc:
                await self._quarantine_and_ack(
                    message=message,
                    portal=str(payload.get("portal", "unknown")),
                    country=str(payload.get("country_code", "unknown")).upper(),
                    record=QuarantineRecord(
                        source=str(payload.get("portal", "unknown")),
                        source_id=_string_or_none(payload.get("external_id")),
                        country=_string_or_none(payload.get("country_code")),
                        portal=_string_or_none(payload.get("portal")),
                        reason="validation_error",
                        error_detail=str(exc),
                        raw_payload=payload,
                    ),
                )
                continue

            portal = raw.portal
            country = raw.country_code
            batch_portal = portal
            batch_country = country
            bind_contextvars(
                portal=portal,
                country=country,
                source_id=raw.external_id,
                trace_id=self._trace_id(message, raw.external_id),
            )

            mapping = self._mapper.get(raw.country_code, raw.portal)
            if mapping is None:
                await self._quarantine_and_ack(
                    message=message,
                    portal=portal,
                    country=country,
                    record=QuarantineRecord(
                        source=raw.portal,
                        source_id=raw.external_id,
                        country=raw.country_code,
                        portal=raw.portal,
                        reason="no_mapping_config",
                        raw_payload=raw.raw_json,
                    ),
                )
                continue

            try:
                mapped = self._mapper.apply(mapping, raw.raw_json, exchange_rates=exchange_rates)
                if mapped.get("asking_price") in {None, Decimal("0")}:
                    raise _QuarantineSignal("invalid_price")
                if mapped.get("location_wkt") is None and not _has_text(mapped.get("address")):
                    raise _QuarantineSignal("missing_location")
                normalized = _build_normalized_listing(raw, mapped)
            except _QuarantineSignal as exc:
                await self._quarantine_and_ack(
                    message=message,
                    portal=portal,
                    country=country,
                    record=QuarantineRecord(
                        source=raw.portal,
                        source_id=raw.external_id,
                        country=raw.country_code,
                        portal=raw.portal,
                        reason=exc.reason,
                        raw_payload=raw.raw_json,
                    ),
                )
                continue
            except ValidationError as exc:
                await self._quarantine_and_ack(
                    message=message,
                    portal=portal,
                    country=country,
                    record=QuarantineRecord(
                        source=raw.portal,
                        source_id=raw.external_id,
                        country=raw.country_code,
                        portal=raw.portal,
                        reason="validation_error",
                        error_detail=str(exc),
                        raw_payload=raw.raw_json,
                    ),
                )
                continue
            except Exception as exc:  # noqa: BLE001
                await self._quarantine_and_ack(
                    message=message,
                    portal=portal,
                    country=country,
                    record=QuarantineRecord(
                        source=raw.portal,
                        source_id=raw.external_id,
                        country=raw.country_code,
                        portal=raw.portal,
                        reason="validation_error",
                        error_detail=str(exc),
                        raw_payload=raw.raw_json,
                    ),
                )
                continue

            valid_rows.append((message, normalized))

        try:
            await self._writer.upsert_batch([row for _, row in valid_rows])
        except Exception as exc:  # noqa: BLE001
            LOGGER.error("normalizer_batch_failed", error=str(exc), size=len(valid_rows))
            for message, _ in valid_rows:
                await message.nak()
            raise

        for message, listing in valid_rows:
            bind_contextvars(
                portal=listing.source,
                country=listing.country,
                source_id=listing.source_id,
                trace_id=self._trace_id(message, listing.source_id),
            )
            await self._jetstream.publish(
                f"normalized.listings.{listing.country.lower()}",
                listing.model_dump_json().encode(),
            )
            await message.ack()
            PIPELINE_MESSAGES_PROCESSED.labels(
                service="normalizer",
                portal=listing.source,
                country=listing.country,
            ).inc()

        PIPELINE_BATCH_DURATION.labels(
            service="normalizer",
            portal=batch_portal,
            country=batch_country,
        ).observe(time.perf_counter() - started)

    async def _quarantine_and_ack(
        self,
        *,
        message: Msg,
        portal: str,
        country: str,
        record: QuarantineRecord,
    ) -> None:
        await self._writer.write_quarantine(record)
        await message.ack()
        PIPELINE_MESSAGES_QUARANTINED.labels(
            service="normalizer",
            portal=portal,
            country=country,
        ).inc()
        PIPELINE_MESSAGES_PROCESSED.labels(
            service="normalizer",
            portal=portal,
            country=country,
        ).inc()

    @staticmethod
    def _trace_id(message: Msg, fallback: str) -> str:
        headers = getattr(message, "headers", None) or {}
        return headers.get("trace_id") or headers.get("Trace-Id") or fallback


class _QuarantineSignal(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _build_normalized_listing(raw: RawListing, mapped: dict[str, Any]) -> NormalizedListing:
    property_category = mapped.get("property_category")
    if isinstance(property_category, str):
        property_category = PropertyCategory(property_category)
    payload: dict[str, Any] = {
        "id": uuid4(),
        "canonical_id": None,
        "country": raw.country_code,
        "source": raw.portal,
        "source_id": raw.external_id,
        "source_url": str(mapped["source_url"]),
        "address": _string_or_none(mapped.get("address")),
        "city": _string_or_none(mapped.get("city")),
        "region": _string_or_none(mapped.get("region")),
        "postal_code": _string_or_none(mapped.get("postal_code")),
        "location_wkt": _string_or_none(mapped.get("location_wkt")),
        "asking_price": mapped["asking_price"],
        "currency": str(mapped.get("currency", "EUR")),
        "asking_price_eur": mapped["asking_price_eur"],
        "price_per_m2_eur": mapped.get("price_per_m2_eur"),
        "property_category": property_category,
        "property_type": _string_or_none(mapped.get("property_type")),
        "built_area_m2": mapped["built_area_m2"],
        "usable_area_m2": mapped.get("usable_area_m2"),
        "plot_area_m2": mapped.get("plot_area_m2"),
        "bedrooms": mapped.get("bedrooms"),
        "bathrooms": mapped.get("bathrooms"),
        "floor_number": mapped.get("floor_number"),
        "total_floors": mapped.get("total_floors"),
        "parking_spaces": mapped.get("parking_spaces"),
        "has_lift": mapped.get("has_lift"),
        "has_pool": mapped.get("has_pool"),
        "year_built": mapped.get("year_built"),
        "council_tax_band": _string_or_none(mapped.get("council_tax_band")),
        "epc_rating": _string_or_none(mapped.get("epc_rating")),
        "tenure": _string_or_none(mapped.get("tenure")),
        "leasehold_years_remaining": mapped.get("leasehold_years_remaining"),
        "seller_type": _string_or_none(mapped.get("seller_type")),
        "bag_id": _string_or_none(mapped.get("bag_id")),
        "condition": _string_or_none(mapped.get("condition")),
        "energy_rating": _string_or_none(mapped.get("energy_rating")),
        "status": ListingStatus.ACTIVE,
        "description_orig": _string_or_none(mapped.get("description_orig")),
        "images_count": int(mapped.get("images_count") or 0),
        "first_seen_at": raw.scraped_at,
        "last_seen_at": raw.scraped_at,
        "published_at": mapped.get("published_at"),
        "raw_hash": hashlib.sha256(
            json.dumps(raw.raw_json, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest(),
    }
    return NormalizedListing.model_validate(payload)


async def run(settings: NormalizerSettings) -> None:
    """Start the long-running normalizer worker."""

    start_metrics_server(settings.metrics_port)
    pool = await create_pool(settings.database_url)
    mapper = PortalMapper(PortalMapper.load_all(settings.mappings_dir))
    writer = ListingWriter(pool)
    nc = await nats.connect(settings.nats_url)
    js = nc.jetstream()
    service = NormalizerService(settings=settings, mapper=mapper, writer=writer, jetstream=js)
    await js.subscribe(
        "raw.listings.*",
        durable="normalizer",
        stream="RAW_LISTINGS",
        manual_ack=True,
        cb=service.handle_message,
        config=ConsumerConfig(
            ack_policy=AckPolicy.EXPLICIT,
            max_deliver=5,
            ack_wait=30,
            max_ack_pending=100,
        ),
    )
    LOGGER.info("normalizer_started", subject="raw.listings.*", durable="normalizer")
    try:
        await asyncio.Event().wait()
    except asyncio.CancelledError:
        LOGGER.info("normalizer_cancelled")
        raise
    finally:
        await service.close()
        await nc.close()
        await pool.close()


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _has_text(value: Any) -> bool:
    return _string_or_none(value) is not None


__all__ = ["NormalizerService", "run"]
