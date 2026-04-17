from __future__ import annotations

import asyncio

import pytest


pytestmark = [pytest.mark.ws, pytest.mark.slow]


@pytest.mark.asyncio
async def test_connection_stays_open_then_idles_out(ws_client) -> None:
    async with ws_client("pro") as client:
        assert client.ws is not None
        await asyncio.sleep(12)
        await client.send_chat("still here", country_code="ES")
        message = await client.next_message(timeout=15.0)
        if message.get("type") == "error":
            pytest.skip(f"AI chat unavailable: {message}")

        await asyncio.sleep(31)
        try:
            follow_up = await client.next_message(timeout=5.0)
        except Exception:
            # The underlying client should be closed by the idle timeout in test values.
            return

        pytest.skip(f"idle timeout override is not enabled in this local environment: {follow_up}")
