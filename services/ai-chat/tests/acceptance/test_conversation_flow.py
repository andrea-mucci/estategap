from __future__ import annotations

import json
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest

from estategap.v1 import ai_chat_pb2
from estategap_ai_chat.servicer import AIChatServicer

from tests.conftest import FakeContext, FakeGatewayClient, FakeLLMProvider


async def _request_iter() -> AsyncIterator[ai_chat_pb2.ChatRequest]:
    requests = [
        ai_chat_pb2.ChatRequest(conversation_id="", user_message="I want a place in Milan", country_code="IT"),
        ai_chat_pb2.ChatRequest(conversation_id="", user_message="Budget up to 500k", country_code="IT"),
        ai_chat_pb2.ChatRequest(conversation_id="", user_message="2 bedrooms please", country_code="IT"),
    ]
    for request in requests:
        yield request


@pytest.mark.asyncio
async def test_three_turn_conversation_updates_session_state(
    redis_client: Any,
    config: SimpleNamespace,
) -> None:
    provider = FakeLLMProvider(
        [
            "Let's narrow that down.\n```json\n"
            '{"status":"in_progress","confidence":0.55,"criteria":{"location":"milan"},'
            '"pending_dimensions":["price_range","bedrooms"],"suggested_chips":["city center"],'
            '"show_visual_references":false}\n```',
            "Great, budget noted.\n```json\n"
            '{"status":"in_progress","confidence":0.72,"criteria":{"location":"milan","price_range":{"max":500000}},'
            '"pending_dimensions":["bedrooms"],"suggested_chips":["2 bedrooms"],'
            '"show_visual_references":false}\n```',
            "Perfect, here is the refined search.\n```json\n"
            '{"status":"ready","confidence":0.91,"criteria":{"location":"milan","price_range":{"max":500000},"bedrooms":2},'
            '"pending_dimensions":[],"suggested_chips":["search now"],'
            '"show_visual_references":false}\n```',
        ]
    )
    servicer = AIChatServicer(
        config=config,
        db_pool=None,
        redis_client=redis_client,
        llm_provider=provider,
        fallback_provider=provider,
        criteria_finalizer=FakeGatewayClient(),
    )

    responses = [response async for response in servicer.Chat(_request_iter(), FakeContext())]

    final_responses = [response for response in responses if response.is_final]
    assert len(final_responses) == 3

    conversation_id = final_responses[-1].conversation_id
    session_data = await redis_client.hgetall(f"conv:{conversation_id}")
    assert session_data["turn_count"] == "3"
    criteria_state = json.loads(session_data["criteria_state"])
    assert criteria_state["criteria"]["location"] == "milan"
    assert criteria_state["criteria"]["bedrooms"] == 2
