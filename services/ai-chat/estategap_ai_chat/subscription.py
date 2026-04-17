"""Subscription-tier usage limits."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4


class LimitExceededError(RuntimeError):
    """Raised when a subscription limit is exceeded."""


TIER_LIMITS: dict[str, tuple[int | None, int | None]] = {
    "free": (3, 10),
    "basic": (10, 20),
    "pro_plus": (None, None),
    "pro": (None, None),
    "global": (None, None),
    "api": (None, None),
}


def _normalize_tier(tier: str) -> str:
    return tier.strip().lower() or "free"


def _counter_key(user_id: str, now: datetime) -> str:
    return f"sub:{user_id}:convs:{now.date().isoformat()}"


async def register_conversation(
    user_id: str,
    tier: str,
    redis_client: Any,
    session_id: str | None = None,
    *,
    now: datetime | None = None,
) -> None:
    """Record a successful new conversation in the daily counter."""

    del tier
    moment = now or datetime.now(tz=UTC)
    member = session_id or str(uuid4())
    key = _counter_key(user_id, moment)
    await redis_client.zadd(key, {member: moment.timestamp()})
    await redis_client.expire(key, 90_000)


async def check_conversation_limit(
    user_id: str,
    tier: str,
    redis_client: Any,
    session_id: str | None = None,
    *,
    now: datetime | None = None,
    record: bool = True,
) -> None:
    """Validate and optionally record the user's daily conversation count."""

    moment = now or datetime.now(tz=UTC)
    normalized_tier = _normalize_tier(tier)
    conversation_limit, _ = TIER_LIMITS.get(normalized_tier, TIER_LIMITS["free"])
    key = _counter_key(user_id, moment)
    current_count = int(await redis_client.zcount(key, "-inf", "+inf"))
    if conversation_limit is not None and current_count >= conversation_limit:
        raise LimitExceededError("Daily conversation limit exceeded")
    if record:
        await register_conversation(
            user_id=user_id,
            tier=normalized_tier,
            redis_client=redis_client,
            session_id=session_id,
            now=moment,
        )


def check_turn_limit(turn_count: int, tier: str) -> None:
    """Validate the remaining turns for an existing conversation."""

    normalized_tier = _normalize_tier(tier)
    _, turn_limit = TIER_LIMITS.get(normalized_tier, TIER_LIMITS["free"])
    if turn_limit is not None and turn_count >= turn_limit:
        raise LimitExceededError("Conversation turn limit exceeded")
