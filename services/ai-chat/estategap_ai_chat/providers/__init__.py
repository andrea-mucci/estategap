"""Provider factory and retryable error definitions."""

from __future__ import annotations

import asyncio
from typing import Any, cast

from .base import BaseLLMProvider, LLMMessage
from .claude import ClaudeProvider
from .litellm import LiteLLMProvider
from .openai import OpenAIProvider


class _UnavailableProviderError(Exception):
    """Placeholder error type used when provider SDKs are unavailable."""


_openai_rate_limit: type[BaseException] = _UnavailableProviderError
_openai_connection: type[BaseException] = _UnavailableProviderError
_anthropic_rate_limit: type[BaseException] = _UnavailableProviderError
_anthropic_connection: type[BaseException] = _UnavailableProviderError

try:
    import openai
except ModuleNotFoundError:
    openai = None
else:
    _openai_rate_limit = openai.RateLimitError
    _openai_connection = openai.APIConnectionError

try:
    import anthropic
except ModuleNotFoundError:
    anthropic = None
else:
    _anthropic_rate_limit = anthropic.RateLimitError
    _anthropic_connection = anthropic.APIConnectionError


_REGISTRY: dict[str, type[Any]] = {
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
    "litellm": LiteLLMProvider,
}
RETRYABLE_ERRORS: tuple[type[BaseException], ...] = (
    asyncio.TimeoutError,
    _openai_rate_limit,
    _openai_connection,
    _anthropic_rate_limit,
    _anthropic_connection,
)


def get_provider(name: str, config: object) -> BaseLLMProvider:
    """Instantiate a provider by name."""

    provider_cls = _REGISTRY.get(name)
    if provider_cls is None:
        raise ValueError(f"Unknown LLM provider: {name!r}")
    return cast(BaseLLMProvider, provider_cls(config))


__all__ = ["BaseLLMProvider", "LLMMessage", "RETRYABLE_ERRORS", "get_provider"]
