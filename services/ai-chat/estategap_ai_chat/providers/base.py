"""LLM provider abstractions."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass


@dataclass(slots=True)
class LLMMessage:
    """A normalized LLM chat message."""

    role: str
    content: str


class BaseLLMProvider(ABC):
    """Abstract streaming text generation provider."""

    name = "unknown"

    @abstractmethod
    def generate(self, messages: list[LLMMessage], system: str) -> AsyncIterator[str]:
        """Yield streamed text fragments for a chat completion."""
