from __future__ import annotations

import pytest

from pipeline.deduplicator.config import DeduplicatorSettings
from pipeline.deduplicator.consumer import DeduplicatorService
from pipeline.deduplicator.matcher import (
    filter_by_features,
    find_proximity_candidates,
    is_address_match,
    resolve_canonical_id,
)
from pipeline.normalizer.writer import ListingWriter


class FakeJetStream:
    def __init__(self) -> None:
        self.published: list[tuple[str, bytes]] = []

    async def publish(self, subject: str, payload: bytes) -> None:
        self.published.append((subject, payload))


class FakeMessage:
    def __init__(self, payload: bytes) -> None:
        self.data = payload
        self.headers: dict[str, str] = {}
        self.acked = False
        self.nacked = False

    async def ack(self) -> None:
        self.acked = True

    async def nak(self) -> None:
        self.nacked = True


@pytest.fixture
def deduplicator_settings(database_url: str) -> DeduplicatorSettings:
    return DeduplicatorSettings.model_construct(
        database_url=database_url,
        nats_url="nats://unused:4222",
        proximity_meters=50,
        area_tolerance=0.10,
        address_threshold=85,
        metrics_port=9102,
        log_level="INFO",
    )


@pytest.mark.asyncio
async def test_deduplicator_matches_same_property(asyncpg_pool, normalized_listing_factory) -> None:
    writer = ListingWriter(asyncpg_pool)
    first = normalized_listing_factory(
        source="idealista",
        source_id="idealista-1",
        address="Calle Mayor 5",
        location_wkt="POINT(-3.70380 40.41680)",
    )
    second = normalized_listing_factory(
        source="fotocasa",
        source_id="fotocasa-2",
        address="Mayor 5",
        location_wkt="POINT(-3.70379 40.41681)",
    )
    await writer.upsert_batch([first, second])
    await resolve_canonical_id(asyncpg_pool, first.id, [], country="ES")

    candidates = await find_proximity_candidates(asyncpg_pool, -3.70379, 40.41681, "ES", second.id)
    matched = [
        candidate
        for candidate in candidates
        if filter_by_features(candidate, second, 0.10) and is_address_match(candidate.address or "", second.address or "", 85)
    ]
    canonical_id = await resolve_canonical_id(asyncpg_pool, second.id, matched, country="ES")

    first_row = await asyncpg_pool.fetchrow("SELECT canonical_id FROM listings WHERE id = $1 AND country = 'ES'", first.id)
    second_row = await asyncpg_pool.fetchrow("SELECT canonical_id FROM listings WHERE id = $1 AND country = 'ES'", second.id)

    assert canonical_id == first.id
    assert first_row is not None and first_row["canonical_id"] == first.id
    assert second_row is not None and second_row["canonical_id"] == first.id


@pytest.mark.asyncio
async def test_deduplicator_keeps_distinct_properties_separate(asyncpg_pool, normalized_listing_factory) -> None:
    writer = ListingWriter(asyncpg_pool)
    first = normalized_listing_factory(source_id="idealista-1", bedrooms=3)
    second = normalized_listing_factory(source="fotocasa", source_id="fotocasa-2", bedrooms=4)
    await writer.upsert_batch([first, second])
    await resolve_canonical_id(asyncpg_pool, first.id, [], country="ES")

    candidates = await find_proximity_candidates(asyncpg_pool, -3.7038, 40.4168, "ES", second.id)
    matched = [
        candidate
        for candidate in candidates
        if filter_by_features(candidate, second, 0.10) and is_address_match(candidate.address or "", second.address or "", 85)
    ]
    canonical_id = await resolve_canonical_id(asyncpg_pool, second.id, matched, country="ES")

    assert matched == []
    assert canonical_id == second.id


@pytest.mark.asyncio
async def test_deduplicator_merges_three_listings_into_earliest_group(asyncpg_pool, normalized_listing_factory) -> None:
    writer = ListingWriter(asyncpg_pool)
    first = normalized_listing_factory(source_id="idealista-1")
    second = normalized_listing_factory(source="fotocasa", source_id="fotocasa-2")
    third = normalized_listing_factory(source="idealista", source_id="idealista-3", address="Calle Mayor 5")
    await writer.upsert_batch([first, second, third])
    await resolve_canonical_id(asyncpg_pool, first.id, [], country="ES")

    second_candidates = await find_proximity_candidates(asyncpg_pool, -3.7038, 40.4168, "ES", second.id)
    second_matched = [
        candidate
        for candidate in second_candidates
        if filter_by_features(candidate, second, 0.10) and is_address_match(candidate.address or "", second.address or "", 85)
    ]
    await resolve_canonical_id(asyncpg_pool, second.id, second_matched, country="ES")

    third_candidates = await find_proximity_candidates(asyncpg_pool, -3.7038, 40.4168, "ES", third.id)
    third_matched = [
        candidate
        for candidate in third_candidates
        if filter_by_features(candidate, third, 0.10) and is_address_match(candidate.address or "", third.address or "", 85)
    ]
    canonical_id = await resolve_canonical_id(asyncpg_pool, third.id, third_matched, country="ES")

    rows = await asyncpg_pool.fetch(
        """
        SELECT canonical_id
        FROM listings
        WHERE id = ANY($1::uuid[]) AND country = 'ES'
        """,
        [first.id, second.id, third.id],
    )

    assert canonical_id == first.id
    assert {row["canonical_id"] for row in rows} == {first.id}


@pytest.mark.asyncio
async def test_deduplicator_skips_postgis_when_location_missing(
    asyncpg_pool,
    deduplicator_settings: DeduplicatorSettings,
    normalized_listing_factory,
) -> None:
    writer = ListingWriter(asyncpg_pool)
    listing = normalized_listing_factory(source_id="no-gps", location_wkt=None, address="Unknown address")
    await writer.upsert_batch([listing])

    service = DeduplicatorService(deduplicator_settings, asyncpg_pool, FakeJetStream())
    message = FakeMessage(listing.model_dump_json().encode())

    await service.handle_message(message)

    canonical_id = await asyncpg_pool.fetchval(
        "SELECT canonical_id FROM listings WHERE id = $1 AND country = 'ES'",
        listing.id,
    )

    assert message.acked is True
    assert message.nacked is False
    assert canonical_id == listing.id
