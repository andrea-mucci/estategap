from __future__ import annotations

from redis.asyncio import Redis


async def flush_test_run_keys(redis_url: str, run_id: str) -> int:
    client = Redis.from_url(redis_url, decode_responses=True)
    deleted = 0
    try:
        async for key in client.scan_iter(match=f"test-run:{run_id}:*"):
            deleted += await client.delete(key)
    finally:
        await client.aclose()
    return deleted
