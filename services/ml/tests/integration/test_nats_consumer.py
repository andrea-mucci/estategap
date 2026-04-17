from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

pytest.importorskip("asyncpg")
pytest.importorskip("testcontainers")

import asyncpg
from testcontainers.postgres import PostgresContainer

from estategap_ml.scorer.nats_consumer import NatsConsumer

from tests.scorer_support import asyncpg_dsn, build_fake_bundle, make_listing, prepare_scorer_database


class FakeMessage:
    def __init__(self, payload: dict[str, object]) -> None:
        self.data = json.dumps(payload).encode("utf-8")
        self.acked = False
        self.nacked = False
        self.termed = False

    async def ack(self) -> None:
        self.acked = True

    async def nak(self, delay: int | None = None) -> None:
        self.nacked = True

    async def term(self) -> None:
        self.termed = True


class FakeJetStream:
    def __init__(self) -> None:
        self._callback = None
        self.published: dict[str, list[bytes]] = {}

    async def subscribe(self, subject: str, **kwargs: object) -> None:
        self._callback = kwargs["cb"]

    async def publish(self, subject: str, payload: bytes) -> None:
        self.published.setdefault(subject, []).append(payload)

    async def send(self, subject: str, payload: dict[str, object]) -> FakeMessage:
        msg = FakeMessage(payload)
        assert self._callback is not None
        await self._callback(msg)
        return msg


@pytest.mark.asyncio
async def test_consume_loop_updates_db_and_publishes_event() -> None:
    with PostgresContainer("postgis/postgis:16-3.4") as postgres:
        dsn = asyncpg_dsn(postgres.get_connection_url())
        listing_id = uuid4()
        await prepare_scorer_database(dsn, [make_listing(id=listing_id)])
        db_pool = await asyncpg.create_pool(dsn)
        try:
            jetstream = FakeJetStream()
            registry = SimpleNamespace(get=lambda country: build_fake_bundle(country_code=country))
            consumer = NatsConsumer(
                config=SimpleNamespace(scorer_batch_size=50, scorer_batch_flush_seconds=0.1),
                db_pool=db_pool,
                registry=registry,
                jetstream=jetstream,
            )
            task = asyncio.create_task(consumer.consume_loop())
            await asyncio.sleep(0.05)
            msg = await jetstream.send("enriched.listings", {"id": str(listing_id)})
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
            assert msg.acked is True
            assert "scored.listings" in jetstream.published
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        finally:
            await db_pool.close()
