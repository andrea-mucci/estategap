from __future__ import annotations

import asyncio
import json
from typing import Any

from websockets.asyncio.client import connect
from websockets.client import ClientConnection


class WSTestClient:
    def __init__(self, url: str) -> None:
        self.url = url
        self.ws: ClientConnection | None = None
        self.received: list[dict[str, Any]] = []
        self.session_id: str | None = None

    async def __aenter__(self) -> "WSTestClient":
        self.ws = await connect(self.url)
        return self

    async def __aexit__(self, *_args: object) -> None:
        if self.ws is not None:
            await self.ws.close()

    async def send_chat(self, text: str, session_id: str | None = None, country_code: str = "ES") -> None:
        assert self.ws is not None, "websocket is not connected"
        await self.ws.send(
            json.dumps(
                {
                    "type": "chat_message",
                    "session_id": session_id or self.session_id or "",
                    "payload": {
                        "user_message": text,
                        "country_code": country_code,
                    },
                }
            )
        )

    async def send_image_feedback(self, listing_id: str, action: str) -> None:
        assert self.ws is not None, "websocket is not connected"
        await self.ws.send(
            json.dumps(
                {
                    "type": "image_feedback",
                    "session_id": self.session_id or "",
                    "payload": {"listing_id": listing_id, "action": action},
                }
            )
        )

    async def send_criteria_confirm(self, confirmed: bool = True, notes: str = "") -> None:
        assert self.ws is not None, "websocket is not connected"
        await self.ws.send(
            json.dumps(
                {
                    "type": "criteria_confirm",
                    "session_id": self.session_id or "",
                    "payload": {"confirmed": confirmed, "notes": notes},
                }
            )
        )

    async def next_message(self, timeout: float = 10.0) -> dict[str, Any]:
        assert self.ws is not None, "websocket is not connected"
        raw = await asyncio.wait_for(self.ws.recv(), timeout=timeout)
        message = json.loads(raw)
        if isinstance(message.get("session_id"), str) and message["session_id"]:
            self.session_id = message["session_id"]
        self.received.append(message)
        return message

    async def collect_messages(self, until_type: str, timeout: float = 10.0) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = []
        while True:
            message = await self.next_message(timeout=timeout)
            messages.append(message)
            if message.get("type") == until_type:
                break
        return messages

    def clear(self) -> None:
        self.received.clear()
