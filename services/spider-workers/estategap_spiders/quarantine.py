"""Redis-backed quarantine store for permanently failing URLs."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel


class QuarantineEntry(BaseModel):
    """Serialised quarantine metadata."""

    url: str
    portal: str
    country: str
    error: str
    attempt_count: int = 1
    quarantined_at: datetime


class QuarantineStore:
    """Store permanently failing URLs in Redis hashes."""

    def __init__(self, redis_client, ttl_days: int) -> None:
        self._redis = redis_client
        self._ttl_seconds = ttl_days * 24 * 60 * 60

    async def add(self, url: str, portal: str, country: str, error: str) -> None:
        entry = QuarantineEntry(
            url=url,
            portal=portal.lower(),
            country=country.lower(),
            error=error,
            quarantined_at=datetime.now(UTC),
        )
        key = self._key(portal, country)
        await self._redis.hset(key, url, entry.model_dump_json())
        await self._redis.expire(key, self._ttl_seconds)

    async def is_quarantined(self, url: str, portal: str, country: str) -> bool:
        return bool(await self._redis.hexists(self._key(portal, country), url))

    @staticmethod
    def _key(portal: str, country: str) -> str:
        return f"quarantine:{portal.lower()}:{country.lower()}"
