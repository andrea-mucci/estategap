"""Market-context adapter for downstream gRPC lookups."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel


def _grpc_error_types() -> tuple[type[BaseException], ...]:
    try:
        import grpc
    except ModuleNotFoundError:
        return ()
    return (grpc.aio.AioRpcError,)


class ZoneMarketData(BaseModel):
    """Market snapshot for a single zone."""

    zone_id: str
    zone_name: str
    median_price_eur: int
    deal_count: int
    listing_volume: int


class MarketData(BaseModel):
    """Market context payload injected into prompts."""

    zones: list[ZoneMarketData]
    fetched_at: str


class MarketContextClient:
    """Thin adapter around an injected downstream market-data fetcher."""

    def __init__(
        self,
        config: Any,
        fetcher: Callable[[list[str]], Awaitable[MarketData | dict[str, Any] | None]] | None = None,
    ) -> None:
        self._config = config
        self._fetcher = fetcher

    async def fetch(self, zone_ids: list[str]) -> MarketData | None:
        """Fetch market context with a 500 ms deadline, returning None on failure."""

        if not zone_ids or self._fetcher is None:
            return None
        try:
            result = await asyncio.wait_for(self._fetcher(zone_ids), timeout=0.5)
        except asyncio.TimeoutError:
            return None
        except Exception as exc:  # noqa: BLE001
            if _grpc_error_types() and isinstance(exc, _grpc_error_types()):
                return None
            raise
        if result is None:
            return None
        if isinstance(result, MarketData):
            return result
        return MarketData.model_validate(result)
