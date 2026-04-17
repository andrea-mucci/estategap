from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

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

    async def ack(self) -> None:
        return None

    async def nak(self, delay: int | None = None) -> None:
        return None

    async def term(self) -> None:
        return None


class FakeJetStream:
    def __init__(self) -> None:
        self._callback = None
        self.published: list[dict[str, object]] = []

    async def subscribe(self, subject: str, **kwargs: object) -> None:
        self._callback = kwargs["cb"]

    async def publish(self, subject: str, payload: bytes) -> None:
        self.published.append({"subject": subject, "payload": json.loads(payload.decode("utf-8"))})

    async def send(self, payload: dict[str, object]) -> None:
        assert self._callback is not None
        await self._callback(FakeMessage(payload))


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("asking_price", "expected_score"),
    [
        (200000.0, 18.37),
        (210000.0, 14.29),
        (230000.0, 6.12),
        (245000.0, 0.00),
        (252000.0, -2.86),
        (270000.0, -10.20),
    ],
)
async def test_scoring_e2e(asking_price: float, expected_score: float) -> None:
    with PostgresContainer("postgis/postgis:16-3.4") as postgres:
        dsn = asyncpg_dsn(postgres.get_connection_url())
        listings = [make_listing(asking_price_eur=asking_price, asking_price=asking_price)]
        listing_id = listings[0]["id"]
        await prepare_scorer_database(dsn, listings)
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
            await jetstream.send({"id": str(listing_id)})
            score = None
            for _ in range(40):
                async with db_pool.acquire() as conn:
                    row = await conn.fetchrow("SELECT deal_score FROM listings WHERE id = $1", listing_id)
                if row and row["deal_score"] is not None:
                    score = float(row["deal_score"])
                    break
                await asyncio.sleep(0.05)
            assert score is not None
            assert score == pytest.approx(expected_score, abs=0.1)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        finally:
            await db_pool.close()
