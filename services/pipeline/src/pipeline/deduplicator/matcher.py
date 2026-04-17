"""Database-backed candidate lookup and canonical-id resolution."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Iterable
from uuid import UUID

import asyncpg  # type: ignore[import-untyped]
from rapidfuzz import fuzz  # type: ignore[import-untyped]

from estategap_common.models import NormalizedListing

from .address import normalize_address


@dataclass(slots=True, frozen=True)
class CandidateRow:
    """Deduplication candidate loaded from the listings table."""

    id: UUID
    address: str | None
    built_area_m2: Decimal | None
    bedrooms: int | None
    property_type: str | None
    canonical_id: UUID | None
    created_at: datetime
    country: str


async def find_proximity_candidates(
    pool: asyncpg.Pool,
    lon: float,
    lat: float,
    country: str,
    exclude_id: UUID,
    proximity_meters: int = 50,
) -> list[CandidateRow]:
    """Find candidate duplicates within the configured spatial radius."""

    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, address, built_area_m2, bedrooms, property_type, canonical_id, created_at, country
            FROM listings
            WHERE ST_DWithin(
                location::geography,
                ST_SetSRID(ST_Point($1, $2), 4326)::geography,
                $3
            )
              AND country = $4
              AND id != $5
            """,
            lon,
            lat,
            proximity_meters,
            country,
            exclude_id,
        )
    return [
        CandidateRow(
            id=row["id"],
            address=row["address"],
            built_area_m2=row["built_area_m2"],
            bedrooms=row["bedrooms"],
            property_type=row["property_type"],
            canonical_id=row["canonical_id"],
            created_at=row["created_at"],
            country=row["country"],
        )
        for row in rows
    ]


def filter_by_features(candidate: CandidateRow, listing: NormalizedListing, area_tolerance: float) -> bool:
    """Reject candidates that are too different on core structural features."""

    if candidate.built_area_m2 is None or candidate.bedrooms is None or candidate.property_type is None:
        return False
    if listing.bedrooms is None or listing.property_type is None or listing.built_area_m2 <= 0:
        return False
    area_difference = abs(candidate.built_area_m2 - listing.built_area_m2) / listing.built_area_m2
    return (
        area_difference < Decimal(str(area_tolerance))
        and candidate.bedrooms == listing.bedrooms
        and candidate.property_type == listing.property_type
    )


def is_address_match(addr_a: str, addr_b: str, threshold: int) -> bool:
    """Return ``True`` when two normalized addresses are similar enough to merge."""

    if not addr_a or not addr_b:
        return False
    return fuzz.ratio(normalize_address(addr_a), normalize_address(addr_b)) > threshold


async def resolve_canonical_id(
    pool: asyncpg.Pool,
    listing_id: UUID,
    candidates: list[CandidateRow],
    country: str | None = None,
) -> UUID:
    """Assign or merge a canonical-id group for a listing."""

    canonical_id = listing_id
    if candidates:
        earliest = min(candidates, key=lambda candidate: candidate.created_at)
        canonical_id = earliest.canonical_id or earliest.id

    async with pool.acquire() as conn:
        async with conn.transaction():
            if country is None:
                country = await conn.fetchval("SELECT country FROM listings WHERE id = $1", listing_id)
            if country is None:
                raise ValueError(f"Listing {listing_id} does not exist")

            await conn.execute(
                """
                UPDATE listings
                SET canonical_id = $1, updated_at = NOW()
                WHERE id = $2 AND country = $3
                """,
                canonical_id,
                listing_id,
                country,
            )

            if candidates:
                merge_ids = list(_canonical_merge_ids(candidates))
                await conn.execute(
                    """
                    UPDATE listings
                    SET canonical_id = $1, updated_at = NOW()
                    WHERE country = $2
                      AND (
                        id = ANY($3::uuid[])
                        OR canonical_id = ANY($3::uuid[])
                        OR id = $1
                        OR canonical_id = $1
                      )
                    """,
                    canonical_id,
                    country,
                    merge_ids,
                )

    return canonical_id


def _canonical_merge_ids(candidates: Iterable[CandidateRow]) -> set[UUID]:
    ids: set[UUID] = set()
    for candidate in candidates:
        ids.add(candidate.id)
        if candidate.canonical_id is not None:
            ids.add(candidate.canonical_id)
    return ids


__all__ = [
    "CandidateRow",
    "filter_by_features",
    "find_proximity_candidates",
    "is_address_match",
    "resolve_canonical_id",
]
