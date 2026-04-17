from __future__ import annotations

import asyncio

import pytest


pytestmark = [pytest.mark.concurrency]


@pytest.mark.asyncio
async def test_many_chat_sessions_do_not_cross_talk(ws_client) -> None:
    total_clients = 100

    async def run_one(index: int) -> str:
        async with ws_client("pro") as client:
            await client.send_chat(f"Client {index} looking for Madrid flats", country_code="ES")
            message = await client.next_message(timeout=20.0)
            if message.get("type") == "error":
                raise RuntimeError("ai_unavailable")
            return str(message.get("session_id") or "")

    try:
        session_ids = await asyncio.gather(*(run_one(index) for index in range(total_clients)))
    except RuntimeError:
        pytest.skip("AI chat backend is not available for the high-concurrency scenario")

    assert len(session_ids) == total_clients
    assert all(session_id for session_id in session_ids)
    assert len(set(session_ids)) == total_clients
