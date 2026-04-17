"""CLI entry point for the AI chat service."""

from __future__ import annotations

import asyncio

from estategap_common.db import create_pool
from estategap_common.logging import configure_logging
import redis.asyncio as redis

from .config import Config
from .providers import get_provider
from .server import serve


async def main() -> int:
    """Boot the AI chat service."""

    config = Config()  # type: ignore[call-arg]
    configure_logging(level=config.log_level, service="ai-chat")
    db_pool = None
    redis_client = None
    try:
        db_pool = await create_pool(config.database_url)
        redis_client = redis.from_url(config.redis_url, decode_responses=True)
        llm_provider = get_provider(config.llm_provider, config)
        fallback_provider = get_provider(config.fallback_llm_provider, config)
        await serve(
            config=config,
            db_pool=db_pool,
            redis_client=redis_client,
            llm_provider=llm_provider,
            fallback_provider=fallback_provider,
        )
        return 0
    finally:
        if redis_client is not None:
            await redis_client.aclose()
        if db_pool is not None:
            await db_pool.close()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
