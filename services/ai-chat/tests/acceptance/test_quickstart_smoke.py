from __future__ import annotations

from collections.abc import AsyncIterator
from types import SimpleNamespace

import pytest

from estategap.v1 import ai_chat_pb2
from estategap_ai_chat.servicer import AIChatServicer

from tests.conftest import FakeContext, FakeGatewayClient, FakeLLMProvider, InMemoryRedis


async def _request_iter() -> AsyncIterator[ai_chat_pb2.ChatRequest]:
    yield ai_chat_pb2.ChatRequest(
        conversation_id="",
        user_message="Ciao, cerco un appartamento a Milano",
        country_code="IT",
    )


@pytest.mark.asyncio
async def test_quickstart_smoke_streams_tokens_and_criteria_json(
    config: SimpleNamespace,
) -> None:
    provider = FakeLLMProvider(
        [
            "Ciao! Che budget hai in mente?\n```json\n"
            '{"status":"in_progress","confidence":0.63,"criteria":{"location":"milan"},'
            '"pending_dimensions":["price_range"],"suggested_chips":["< €500k"],'
            '"show_visual_references":false}\n```',
        ]
    )
    servicer = AIChatServicer(
        config=config,
        db_pool=None,
        redis_client=InMemoryRedis(),
        llm_provider=provider,
        fallback_provider=provider,
        criteria_finalizer=FakeGatewayClient(),
    )
    responses = [response async for response in servicer.Chat(_request_iter(), FakeContext())]

    assert responses
    assert responses[-1].is_final is True
    assert responses[-1].conversation_id

    streamed_text = "".join(response.chunk for response in responses if response.chunk)
    assert "Ciao!" in streamed_text
    assert "```json" in streamed_text
    assert '"status":"in_progress"' in streamed_text
