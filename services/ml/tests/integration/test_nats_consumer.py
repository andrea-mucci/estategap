from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("asyncpg")
pytest.importorskip("testcontainers")

import asyncpg
from estategap_common.broker import Message
from testcontainers.postgres import PostgresContainer

from estategap_ml.scorer.kafka_consumer import KafkaConsumer

from tests.scorer_support import asyncpg_dsn, build_fake_bundle, make_listing, prepare_scorer_database


class FakeConsumer:
    async def stop(self) -> None:
        return None


class FakeBroker:
    def __init__(self) -> None:
        self._messages: asyncio.Queue[dict[str, object]] = asyncio.Queue()
        self.published: dict[str, list[dict[str, object]]] = {}

    async def create_consumer(self, topics: list[str], group: str) -> FakeConsumer:
        return FakeConsumer()

    async def consume(self, consumer: FakeConsumer, group: str, handler) -> None:
        while True:
            payload = await self._messages.get()
            try:
                await handler(
                    Message(
                        key="ES",
                        value=json.dumps(payload).encode("utf-8"),
                        topic="estategap.enriched-listings",
                    )
                )
            finally:
                self._messages.task_done()

    async def publish(self, topic: str, key: str, value: bytes) -> None:
        self.published.setdefault(topic, []).append({"key": key, "value": json.loads(value.decode("utf-8"))})

    async def send(self, payload: dict[str, object]) -> None:
        await self._messages.put(payload)


@pytest.mark.asyncio
async def test_consume_loop_updates_db_and_publishes_event() -> None:
    with PostgresContainer("postgis/postgis:16-3.4") as postgres:
        dsn = asyncpg_dsn(postgres.get_connection_url())
        listing_id = uuid4()
        await prepare_scorer_database(dsn, [make_listing(id=listing_id)])
        db_pool = await asyncpg.create_pool(dsn)
        try:
            broker = FakeBroker()
            registry = SimpleNamespace(get=lambda country: build_fake_bundle(country_code=country))
            consumer = KafkaConsumer(
                config=SimpleNamespace(scorer_batch_size=50, scorer_batch_flush_seconds=0.1),
                db_pool=db_pool,
                registry=registry,
                broker=broker,
            )
            task = asyncio.create_task(consumer.consume_loop())
            await asyncio.sleep(0.05)
            await broker.send({"id": str(listing_id)})
            row = None
            for _ in range(40):
                async with db_pool.acquire() as conn:
                    row = await conn.fetchrow(
                        "SELECT estimated_price_eur, deal_tier, model_version FROM listings WHERE id = $1",
                        listing_id,
                    )
                if row and row["deal_tier"] is not None:
                    break
                await asyncio.sleep(0.05)
            assert row is not None
            assert float(row["estimated_price_eur"]) == pytest.approx(245000.0)
            assert row["deal_tier"] == 1
            assert row["model_version"] == "es_national_v1"
            assert "scored-listings" in broker.published
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        finally:
            await db_pool.close()
