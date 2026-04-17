from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from estategap_common.models import ScrapeCycleEvent
from pipeline.change_detector import ChangeDetectorConsumer, ChangeDetectorSettings
from tests.conftest import FakeMsg


class FakeBroker:
    def __init__(self) -> None:
        self.published: list[tuple[str, str, bytes]] = []

    async def publish(self, topic: str, key: str, payload: bytes) -> None:
        self.published.append((topic, key, payload))


@pytest.mark.asyncio
async def test_change_detector_records_drop_and_delisting(asyncpg_pool) -> None:
    dropped_id = uuid4()
    missing_id = uuid4()
    completed_at = datetime(2026, 4, 17, 13, 0, tzinfo=UTC)

    async with asyncpg_pool.acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO listings (
                id,
                country,
                source,
                source_id,
                source_url,
                asking_price,
                currency,
                asking_price_eur,
                built_area,
                area_unit,
                built_area_m2,
                status,
                first_seen_at,
                last_seen_at
            ) VALUES (
                $1, $2, $3, $4, $5, $6, $7, $8, $9, 'm2', $10, $11, $12, $13
            )
            """,
            [
                (
                    dropped_id,
                    "ES",
                    "idealista",
                    "drop-1",
                    "https://www.idealista.com/inmueble/drop-1/",
                    Decimal("290000"),
                    "EUR",
                    Decimal("290000"),
                    Decimal("80"),
                    Decimal("80"),
                    "active",
                    datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
                    completed_at,
                ),
                (
                    missing_id,
                    "ES",
                    "idealista",
                    "missing-1",
                    "https://www.idealista.com/inmueble/missing-1/",
                    Decimal("180000"),
                    "EUR",
                    Decimal("180000"),
                    Decimal("70"),
                    Decimal("70"),
                    "active",
                    datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
                    datetime(2026, 4, 17, 12, 30, tzinfo=UTC),
                ),
            ],
        )
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
            dropped_id,
            "ES",
            Decimal("300000"),
            Decimal("300000"),
            "EUR",
            Decimal("300000"),
            Decimal("300000"),
            datetime(2026, 4, 17, 11, 0, tzinfo=UTC),
            "idealista",
        )

    broker = FakeBroker()
    consumer = ChangeDetectorConsumer(
        ChangeDetectorSettings(database_url="postgresql://unused", kafka_brokers="localhost:9092"),
        pool=asyncpg_pool,
        broker=broker,
    )
    event = ScrapeCycleEvent(
        cycle_id="cycle-1",
        portal="idealista",
        country="ES",
        completed_at=completed_at,
        listing_ids=[str(dropped_id)],
    )
    message = FakeMsg(event.model_dump_json().encode())

    await consumer.handle_message(message)

    latest_price_row = await asyncpg_pool.fetchrow(
        """
        SELECT old_price, new_price
        FROM price_history
        WHERE listing_id = $1
        ORDER BY recorded_at DESC
        LIMIT 1
        """,
        dropped_id,
    )
    missing_status = await asyncpg_pool.fetchrow(
        "SELECT status, delisted_at FROM listings WHERE id = $1 AND country = 'ES'",
        missing_id,
    )
    published = await subscription.next_msg(timeout=1)
    count = await asyncpg_pool.fetchval(
        "SELECT COUNT(*) FROM price_history WHERE listing_id = $1",
        missing_id,
    )

    assert latest_price_row is not None
    assert latest_price_row["old_price"] == Decimal("300000.00")
    assert latest_price_row["new_price"] == Decimal("290000.00")
    assert missing_status["status"] == "delisted"
    assert missing_status["delisted_at"] is not None
    assert broker.published
    assert "290000" in broker.published[0][2].decode()
    assert count == 0

    await consumer.close()
