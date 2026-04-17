"""Deterministic provider used for test-mode deployments."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from .base import BaseLLMProvider, LLMMessage

FAKE_RESPONSE = "This is a test response from FakeLLMProvider. Found 3 matching properties in your area."


class FakeLLMProvider(BaseLLMProvider):
    """Yield a stable canned response without making outbound calls."""

    name = "fake"

    def __init__(self, _config: Any) -> None:
        return None

    async def generate(self, messages: list[LLMMessage], system: str) -> AsyncIterator[str]:
        del messages, system
        chunk_size = 16
        for index in range(0, len(FAKE_RESPONSE), chunk_size):
            yield FAKE_RESPONSE[index : index + chunk_size]
