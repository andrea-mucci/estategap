from __future__ import annotations

from typing import Any
from uuid import uuid4

import pytest

from estategap_ai_chat.visual_refs import query_by_tags


@pytest.mark.asyncio
async def test_query_by_tags_returns_matches_and_handles_empty_results(db_pool: Any) -> None:
    if db_pool is None:
        pytest.skip("PostgreSQL test dependencies are not available")

    async with db_pool.acquire() as conn:
        await conn.execute("TRUNCATE TABLE visual_references")
        await conn.executemany(
            """
            INSERT INTO visual_references (id, image_url, tags, description)
            VALUES ($1, $2, $3::text[], $4)
            """,
            [
                (uuid4(), "https://example.com/modern-1.jpg", ["modern", "loft"], "Modern loft"),
                (uuid4(), "https://example.com/modern-2.jpg", ["modern", "minimal"], "Modern minimal"),
                (uuid4(), "https://example.com/rustic.jpg", ["rustic"], "Rustic home"),
            ],
        )

    matches = await query_by_tags(["modern"], db_pool)
    missing = await query_by_tags(["nonexistent"], db_pool)

    assert 1 <= len(matches) <= 5
    assert all("https://example.com/" in item.image_url for item in matches)
    assert missing == []
