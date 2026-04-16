"""asyncpg database session factory."""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Any

import asyncpg  # type: ignore[import-untyped]


async def create_pool(dsn: str) -> Any:
    """Create and return an asyncpg connection pool."""
    return await asyncpg.create_pool(dsn)


@asynccontextmanager
async def get_connection(pool: Any) -> AsyncIterator[Any]:
    """Acquire a connection from the pool as an async context manager."""
    conn = await pool.acquire()
    try:
        yield conn
    finally:
        await pool.release(conn)
