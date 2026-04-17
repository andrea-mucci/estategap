from __future__ import annotations


class FakeMsg:
    def __init__(self, data: bytes, headers: dict[str, str] | None = None) -> None:
        self.data = data
        self.value = data
        self.headers = headers or {}
