from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from estategap_common.models import ScrapeCycleEvent
from pipeline.change_detector.config import ChangeDetectorSettings
from pipeline.change_detector.detector import Detector


class _Acquire(AbstractAsyncContextManager["_FakeConn"]):
    def __init__(self, conn: "_FakeConn") -> None:
        self._conn = conn

    async def __aenter__(self) -> "_FakeConn":
        return self._conn

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeConn:
    def __init__(
        self,
        *,
        cycle_rows: list[dict[str, object]] | None = None,
        active_rows: list[dict[str, object]] | None = None,
        delisted_rows: list[dict[str, object]] | None = None,
        history_rows: list[dict[str, object]] | None = None,
    ) -> None:
        self.cycle_rows = cycle_rows or []
        self.active_rows = active_rows or []
        self.delisted_rows = delisted_rows or []
        self.history_rows = history_rows or []
        self.executemany_calls: list[tuple[str, list[tuple[object, ...]]]] = []
        self.execute_calls: list[tuple[str, tuple[object, ...]]] = []

    async def fetch(self, sql: str, *args) -> list[dict[str, object]]:
        if "last_seen_at >=" in sql:
            return self.cycle_rows
        if "status = ANY" in sql:
            requested_status = args[2][0]
            return self.active_rows if requested_status == "active" else self.delisted_rows
        if "FROM price_history" in sql:
            return self.history_rows
        return []

    async def execute(self, sql: str, *args) -> str:
        self.execute_calls.append((sql, args))
        return "OK"

    async def executemany(self, sql: str, args_iterable) -> None:
        self.executemany_calls.append((sql, list(args_iterable)))

    async def fetchval(self, sql: str, *args) -> object:
        return None


class _FakePool:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    def acquire(self) -> _Acquire:
        return _Acquire(self._conn)


class _FakeJetStream:
    def __init__(self) -> None:
        self.published: list[tuple[str, bytes]] = []

    async def publish(self, subject: str, payload: bytes) -> None:
        self.published.append((subject, payload))


def _settings() -> ChangeDetectorSettings:
    return ChangeDetectorSettings(database_url="postgresql://example", nats_url="nats://example")


@pytest.mark.asyncio
async def test_change_detector_handles_delist_relist_and_price_drop() -> None:
    drop_id = uuid4()
    missing_id = uuid4()
    relist_id = uuid4()
    conn = _FakeConn(
        active_rows=[
            {
                "id": drop_id,
                "country": "ES",
                "source": "idealista",
                "asking_price": Decimal("290000"),
                "asking_price_eur": Decimal("290000"),
                "currency": "EUR",
                "status": "active",
                "description_orig": "Current",
                "last_seen_at": datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
            },
            {
                "id": missing_id,
                "country": "ES",
                "source": "idealista",
                "asking_price": Decimal("180000"),
                "asking_price_eur": Decimal("180000"),
                "currency": "EUR",
                "status": "active",
                "description_orig": "Missing",
                "last_seen_at": datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
            },
        ],
        delisted_rows=[
            {
                "id": relist_id,
                "country": "ES",
                "source": "idealista",
                "asking_price": Decimal("200000"),
                "asking_price_eur": Decimal("200000"),
                "currency": "EUR",
                "status": "delisted",
                "description_orig": "Relisted",
                "last_seen_at": datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
            }
        ],
        history_rows=[
            {
                "listing_id": drop_id,
                "old_price": Decimal("300000"),
                "new_price": Decimal("300000"),
                "currency": "EUR",
                "old_price_eur": Decimal("300000"),
                "new_price_eur": Decimal("300000"),
            }
        ],
    )
    pool = _FakePool(conn)
    jetstream = _FakeJetStream()
    detector = Detector(_settings())
    event = ScrapeCycleEvent(
        cycle_id="cycle-1",
        portal="idealista",
        country="ES",
        completed_at=datetime(2026, 4, 17, 13, 0, tzinfo=UTC),
        listing_ids=[str(drop_id), str(relist_id)],
    )

    await detector.run_cycle(event, pool, jetstream)

    delist_args = conn.executemany_calls[0][1]
    relist_args = conn.executemany_calls[1][1]
    assert delist_args == [(missing_id, "ES")]
    assert relist_args == [(relist_id, "ES")]
    assert any("INSERT INTO price_history" in sql for sql, _ in conn.execute_calls)
    assert jetstream.published[0][0] == "listings.price-change.es"


@pytest.mark.asyncio
async def test_change_detector_does_not_publish_for_price_increase_or_equal_price() -> None:
    increase_id = uuid4()
    unchanged_id = uuid4()
    conn = _FakeConn(
        active_rows=[
            {
                "id": increase_id,
                "country": "ES",
                "source": "idealista",
                "asking_price": Decimal("310000"),
                "asking_price_eur": Decimal("310000"),
                "currency": "EUR",
                "status": "active",
                "description_orig": "Increase",
                "last_seen_at": datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
            },
            {
                "id": unchanged_id,
                "country": "ES",
                "source": "idealista",
                "asking_price": Decimal("290000"),
                "asking_price_eur": Decimal("290000"),
                "currency": "EUR",
                "status": "active",
                "description_orig": "Same",
                "last_seen_at": datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
            },
        ],
        history_rows=[
            {
                "listing_id": increase_id,
                "old_price": Decimal("300000"),
                "new_price": Decimal("300000"),
                "currency": "EUR",
                "old_price_eur": Decimal("300000"),
                "new_price_eur": Decimal("300000"),
            },
            {
                "listing_id": unchanged_id,
                "old_price": Decimal("290000"),
                "new_price": Decimal("290000"),
                "currency": "EUR",
                "old_price_eur": Decimal("290000"),
                "new_price_eur": Decimal("290000"),
            },
        ],
    )
    detector = Detector(_settings())
    jetstream = _FakeJetStream()
    event = ScrapeCycleEvent(
        cycle_id="cycle-2",
        portal="idealista",
        country="ES",
        completed_at=datetime(2026, 4, 17, 13, 0, tzinfo=UTC),
        listing_ids=[str(increase_id), str(unchanged_id)],
    )

    await detector.run_cycle(event, _FakePool(conn), jetstream)

    inserts = [sql for sql, _ in conn.execute_calls if "INSERT INTO price_history" in sql]
    assert len(inserts) == 1
    assert jetstream.published == []


@pytest.mark.asyncio
async def test_change_detector_resolves_cycle_members_from_db_when_ids_missing() -> None:
    listing_id = uuid4()
    conn = _FakeConn(cycle_rows=[{"id": listing_id}])
    detector = Detector(_settings())
    event = ScrapeCycleEvent(
        cycle_id="cycle-3",
        portal="idealista",
        country="ES",
        completed_at=datetime(2026, 4, 17, 13, 0, tzinfo=UTC),
        listing_ids=[],
    )

    resolved = await detector._resolve_cycle_listing_ids(event, _FakePool(conn))

    assert resolved == {listing_id}
