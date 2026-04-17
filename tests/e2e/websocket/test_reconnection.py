from __future__ import annotations

import pytest


pytestmark = [pytest.mark.ws]


@pytest.mark.asyncio
async def test_session_can_reconnect_with_same_session_id(ws_client) -> None:
    first_session_id: str | None = None

    async with ws_client("pro") as client:
        await client.send_chat("Remember that I want properties in Madrid", country_code="ES")
        message = await client.next_message(timeout=15.0)
        if message.get("type") == "error":
            pytest.skip(f"AI chat unavailable: {message}")
        first_session_id = message.get("session_id")
        assert first_session_id

    async with ws_client("pro") as client:
        await client.send_chat(
            "Continue the same conversation",
            session_id=first_session_id,
            country_code="ES",
        )
        message = await client.next_message(timeout=15.0)
        assert message.get("type") in {"text_chunk", "criteria_summary", "search_results", "error"}
        if message.get("type") != "error":
            assert message.get("session_id") == first_session_id
