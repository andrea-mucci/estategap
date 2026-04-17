from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import grpc
import pytest

from estategap.v1 import ai_chat_pb2
from estategap_ai_chat.servicer import AIChatServicer
from estategap_ai_chat.providers import get_provider

from tests.conftest import FakeGatewayClient, FakeLLMProvider


class AbortCalled(Exception):
    def __init__(self, code: grpc.StatusCode, details: str) -> None:
        super().__init__(details)
        self.code = code
        self.details = details


class FakeContext:
    def __init__(self) -> None:
        self._metadata = [
            SimpleNamespace(key="x-user-id", value="user-1"),
            SimpleNamespace(key="x-subscription-tier", value="pro_plus"),
        ]

    def invocation_metadata(self) -> list[SimpleNamespace]:
        return self._metadata

    async def abort(self, code: grpc.StatusCode, details: str) -> None:
        raise AbortCalled(code, details)


async def _request_iter(*requests: ai_chat_pb2.ChatRequest) -> AsyncIterator[ai_chat_pb2.ChatRequest]:
    for request in requests:
        yield request


def test_provider_factory_returns_known_providers(config: SimpleNamespace) -> None:
    assert get_provider("claude", config).__class__.__name__ == "ClaudeProvider"
    assert get_provider("openai", config).__class__.__name__ == "OpenAIProvider"
    assert get_provider("litellm", config).__class__.__name__ == "LiteLLMProvider"


@pytest.mark.asyncio
async def test_chat_uses_fallback_provider_on_retryable_error(
    redis_client: Any,
    config: SimpleNamespace,
) -> None:
    primary = FakeLLMProvider([asyncio.TimeoutError("primary timeout")])
    fallback = FakeLLMProvider(
        [
            "Fallback reply\n```json\n"
            '{"status":"in_progress","confidence":0.7,"criteria":{"location":"rome"},'
            '"pending_dimensions":["price_range"],"suggested_chips":["city center"],'
            '"show_visual_references":false}\n```'
        ]
    )
    servicer = AIChatServicer(
        config=config,
        db_pool=None,
        redis_client=redis_client,
        llm_provider=primary,
        fallback_provider=fallback,
        criteria_finalizer=FakeGatewayClient(),
    )

    responses = [
        response
        async for response in servicer.Chat(
            _request_iter(
                ai_chat_pb2.ChatRequest(
                    conversation_id="",
                    user_message="Find me something in Rome",
                    country_code="IT",
                )
            ),
            FakeContext(),
        )
    ]

    streamed_text = "".join(response.chunk for response in responses if not response.is_final)
    assert "Fallback reply" in streamed_text
    assert responses[-1].is_final is True


@pytest.mark.asyncio
async def test_chat_aborts_when_primary_and_fallback_fail(
    redis_client: Any,
    config: SimpleNamespace,
) -> None:
    servicer = AIChatServicer(
        config=config,
        db_pool=None,
        redis_client=redis_client,
        llm_provider=FakeLLMProvider([asyncio.TimeoutError("primary timeout")]),
        fallback_provider=FakeLLMProvider([asyncio.TimeoutError("fallback timeout")]),
    )

    with pytest.raises(AbortCalled) as excinfo:
        async for _response in servicer.Chat(
            _request_iter(
                ai_chat_pb2.ChatRequest(
                    conversation_id="",
                    user_message="Find me something in Rome",
                    country_code="IT",
                )
            ),
            FakeContext(),
        ):
            pass

    assert excinfo.value.code == grpc.StatusCode.INTERNAL
