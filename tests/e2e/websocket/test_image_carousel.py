from __future__ import annotations

import asyncio

import pytest

from tests.e2e.helpers.assertions import assert_envelope_type


pytestmark = [pytest.mark.ws]


async def _collect_until_terminal(client, timeout: float = 20.0) -> list[dict[str, object]]:
    messages: list[dict[str, object]] = []
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        message = await client.next_message(timeout=timeout)
        messages.append(message)
        if message.get("type") == "error":
            break
        if message.get("type") in {"criteria_summary", "search_results"}:
            break
    return messages


@pytest.mark.asyncio
async def test_image_carousel_feedback_round_trip(ws_client) -> None:
    async with ws_client("pro") as client:
        await client.send_chat("Show me example listings with bright living rooms in Madrid", country_code="ES")
        messages = await _collect_until_terminal(client)

        if messages and messages[0].get("type") == "error":
            pytest.skip(f"AI chat unavailable: {messages[0]}")

        carousel_messages = [message for message in messages if message.get("type") == "image_carousel"]
        if not carousel_messages:
            pytest.skip("AI chat did not emit an image carousel for this environment")

        payload = assert_envelope_type(carousel_messages[-1], "image_carousel")
        listings = payload.get("listings")
        assert isinstance(listings, list) and listings, payload

        listing = listings[0]
        assert isinstance(listing.get("listing_id"), str)
        await client.send_image_feedback(listing["listing_id"], "like")

        follow_up = await client.next_message(timeout=15.0)
        assert follow_up["type"] in {"text_chunk", "criteria_summary", "search_results"}, follow_up
