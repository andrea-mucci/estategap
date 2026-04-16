"""Async NATS JetStream client wrapper."""

from collections.abc import Callable
from typing import Any

import nats
from nats.aio.client import Client


class NatsClient:
    """Async NATS client with JetStream support."""

    def __init__(self) -> None:
        self._nc: Client | None = None

    async def connect(self, url: str) -> None:
        self._nc = await nats.connect(url)

    @property
    def _conn(self) -> Client:
        if self._nc is None:
            msg = "Not connected. Call connect() first."
            raise RuntimeError(msg)
        return self._nc

    async def publish(self, subject: str, payload: bytes) -> None:
        await self._conn.publish(subject, payload)

    async def subscribe(self, subject: str, cb: Callable[..., Any]) -> None:
        await self._conn.subscribe(subject, cb=cb)

    async def close(self) -> None:
        if self._nc is not None:
            await self._nc.close()
            self._nc = None
