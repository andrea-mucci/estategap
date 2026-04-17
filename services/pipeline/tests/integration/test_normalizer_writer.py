from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from pipeline.normalizer.writer import ListingWriter


@pytest.mark.asyncio
async def test_listing_writer_upserts_rows(asyncpg_pool, normalized_listing_factory) -> None:
    writer = ListingWriter(asyncpg_pool)
    listing = normalized_listing_factory()

    await writer.upsert_batch([listing])

    row = await asyncpg_pool.fetchrow(
        """
        SELECT source, source_id, country, city, asking_price, asking_price_eur, built_area_m2, data_completeness
        FROM listings
        WHERE source = $1 AND source_id = $2 AND country = $3
        """,
        listing.source,
        listing.source_id,
        listing.country,
    )
    assert row is not None
    assert row["source"] == "idealista"
    assert row["city"] == "Madrid"
    assert row["asking_price"] == Decimal("450000.00")
    assert row["asking_price_eur"] == Decimal("450000.00")
    assert row["built_area_m2"] == Decimal("80.00")
    assert float(row["data_completeness"]) == pytest.approx(listing.data_completeness or 0.0, abs=0.01)

    updated = listing.model_copy(
        update={
            "asking_price": Decimal("460000"),
            "asking_price_eur": Decimal("460000"),
            "city": "Barcelona",
            "last_seen_at": datetime(2026, 4, 18, 12, 0, tzinfo=UTC),
        }
    )
    await writer.upsert_batch([updated])

    count = await asyncpg_pool.fetchval(
        "SELECT COUNT(*) FROM listings WHERE source = $1 AND source_id = $2 AND country = $3",
        listing.source,
        listing.source_id,
        listing.country,
    )
    row = await asyncpg_pool.fetchrow(
        "SELECT city, asking_price, last_seen_at FROM listings WHERE source = $1 AND source_id = $2 AND country = $3",
        listing.source,
        listing.source_id,
        listing.country,
    )
    assert count == 1
    assert row is not None
    assert row["city"] == "Barcelona"
    assert row["asking_price"] == Decimal("460000.00")
    assert row["last_seen_at"] == datetime(2026, 4, 18, 12, 0, tzinfo=UTC)
