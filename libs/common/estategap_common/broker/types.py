"""Transport-agnostic broker message types."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field


@dataclass(slots=True)
class Message:
    """Canonical event envelope delivered to service handlers."""

    key: str
    value: bytes
    topic: str
    headers: dict[str, str] = field(default_factory=dict)


MessageHandler = Callable[[Message], Awaitable[None]]

__all__ = ["Message", "MessageHandler"]
