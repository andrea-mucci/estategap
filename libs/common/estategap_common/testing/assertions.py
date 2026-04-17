from __future__ import annotations

import asyncio
from uuid import UUID

import asyncpg  # type: ignore[import-untyped]


async def assert_listing_processed(pool: asyncpg.Pool, listing_id: UUID | str) -> None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, status, enrichment_status
            FROM listings
            WHERE id = $1
            """,
            listing_id,
        )
    if row is None:
        raise AssertionError(f"listing {listing_id} was not persisted")


async def assert_nats_message_received(client: object, subject: str, timeout: float = 5.0) -> object:
    subscription = await client.subscribe(subject)  # type: ignore[attr-defined]
    try:
        return await asyncio.wait_for(subscription.next_msg(timeout=timeout), timeout=timeout)
    except TimeoutError as exc:
        raise AssertionError(f"no NATS message received on {subject} within {timeout}s") from exc
    finally:
        await subscription.unsubscribe()


async def assert_deal_score_set(pool: asyncpg.Pool, listing_id: UUID | str) -> None:
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT deal_score
            FROM listings
            WHERE id = $1
            """,
            listing_id,
        )
    if row is None:
        raise AssertionError(f"listing {listing_id} was not found")
    if row["deal_score"] is None:
        raise AssertionError(f"listing {listing_id} does not have a deal score")


__all__ = [
    "assert_deal_score_set",
    "assert_listing_processed",
    "assert_nats_message_received",
]
