"""Database writer helpers for normalized and quarantined listings."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import asyncpg  # type: ignore[import-untyped]

from estategap_common.models import NormalizedListing, PropertyCategory


COMPLETENESS_FIELDS: list[str] = [
    "address",
    "city",
    "region",
    "postal_code",
    "location_wkt",
    "asking_price",
    "asking_price_eur",
    "price_per_m2_eur",
    "property_category",
    "property_type",
    "built_area_m2",
    "usable_area_m2",
    "plot_area_m2",
    "bedrooms",
    "bathrooms",
    "floor_number",
    "total_floors",
    "parking_spaces",
    "has_lift",
    "has_pool",
    "year_built",
    "condition",
    "energy_rating",
    "description_orig",
    "images_count",
    "published_at",
]

_UPSERT_SQL = """
INSERT INTO listings (
    id,
    canonical_id,
    country,
    source,
    source_id,
    source_url,
    address,
    city,
    region,
    postal_code,
    location,
    asking_price,
    currency,
    asking_price_eur,
    price_per_m2_eur,
    property_category,
    property_type,
    built_area,
    area_unit,
    built_area_m2,
    bedrooms,
    bathrooms,
    floor_number,
    total_floors,
    parking_spaces,
    has_lift,
    has_pool,
    year_built,
    condition,
    energy_rating,
    description_orig,
    images_count,
    first_seen_at,
    last_seen_at,
    published_at,
    raw_hash,
    data_completeness
) VALUES (
    $1,
    $2,
    $3,
    $4,
    $5,
    $6,
    $7,
    $8,
    $9,
    $10,
    CASE WHEN $11 IS NULL THEN NULL ELSE ST_GeomFromText($11, 4326) END,
    $12,
    $13,
    $14,
    $15,
    $16,
    $17,
    $18,
    $19,
    $20,
    $21,
    $22,
    $23,
    $24,
    $25,
    $26,
    $27,
    $28,
    $29,
    $30,
    $31,
    $32,
    $33,
    $34,
    $35,
    $36,
    $37
)
ON CONFLICT (source, source_id, country) DO UPDATE SET
    canonical_id = COALESCE(EXCLUDED.canonical_id, listings.canonical_id),
    source_url = EXCLUDED.source_url,
    address = EXCLUDED.address,
    city = EXCLUDED.city,
    region = EXCLUDED.region,
    postal_code = EXCLUDED.postal_code,
    location = EXCLUDED.location,
    asking_price = EXCLUDED.asking_price,
    currency = EXCLUDED.currency,
    asking_price_eur = EXCLUDED.asking_price_eur,
    price_per_m2_eur = EXCLUDED.price_per_m2_eur,
    property_category = EXCLUDED.property_category,
    property_type = EXCLUDED.property_type,
    built_area = EXCLUDED.built_area,
    area_unit = EXCLUDED.area_unit,
    built_area_m2 = EXCLUDED.built_area_m2,
    bedrooms = EXCLUDED.bedrooms,
    bathrooms = EXCLUDED.bathrooms,
    floor_number = EXCLUDED.floor_number,
    total_floors = EXCLUDED.total_floors,
    parking_spaces = EXCLUDED.parking_spaces,
    has_lift = EXCLUDED.has_lift,
    has_pool = EXCLUDED.has_pool,
    year_built = EXCLUDED.year_built,
    condition = EXCLUDED.condition,
    energy_rating = EXCLUDED.energy_rating,
    description_orig = EXCLUDED.description_orig,
    images_count = EXCLUDED.images_count,
    first_seen_at = LEAST(listings.first_seen_at, EXCLUDED.first_seen_at),
    last_seen_at = EXCLUDED.last_seen_at,
    published_at = EXCLUDED.published_at,
    raw_hash = EXCLUDED.raw_hash,
    data_completeness = EXCLUDED.data_completeness,
    updated_at = NOW()
