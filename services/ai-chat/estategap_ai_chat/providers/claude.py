"""Anthropic Claude provider."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from .base import BaseLLMProvider, LLMMessage


class ClaudeProvider(BaseLLMProvider):
    """Anthropic Claude streaming provider."""

    name = "claude"

    def __init__(self, config: Any) -> None:
        self._api_key = config.anthropic_api_key
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=self._api_key)
        return self._client

    async def generate(self, messages: list[LLMMessage], system: str) -> AsyncIterator[str]:
        client = self._get_client()
        payload = [
            {"role": message.role, "content": message.content}
            for message in messages
            if message.role in {"user", "assistant"}
        ]
        async with client.messages.stream(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            stream=True,
            system=system,
            messages=payload,
        ) as stream:
            async for chunk in stream.text_stream:
                if chunk:
                    yield chunk
