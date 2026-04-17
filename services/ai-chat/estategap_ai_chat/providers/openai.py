"""OpenAI streaming provider."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from .base import BaseLLMProvider, LLMMessage


class OpenAIProvider(BaseLLMProvider):
    """OpenAI chat-completions streaming provider."""

    name = "openai"

    def __init__(self, config: Any) -> None:
        self._api_key = config.openai_api_key
        self._client: Any | None = None

    def _get_client(self) -> Any:
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(api_key=self._api_key)
        return self._client

    async def generate(self, messages: list[LLMMessage], system: str) -> AsyncIterator[str]:
        client = self._get_client()
        payload = [{"role": "system", "content": system}]
        payload.extend(
            {"role": message.role, "content": message.content}
            for message in messages
            if message.role in {"user", "assistant", "system"}
        )
        stream = await client.chat.completions.create(
            model="gpt-4o",
            messages=payload,
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content if chunk.choices else None
            if delta:
                yield delta
