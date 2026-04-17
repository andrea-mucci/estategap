from __future__ import annotations

import httpx
import pytest


pytestmark = [pytest.mark.ws]


@pytest.mark.asyncio
async def test_valid_token_connects(ws_client) -> None:
    async with ws_client("pro") as client:
        assert client.ws is not None
        assert client.received == []


@pytest.mark.asyncio
async def test_missing_or_invalid_token_is_rejected(ws_base_url: str) -> None:
    http_base = ws_base_url.replace("ws://", "http://").rstrip("/")
    async with httpx.AsyncClient(base_url=http_base, timeout=10.0) as client:
        missing = await client.get("/ws/chat")
        assert missing.status_code == 401, missing.text

        invalid = await client.get("/ws/chat", params={"token": "not-a-real-jwt"})
        assert invalid.status_code == 401, invalid.text
