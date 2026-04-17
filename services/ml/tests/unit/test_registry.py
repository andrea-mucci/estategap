from __future__ import annotations

import pytest

pytest.importorskip("asyncpg")
pytest.importorskip("boto3")
pytest.importorskip("pydantic_settings")

from estategap_ml.trainer.registry import next_version_tag


class _FakeConnection:
    def __init__(self, version_tag: str | None) -> None:
        self.version_tag = version_tag

    async def fetchrow(self, query: str, country_code: str, prefix: str):
        if self.version_tag is None:
            return None
        return {"version_tag": self.version_tag}


@pytest.mark.asyncio
async def test_next_version_tag_starts_at_one() -> None:
    conn = _FakeConnection(None)
    assert await next_version_tag("es", "national", conn) == "es_national_v1"


@pytest.mark.asyncio
async def test_next_version_tag_increments_existing_version() -> None:
    conn = _FakeConnection("es_national_v12")
    assert await next_version_tag("es", "national", conn) == "es_national_v13"


@pytest.mark.asyncio
async def test_next_version_tag_is_country_scoped() -> None:
    conn = _FakeConnection("pt_national_v8")
    assert await next_version_tag("pt", "national", conn) == "pt_national_v9"