"""


@dataclass(slots=True)
class QuarantineRecord:
    """Payload persisted when the normalizer rejects a listing."""

    source: str
    source_id: str | None
    country: str | None
    portal: str | None
    reason: str
    raw_payload: dict[str, Any]
    error_detail: str | None = None


class ListingWriter:
    """Persist normalized listings and quarantine events."""

    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool
        self._exchange_rates: dict[str, Decimal] | None = None
        self._exchange_rates_loaded_at: datetime | None = None

    async def load_exchange_rates(self) -> dict[str, Decimal]:
        """Return the latest exchange-rate snapshot, refreshed every five minutes."""

        now = datetime.now(UTC)
        if (
            self._exchange_rates is not None
            and self._exchange_rates_loaded_at is not None
            and now - self._exchange_rates_loaded_at < timedelta(minutes=5)
        ):
            return self._exchange_rates

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT DISTINCT ON (currency) currency, rate_to_eur
                FROM exchange_rates
                ORDER BY currency, date DESC
                """
            )
        rates = {str(row["currency"]).upper(): Decimal(str(row["rate_to_eur"])) for row in rows}
        rates.setdefault("EUR", Decimal("1"))
        self._exchange_rates = rates
        self._exchange_rates_loaded_at = now
        return rates

    async def upsert_batch(self, rows: list[NormalizedListing]) -> None:
        """Upsert a batch of normalized listings into the shared listings table."""

        if not rows:
            return
        payload = [self._listing_tuple(listing) for listing in rows]
        async with self._pool.acquire() as conn:
            await conn.executemany(_UPSERT_SQL, payload)

    async def write_quarantine(self, record: QuarantineRecord) -> None:
        """Persist one rejected listing immediately."""

        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO quarantine (
                    source,
                    source_id,
                    country,
                    portal,
                    reason,
                    error_detail,
                    raw_payload
                ) VALUES ($1, $2, $3, $4, $5, $6, $7)
                """,
                record.source,
                record.source_id,
                record.country,
                record.portal,
                record.reason,
                record.error_detail,
                record.raw_payload,
            )

    def _listing_tuple(self, listing: NormalizedListing) -> tuple[Any, ...]:
        completeness = compute_completeness(listing)
        listing.data_completeness = completeness
        if listing.price_per_m2_eur is None and listing.built_area_m2 > 0:
            listing.price_per_m2_eur = (
                (listing.asking_price_eur / listing.built_area_m2).quantize(Decimal("0.01"))
            )
        property_category = (
            listing.property_category.value
            if isinstance(listing.property_category, PropertyCategory)
            else listing.property_category
        )
        built_area = listing.built_area_m2
        area_unit = "m2"
        return (
            listing.id,
            listing.canonical_id,
            listing.country,
            listing.source,
            listing.source_id,
            listing.source_url,
            listing.address,
            listing.city,
            listing.region,
            listing.postal_code,
            listing.location_wkt,
            listing.asking_price,
            listing.currency,
            listing.asking_price_eur,
            listing.price_per_m2_eur,
            property_category,
            listing.property_type,
            built_area,
            area_unit,
            listing.built_area_m2,
            listing.bedrooms,
            listing.bathrooms,
            listing.floor_number,
            listing.total_floors,
            listing.parking_spaces,
            listing.has_lift,
            listing.has_pool,
            listing.year_built,
            listing.condition,
            listing.energy_rating,
            listing.description_orig,
            listing.images_count,
            listing.first_seen_at,
            listing.last_seen_at,
            listing.published_at,
            listing.raw_hash,
            completeness,
        )


def compute_completeness(listing: NormalizedListing) -> float:
    """Compute the listing completeness score from the fixed field list."""

    present = sum(1 for field in COMPLETENESS_FIELDS if getattr(listing, field, None) is not None)
    return round(present / len(COMPLETENESS_FIELDS), 4)


__all__ = ["COMPLETENESS_FIELDS", "ListingWriter", "QuarantineRecord", "compute_completeness"]
