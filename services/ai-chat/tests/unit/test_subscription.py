from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest

from estategap_ai_chat.subscription import (
    LimitExceededError,
    check_conversation_limit,
    check_turn_limit,
)


@pytest.mark.asyncio
async def test_free_tier_daily_limit(redis_client: Any) -> None:
    now = datetime(2026, 4, 17, 12, 0, tzinfo=UTC)
    for index in range(3):
        await check_conversation_limit(
            "user-free",
            "free",
            redis_client,
            session_id=f"conv-{index}",
            now=now,
        )

    with pytest.raises(LimitExceededError):
        await check_conversation_limit(
            "user-free",
            "free",
            redis_client,
            session_id="conv-4",
            now=now,
        )


def test_turn_limits_for_all_tiers() -> None:
    check_turn_limit(9, "free")
    with pytest.raises(LimitExceededError):
        check_turn_limit(10, "free")

    check_turn_limit(19, "basic")
    with pytest.raises(LimitExceededError):
        check_turn_limit(20, "basic")

    check_turn_limit(999, "pro_plus")
