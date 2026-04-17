"""Redis-backed conversation session storage."""

from __future__ import annotations

from datetime import UTC, datetime
import json
from typing import Any

from .providers.base import LLMMessage


SESSION_TTL_SECONDS = 24 * 60 * 60
MESSAGE_WINDOW_SIZE = 40


def _utcnow() -> str:
    return datetime.now(tz=UTC).isoformat()


def _decode(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8")
    return str(value)


class ConversationSession:
    """Redis helpers for mutable conversation state plus message history."""

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client

    @staticmethod
    def _hash_key(session_id: str) -> str:
        return f"conv:{session_id}"

    @staticmethod
    def _messages_key(session_id: str) -> str:
        return f"conv:{session_id}:messages"

    async def create(self, session_id: str, user_id: str, language: str, tier: str) -> None:
        timestamp = _utcnow()
        await self._redis.hset(
            self._hash_key(session_id),
            mapping={
                "user_id": user_id,
                "language": language,
                "criteria_state": "{}",
                "turn_count": "0",
                "created_at": timestamp,
                "last_active_at": timestamp,
                "subscription_tier": tier,
                "preview": "",
            },
        )
        await self._touch(session_id)

    async def get(self, session_id: str) -> dict[str, str]:
        data = await self._redis.hgetall(self._hash_key(session_id))
        return {_decode(key): _decode(value) for key, value in data.items()}

    async def update_criteria(self, session_id: str, criteria_json: dict[str, Any] | str) -> None:
        payload = criteria_json if isinstance(criteria_json, str) else json.dumps(criteria_json)
        await self._redis.hset(
            self._hash_key(session_id),
            mapping={
                "criteria_state": payload,
                "last_active_at": _utcnow(),
            },
        )
        await self._touch(session_id)

    async def increment_turn(self, session_id: str) -> int:
        turn_count = await self._redis.hincrby(self._hash_key(session_id), "turn_count", 1)
        await self._redis.hset(self._hash_key(session_id), "last_active_at", _utcnow())
        await self._touch(session_id)
        return int(turn_count)

    async def append_message(self, session_id: str, role: str, content: str) -> None:
        message = json.dumps(
            {
                "role": role,
                "content": content,
                "timestamp": _utcnow(),
            }
        )
        await self._redis.rpush(self._messages_key(session_id), message)
        await self._redis.ltrim(self._messages_key(session_id), -MESSAGE_WINDOW_SIZE, -1)
        preview = " ".join(content.split())[:160]
        await self._redis.hset(
            self._hash_key(session_id),
            mapping={
                "last_active_at": _utcnow(),
                "preview": preview,
            },
        )
        await self._touch(session_id)

    async def get_messages(self, session_id: str) -> list[LLMMessage]:
        raw_messages = await self._redis.lrange(self._messages_key(session_id), 0, -1)
        messages: list[LLMMessage] = []
        for item in raw_messages:
            payload = json.loads(_decode(item))
            messages.append(
                LLMMessage(
                    role=str(payload["role"]),
                    content=str(payload["content"]),
                )
            )
        return messages

    async def exists(self, session_id: str) -> bool:
        return bool(await self._redis.exists(self._hash_key(session_id)))

    async def _touch(self, session_id: str) -> None:
        await self._redis.expire(self._hash_key(session_id), SESSION_TTL_SECONDS)
        await self._redis.expire(self._messages_key(session_id), SESSION_TTL_SECONDS)
