"""LiteLLM streaming provider."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from .base import BaseLLMProvider, LLMMessage


class LiteLLMProvider(BaseLLMProvider):
    """LiteLLM streaming provider."""

    name = "litellm"

    def __init__(self, config: Any) -> None:
        self._model = config.litellm_model or "gpt-4o-mini"

    async def generate(self, messages: list[LLMMessage], system: str) -> AsyncIterator[str]:
        from litellm import acompletion

        payload = [{"role": "system", "content": system}]
        payload.extend(
            {"role": message.role, "content": message.content}
            for message in messages
            if message.role in {"user", "assistant", "system"}
        )
        stream = await acompletion(
            model=self._model,
            messages=payload,
            stream=True,
        )
        async for chunk in stream:
            choices = getattr(chunk, "choices", None) or []
            if not choices:
                continue
            delta = getattr(choices[0], "delta", None)
            content = getattr(delta, "content", None) if delta is not None else None
            if content:
                yield content
