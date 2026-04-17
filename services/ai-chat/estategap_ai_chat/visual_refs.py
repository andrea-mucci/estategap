"""Visual reference lookup helpers."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel


class VisualReference(BaseModel):
    """Visual reference card returned to the client."""

    id: UUID
    image_url: str
    description: str | None = None


async def query_by_tags(tags: list[str], pool: Any) -> list[VisualReference]:
    """Query visual references by up to three normalized tags."""

    if pool is None:
        return []
    normalized_tags = [tag.strip().lower() for tag in tags if tag.strip()]
    unique_tags = list(dict.fromkeys(normalized_tags))[:3]
    if not unique_tags:
        return []
    try:
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, image_url, description
                FROM visual_references
                WHERE tags @> $1::text[]
                LIMIT 5
                """,
                unique_tags,
            )
    except Exception:  # noqa: BLE001
        return []
    return [
        VisualReference(
            id=row["id"],
            image_url=row["image_url"],
            description=row["description"],
        )
        for row in rows
    ]
