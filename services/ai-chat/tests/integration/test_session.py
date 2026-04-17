from __future__ import annotations

import json
from typing import Any

import pytest

from estategap_ai_chat.session import ConversationSession


@pytest.mark.asyncio
async def test_conversation_session_create_update_append_and_trim(redis_client: Any) -> None:
    session = ConversationSession(redis_client)
    session_id = "session-1"

    await session.create(session_id, user_id="user-1", language="en", tier="free")
    await session.update_criteria(session_id, {"status": "in_progress"})
    for index in range(45):
        await session.append_message(session_id, "user", f"message-{index}")
    await session.increment_turn(session_id)

    payload = await session.get(session_id)
    messages = await session.get_messages(session_id)

    assert payload["user_id"] == "user-1"
    assert json.loads(payload["criteria_state"]) == {"status": "in_progress"}
    assert payload["turn_count"] == "1"
    assert len(messages) == 40
    assert messages[0].content == "message-5"
    assert messages[-1].content == "message-44"
    assert await redis_client.ttl("conv:session-1") > 0
    assert await redis_client.ttl("conv:session-1:messages") > 0
