from __future__ import annotations

from collections.abc import AsyncIterator
from fnmatch import fnmatch
from types import SimpleNamespace
from typing import Any

import grpc
import pytest

from estategap_ai_chat.providers.base import BaseLLMProvider, LLMMessage


class FakeLLMProvider(BaseLLMProvider):
    """Deterministic streaming provider used in tests."""

    name = "fake"

    def __init__(self, responses: list[str | BaseException] | None = None) -> None:
        self._responses = list(responses or [])
        self.calls: list[dict[str, Any]] = []

    def push(self, response: str | BaseException) -> None:
        self._responses.append(response)

    async def generate(self, messages: list[LLMMessage], system: str) -> AsyncIterator[str]:
        self.calls.append({"messages": messages, "system": system})
        if not self._responses:
            return
        next_response = self._responses.pop(0)
        if isinstance(next_response, BaseException):
            raise next_response
        for chunk in _chunk_text(next_response):
            yield chunk


class FakeGatewayClient:
    """Async fake for search + alert finalization."""

    def __init__(
        self,
        *,
        listing_ids: list[str] | None = None,
        alert_rule_id: str = "",
    ) -> None:
        self.listing_ids = listing_ids or []
        self.alert_rule_id = alert_rule_id

    async def search_listings(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"listing_ids": self.listing_ids, "payload": payload}

    async def create_alert_rule(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {"alert_rule_id": self.alert_rule_id, "payload": payload}

    async def finalize(self, session_id: str, criteria: dict[str, Any]) -> tuple[list[str], str]:
        await self.search_listings({"session_id": session_id, "criteria": criteria})
        await self.create_alert_rule({"session_id": session_id, "criteria": criteria})
        return self.listing_ids, self.alert_rule_id


def _chunk_text(text: str, *, chunk_size: int = 12) -> list[str]:
    return [text[index : index + chunk_size] for index in range(0, len(text), chunk_size)]


class InMemoryRedis:
    """Small async Redis test double that covers the service's usage surface."""

    def __init__(self) -> None:
        self._hashes: dict[str, dict[str, str]] = {}
        self._lists: dict[str, list[str]] = {}
        self._sorted_sets: dict[str, dict[str, float]] = {}
        self._ttls: dict[str, int] = {}

    async def hset(
        self,
        key: str,
        field: str | None = None,
        value: str | None = None,
        *,
        mapping: dict[str, Any] | None = None,
    ) -> None:
        bucket = self._hashes.setdefault(key, {})
        if mapping is not None:
            for map_key, map_value in mapping.items():
                bucket[str(map_key)] = str(map_value)
            return
        if field is None or value is None:
            raise ValueError("field and value are required when mapping is absent")
        bucket[field] = value

    async def hgetall(self, key: str) -> dict[str, str]:
        return dict(self._hashes.get(key, {}))

    async def hincrby(self, key: str, field: str, amount: int) -> int:
        bucket = self._hashes.setdefault(key, {})
        current = int(bucket.get(field, "0")) + amount
        bucket[field] = str(current)
        return current

    async def rpush(self, key: str, value: str) -> None:
        self._lists.setdefault(key, []).append(value)

    async def ltrim(self, key: str, start: int, stop: int) -> None:
        values = self._lists.get(key, [])
        normalized_start = len(values) + start if start < 0 else start
        normalized_stop = len(values) + stop if stop < 0 else stop
        normalized_start = max(normalized_start, 0)
        normalized_stop = max(normalized_stop, -1)
        self._lists[key] = values[normalized_start : normalized_stop + 1]

    async def lrange(self, key: str, start: int, stop: int) -> list[str]:
        values = self._lists.get(key, [])
        normalized_start = len(values) + start if start < 0 else start
        normalized_stop = len(values) + stop if stop < 0 else stop
        normalized_start = max(normalized_start, 0)
        normalized_stop = len(values) - 1 if stop == -1 else normalized_stop
        return values[normalized_start : normalized_stop + 1]

    async def exists(self, key: str) -> int:
        return int(key in self._hashes or key in self._lists or key in self._sorted_sets)

    async def expire(self, key: str, seconds: int) -> None:
        self._ttls[key] = seconds

    async def ttl(self, key: str) -> int:
        return self._ttls.get(key, -1)

    async def zadd(self, key: str, mapping: dict[str, float]) -> None:
        bucket = self._sorted_sets.setdefault(key, {})
        bucket.update(mapping)

    async def zcount(self, key: str, _minimum: str, _maximum: str) -> int:
        return len(self._sorted_sets.get(key, {}))

    async def flushall(self) -> None:
        self._hashes.clear()
        self._lists.clear()
        self._sorted_sets.clear()
        self._ttls.clear()

    async def scan_iter(self, match: str) -> AsyncIterator[str]:
        keys = sorted({*self._hashes.keys(), *self._lists.keys(), *self._sorted_sets.keys()})
        for key in keys:
            if fnmatch(key, match):
                yield key

    async def aclose(self) -> None:
        return None


class FakeContext:
    """Minimal gRPC context double for direct servicer testing."""

    def __init__(self) -> None:
        self._metadata = [
            SimpleNamespace(key="x-user-id", value="user-1"),
            SimpleNamespace(key="x-subscription-tier", value="pro_plus"),
        ]

    def invocation_metadata(self) -> list[SimpleNamespace]:
        return self._metadata

    async def abort(self, code: grpc.StatusCode, details: str) -> None:
        raise RuntimeError(f"{code}:{details}")


@pytest.fixture
def config() -> SimpleNamespace:
    return SimpleNamespace(
        grpc_port=50053,
        metrics_port=9090,
        llm_provider="claude",
        fallback_llm_provider="openai",
        anthropic_api_key=None,
        openai_api_key=None,
        litellm_model="gpt-4o-mini",
        fake_llm_provider=False,
        redis_url="redis://localhost:6379/0",
        database_url="postgresql://estategap:password@localhost:5432/estategap",
        api_gateway_grpc_addr="localhost:50051",
        log_level="INFO",
    )


@pytest.fixture
def fake_llm_provider() -> FakeLLMProvider:
    return FakeLLMProvider(
        [
            (
                "Could you clarify your budget?\n"
                "```json\n"
                '{"status":"in_progress","confidence":0.6,"criteria":{"location":"milan"},'
                '"pending_dimensions":["price_range"],"suggested_chips":["< €500k"],'
                '"show_visual_references":false}\n'
                "```"
            )
        ]
    )


@pytest.fixture
async def redis_client() -> AsyncIterator[Any]:
    try:
        from fakeredis.aioredis import FakeRedis
    except ModuleNotFoundError:
        client = InMemoryRedis()
        yield client
        return

    client = FakeRedis(decode_responses=True)
    try:
        yield client
    finally:
        await client.flushall()
        await client.aclose()


@pytest.fixture
async def db_pool() -> AsyncIterator[Any]:
    try:
        import asyncpg
        from testcontainers.postgres import PostgresContainer
    except ModuleNotFoundError:
        yield None
        return

    container = PostgresContainer("postgis/postgis:16-3.4")
    try:
        container.start()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"Docker is not available for PostgreSQL tests: {exc}")
    pool = await asyncpg.create_pool(container.get_connection_url().replace("+psycopg2", ""))
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS visual_references (
                    id UUID PRIMARY KEY,
                    image_url TEXT NOT NULL,
                    tags TEXT[] NOT NULL DEFAULT '{}',
                    description TEXT,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                )
                """
            )
        yield pool
    finally:
        await pool.close()
        container.stop()
