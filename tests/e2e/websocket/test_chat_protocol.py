from __future__ import annotations

import asyncio
from typing import Any

import pytest

from tests.e2e.helpers.assertions import assert_envelope_type


pytestmark = [pytest.mark.ws]


async def _collect_until_terminal(client, timeout: float = 20.0) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        message = await client.next_message(timeout=timeout)
        messages.append(message)
        if message.get("type") == "error":
            break
        if message.get("type") == "search_results":
            break
        if message.get("type") == "text_chunk" and message.get("payload", {}).get("is_final") is True:
            break
    return messages


@pytest.mark.asyncio
async def test_chat_streams_text_and_optional_summary(ws_client) -> None:
    async with ws_client("pro") as client:
        await client.send_chat("Find me a good apartment in Madrid under 500k", country_code="ES")
        messages = await _collect_until_terminal(client)
        assert messages, "expected at least one websocket message"

        if messages[0].get("type") == "error":
            pytest.skip(f"AI chat unavailable: {messages[0]}")

        text_chunks = [message for message in messages if message.get("type") == "text_chunk"]
        assert text_chunks, messages
        final_chunk = text_chunks[-1]
        payload = assert_envelope_type(final_chunk, "text_chunk")
        assert isinstance(payload["text"], str)

        criteria_messages = [m for m in client.received if m.get("type") == "criteria_summary"]
        if criteria_messages:
            summary = assert_envelope_type(criteria_messages[-1], "criteria_summary")
            assert isinstance(summary.get("ready_to_search"), bool)

        chips_messages = [m for m in client.received if m.get("type") == "chips"]
        if chips_messages:
            chips = assert_envelope_type(chips_messages[-1], "chips")
            assert isinstance(chips.get("options"), list)
