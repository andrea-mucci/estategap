from __future__ import annotations


class FakeMsg:
    def __init__(self, data: bytes, headers: dict[str, str] | None = None) -> None:
        self.data = data
        self.headers = headers or {}
        self.acked = False
        self.nacked = False

    async def ack(self) -> None:
        self.acked = True

    async def nak(self) -> None:
        self.nacked = True
