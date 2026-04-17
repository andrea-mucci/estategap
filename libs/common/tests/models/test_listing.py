from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from estategap_common.models import (
    DealTier,
    Listing,
    ListingStatus,
    NormalizedListing,
    PropertyCategory,
    RawListing,
)


def _aware_datetime() -> datetime:
    return datetime(2026, 4, 17, 8, 0, tzinfo=timezone.utc)


def _normalized_listing_payload() -> dict[str, object]:
    return {
        "id": uuid4(),
        "canonical_id": None,
        "country": "ES",
        "source": "idealista",
        "source_id": "listing-123",
        "source_url": "https://www.idealista.com/inmueble/listing-123/",
        "portal_id": None,
        "address": "Calle Mayor 1",
        "city": "Madrid",
        "region": "Comunidad de Madrid",
        "postal_code": "28013",
        "location_wkt": None,
        "zone_id": None,
        "asking_price": Decimal("450000"),
        "currency": "EUR",
        "asking_price_eur": Decimal("450000"),
        "price_per_m2_eur": Decimal("5625"),
        "property_category": PropertyCategory.RESIDENTIAL,
        "property_type": "apartment",
        "built_area_m2": Decimal("80"),
        "usable_area_m2": Decimal("75"),
        "plot_area_m2": None,
        "bedrooms": 3,
        "bathrooms": 2,
        "status": ListingStatus.ACTIVE,
        "first_seen_at": _aware_datetime(),
        "last_seen_at": _aware_datetime(),
        "published_at": _aware_datetime(),
        "raw_hash": "a" * 64,
    }


def test_normalized_listing_valid_construction() -> None:
    listing = NormalizedListing(**_normalized_listing_payload())

    assert listing.country == "ES"
    assert listing.currency == "EUR"
    assert listing.property_category is PropertyCategory.RESIDENTIAL


@pytest.mark.parametrize(
    ("field_name", "field_value", "message"),
    [
        ("asking_price", Decimal("0"), "asking_price must be greater than zero"),
        ("asking_price", Decimal("-1"), "asking_price must be greater than zero"),
        ("built_area_m2", Decimal("0"), "built_area_m2 must be greater than zero"),
        ("country", "XX", "Unsupported ISO 3166-1 alpha-2 code"),
        ("currency", "ZZZ", "Unsupported ISO 4217 alpha-3 code"),
        ("first_seen_at", datetime(2026, 4, 17, 8, 0), "timezone"),
    ],
)
def test_normalized_listing_validation_errors(
    field_name: str,
    field_value: object,
    message: str,
) -> None:
    payload = _normalized_listing_payload()
    payload[field_name] = field_value

    with pytest.raises(ValidationError, match=message):
        NormalizedListing(**payload)


def test_raw_listing_accepts_valid_iso_country_code() -> None:
    raw_listing = RawListing(
        external_id="raw-123",
        portal="idealista",
        country_code="PT",
        raw_json={"price": "100000", "misc": ["anything", {"goes": True}]},
        scraped_at=_aware_datetime(),
    )

    assert raw_listing.country_code == "PT"


def test_listing_accepts_deal_tier_enum_values() -> None:
    listing = Listing(
        **_normalized_listing_payload(),
        id=UUID("550e8400-e29b-41d4-a716-446655440000"),
        deal_tier=DealTier.GOOD_DEAL,
        created_at=_aware_datetime(),
        updated_at=_aware_datetime(),
    )

    assert listing.deal_tier is DealTier.GOOD_DEAL
