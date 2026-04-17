"""Core change-detection logic for cycle-complete portal events."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import asyncpg  # type: ignore[import-untyped]
import structlog

from estategap_common.models import PriceChangeEvent, ScrapeCycleEvent

from ..metrics import (
    CHANGE_DETECTOR_CYCLES_TOTAL,
    CHANGE_DETECTOR_DELISTINGS_TOTAL,
    CHANGE_DETECTOR_PRICE_CHANGES_TOTAL,
    CHANGE_DETECTOR_RELISTINGS_TOTAL,
)
from .config import ChangeDetectorSettings


LOGGER = structlog.get_logger(__name__)


@dataclass(slots=True)
class ListingState:
    """Current persisted state for a listing."""

    id: UUID
    country: str
    source: str
    asking_price: Decimal | None
    asking_price_eur: Decimal | None
    currency: str
    status: str
    description_orig: str | None
    last_seen_at: datetime | None


class Detector:
    """Detect delistings, re-listings, and price drops for one cycle."""

    def __init__(self, settings: ChangeDetectorSettings) -> None:
        self._settings = settings

    async def run_cycle(
        self,
        event: ScrapeCycleEvent,
        pool: asyncpg.Pool,
        jetstream: Any,
    ) -> None:
        cycle_listing_ids = await self._resolve_cycle_listing_ids(event, pool)
        active_rows = await self._fetch_listing_states(
            pool,
            portal=event.portal,
            country=event.country,
            statuses=("active",),
        )
        delisted_rows = await self._fetch_listing_states(
            pool,
            portal=event.portal,
            country=event.country,
            statuses=("delisted",),
        )
        active_ids = set(active_rows)
        delisted_ids = set(delisted_rows)
        to_delist = active_ids - cycle_listing_ids
        to_relist = cycle_listing_ids & delisted_ids
        to_check_price = cycle_listing_ids & active_ids

        await self._mark_delisted(pool, country=event.country, listing_ids=to_delist)
        await self._mark_relisted(pool, country=event.country, listing_ids=to_relist)
        await self._detect_price_changes(
            event=event,
            pool=pool,
            jetstream=jetstream,
            active_rows=active_rows,
            listing_ids=to_check_price,
        )
        await self._detect_description_changes(
            event=event,
            pool=pool,
            active_rows=active_rows,
            listing_ids=to_check_price,
        )
        CHANGE_DETECTOR_CYCLES_TOTAL.labels(country=event.country, portal=event.portal).inc()

    async def _resolve_cycle_listing_ids(
        self,
        event: ScrapeCycleEvent,
        pool: asyncpg.Pool,
    ) -> set[UUID]:
        if event.listing_ids:
            return {UUID(listing_id) for listing_id in event.listing_ids}

        window_start = event.completed_at - timedelta(hours=self._settings.cycle_window_hours)
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id
                FROM listings
                WHERE source = $1
                  AND country = $2
                  AND last_seen_at >= $3
                  AND last_seen_at <= $4
                """,
                event.portal,
                event.country,
                window_start,
                event.completed_at,
            )
        return {row["id"] for row in rows}

    async def _fetch_listing_states(
        self,
        pool: asyncpg.Pool,
        *,
        portal: str,
        country: str,
        statuses: tuple[str, ...],
    ) -> dict[UUID, ListingState]:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, country, source, asking_price, asking_price_eur, currency, status, description_orig, last_seen_at
                FROM listings
                WHERE source = $1
                  AND country = $2
                  AND status = ANY($3::text[])
                """,
                portal,
                country,
                list(statuses),
            )
        return {
            row["id"]: ListingState(
                id=row["id"],
                country=row["country"],
                source=row["source"],
                asking_price=row["asking_price"],
                asking_price_eur=row["asking_price_eur"],
                currency=row["currency"],
                status=row["status"],
                description_orig=row["description_orig"],
                last_seen_at=row["last_seen_at"],
            )
            for row in rows
        }

    async def _mark_delisted(
        self,
        pool: asyncpg.Pool,
        *,
        country: str,
        listing_ids: set[UUID],
    ) -> None:
        if not listing_ids:
            return
        async with pool.acquire() as conn:
            await conn.executemany(
                """
                UPDATE listings
                SET status = 'delisted', delisted_at = NOW(), updated_at = NOW()
                WHERE id = $1 AND country = $2
                """,
                [(listing_id, country) for listing_id in listing_ids],
            )
        CHANGE_DETECTOR_DELISTINGS_TOTAL.labels(country=country).inc(len(listing_ids))

    async def _mark_relisted(
        self,
        pool: asyncpg.Pool,
        *,
        country: str,
        listing_ids: set[UUID],
    ) -> None:
        if not listing_ids:
            return
        async with pool.acquire() as conn:
            await conn.executemany(
                """
                UPDATE listings
                SET status = 'active', delisted_at = NULL, updated_at = NOW()
                WHERE id = $1 AND country = $2
                """,
                [(listing_id, country) for listing_id in listing_ids],
            )
        CHANGE_DETECTOR_RELISTINGS_TOTAL.labels(country=country).inc(len(listing_ids))

    async def _detect_price_changes(
        self,
        *,
        event: ScrapeCycleEvent,
        pool: asyncpg.Pool,
        jetstream: Any,
        active_rows: dict[UUID, ListingState],
        listing_ids: set[UUID],
    ) -> None:
        if not listing_ids:
            return
        previous_prices = await self._fetch_previous_prices(pool, country=event.country, listing_ids=listing_ids)
        async with pool.acquire() as conn:
            for listing_id in listing_ids:
                current = active_rows[listing_id]
                previous = previous_prices.get(listing_id)
                if previous is None or current.asking_price is None or previous.asking_price is None:
                    continue
                if current.asking_price == previous.asking_price:
                    continue
                await conn.execute(
                    """
                    INSERT INTO price_history (
                        listing_id,
                        country,
                        old_price,
                        new_price,
                        currency,
                        old_price_eur,
                        new_price_eur,
                        change_type,
                        recorded_at,
                        source
                    ) VALUES ($1, $2, $3, $4, $5, $6, $7, 'price_change', $8, $9)
                    """,
                    listing_id,
                    event.country,
                    previous.asking_price,
                    current.asking_price,
                    current.currency,
                    previous.asking_price_eur,
                    current.asking_price_eur,
                    event.completed_at,
                    event.portal,
                )
                await conn.execute(
                    """
                    UPDATE listings
                    SET asking_price = $1, asking_price_eur = $2, updated_at = NOW()
                    WHERE id = $3 AND country = $4
                    """,
                    current.asking_price,
                    current.asking_price_eur,
                    listing_id,
                    event.country,
                )
                CHANGE_DETECTOR_PRICE_CHANGES_TOTAL.labels(country=event.country).inc()
                if current.asking_price < previous.asking_price:
                    drop_percentage = (
                        (previous.asking_price - current.asking_price) / previous.asking_price * Decimal("100")
                    ).quantize(Decimal("0.01"))
                    price_event = PriceChangeEvent(
                        listing_id=listing_id,
                        country=event.country,
                        portal=event.portal,
                        old_price=previous.asking_price,
                        new_price=current.asking_price,
                        currency=current.currency,
                        old_price_eur=previous.asking_price_eur,
                        new_price_eur=current.asking_price_eur,
                        drop_percentage=drop_percentage,
                        recorded_at=event.completed_at,
                    )
                    await jetstream.publish(
                        f"listings.price-change.{event.country.lower()}",
                        price_event.model_dump_json().encode(),
                    )

    async def _fetch_previous_prices(
        self,
        pool: asyncpg.Pool,
        *,
        country: str,
        listing_ids: set[UUID],
    ) -> dict[UUID, ListingState]:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT ON (listing_id)
                    listing_id,
                    old_price,
                    new_price,
                    currency,
                    old_price_eur,
                    new_price_eur
                FROM price_history
                WHERE country = $1
                  AND listing_id = ANY($2::uuid[])
                ORDER BY listing_id, recorded_at DESC
                """,
                country,
                list(listing_ids),
            )
        previous: dict[UUID, ListingState] = {}
        for row in rows:
            baseline_price = row["new_price"] if row["new_price"] is not None else row["old_price"]
            baseline_price_eur = (
                row["new_price_eur"] if row["new_price_eur"] is not None else row["old_price_eur"]
            )
            previous[row["listing_id"]] = ListingState(
                id=row["listing_id"],
                country=country,
                source="",
                asking_price=baseline_price,
                asking_price_eur=baseline_price_eur,
                currency=row["currency"],
                status="active",
                description_orig=None,
                last_seen_at=None,
            )
        return previous

    async def _detect_description_changes(
        self,
        *,
        event: ScrapeCycleEvent,
        pool: asyncpg.Pool,
        active_rows: dict[UUID, ListingState],
        listing_ids: set[UUID],
    ) -> None:
        if not listing_ids:
            return
        async with pool.acquire() as conn:
            for listing_id in listing_ids:
                current = active_rows[listing_id]
                stored_hash = _description_hash(current.description_orig)
                if stored_hash is None:
                    continue
                latest = await conn.fetchval(
                    """
                    SELECT description_orig
                    FROM listings
                    WHERE id = $1 AND country = $2
                    """,
                    listing_id,
                    event.country,
                )
                if _description_hash(latest) == stored_hash:
                    continue
                await conn.execute(
                    """
                    UPDATE listings
                    SET description_orig = $1, updated_at = NOW()
                    WHERE id = $2 AND country = $3
                    """,
                    latest,
                    listing_id,
                    event.country,
                )


def _description_hash(value: str | None) -> str | None:
    if value is None:
        return None
    return hashlib.md5(value.encode("utf-8"), usedforsecurity=False).hexdigest()


__all__ = ["Detector", "ListingState"]
