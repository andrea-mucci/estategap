"""asyncpg connection-pool helpers for the pipeline workers."""

from __future__ import annotations

import asyncpg  # type: ignore[import-untyped]


async def create_pool(dsn: str) -> asyncpg.Pool:
    """Create the shared asyncpg pool used by the pipeline workers."""

    return await asyncpg.create_pool(
        dsn,
        min_size=2,
        max_size=10,
        command_timeout=30,
    )


__all__ = ["create_pool"]
