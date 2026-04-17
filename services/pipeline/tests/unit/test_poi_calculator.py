from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import httpx
import pytest

from estategap_common.models import NormalizedListing
from pipeline.enricher.poi import POIDistanceCalculator, _haversine_m


def _listing() -> NormalizedListing:
    return NormalizedListing.model_validate(
        {
            "id": uuid4(),
            "country": "ES",
            "source": "idealista",
            "source_id": "listing-123",
            "source_url": "https://www.idealista.com/inmueble/listing-123/",
            "location_wkt": "POINT(-3.7038 40.4168)",
            "asking_price": Decimal("450000"),
            "currency": "EUR",
            "asking_price_eur": Decimal("450000"),
            "built_area_m2": Decimal("80"),
            "first_seen_at": datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
            "last_seen_at": datetime(2026, 4, 17, 12, 0, tzinfo=UTC),
        }
    )


class _Acquire(AbstractAsyncContextManager["_FakeConn"]):
    def __init__(self, conn: "_FakeConn") -> None:
        self._conn = conn

    async def __aenter__(self) -> "_FakeConn":
        return self._conn

    async def __aexit__(self, exc_type, exc, tb) -> None:
        return None


class _FakeConn:
    def __init__(self, distances: dict[str, int | None]) -> None:
        self.distances = distances
        self.calls: list[str] = []

    async def fetchrow(self, sql: str, *_args) -> dict[str, int] | None:
        category = _args[2]
        self.calls.append(category)
        distance = self.distances.get(category)
        if distance is None:
            return None
        return {"dist_m": distance}


class _FakePool:
    def __init__(self, conn: _FakeConn) -> None:
        self._conn = conn

    def acquire(self) -> _Acquire:
        return _Acquire(self._conn)


@pytest.mark.asyncio
async def test_poi_calculator_prefers_postgis_distances() -> None:
    conn = _FakeConn({"metro": 120, "train": None, "airport": None, "park": None, "beach": None})
    pool = _FakePool(conn)
    calculator = POIDistanceCalculator(pool=pool, overpass_url="https://example.test", overpass_cache={})
    calculator._overpass_fallback = AsyncMock(side_effect=[210, 320, 430, 540])  # type: ignore[method-assign]

    result = await calculator.calculate(_listing())

    assert result["dist_metro_m"] == 120
    assert result["dist_train_m"] == 210
    assert result["dist_airport_m"] == 320
    assert result["dist_park_m"] == 430
    assert result["dist_beach_m"] == 540
    assert calculator._overpass_fallback.await_count == 4  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_overpass_fallback_uses_haversine_distance() -> None:
    client = AsyncMock()
    client.post.return_value = httpx.Response(
        200,
        json={"elements": [{"lat": 40.4170, "lon": -3.7040}]},
        request=httpx.Request("POST", "https://example.test"),
    )
    calculator = POIDistanceCalculator(
        pool=_FakePool(_FakeConn({})),
        overpass_url="https://example.test",
        overpass_cache={},
        client=client,
    )

    result = await calculator._overpass_fallback(40.4168, -3.7038, "park")

    assert result == _haversine_m(40.4168, -3.7038, 40.4170, -3.7040)


@pytest.mark.asyncio
async def test_overpass_fallback_returns_none_when_no_data() -> None:
    client = AsyncMock()
    client.post.return_value = httpx.Response(
        200,
        json={"elements": []},
        request=httpx.Request("POST", "https://example.test"),
    )
    calculator = POIDistanceCalculator(
        pool=_FakePool(_FakeConn({})),
        overpass_url="https://example.test",
        overpass_cache={},
        client=client,
    )

    result = await calculator._overpass_fallback(40.4168, -3.7038, "beach")

    assert result is None
