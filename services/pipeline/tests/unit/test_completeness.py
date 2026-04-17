from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from uuid import uuid4

import pytest

from estategap_common.models import ListingStatus, NormalizedListing, PropertyCategory

from pipeline.normalizer.writer import compute_completeness


def _dt() -> datetime:
    return datetime(2026, 4, 17, 12, 0, tzinfo=UTC)


def _listing(**overrides: object) -> NormalizedListing:
    payload: dict[str, object] = {
        "id": uuid4(),
        "canonical_id": None,
        "country": "ES",
        "source": "idealista",
        "source_id": "listing-123",
        "source_url": "https://www.idealista.com/inmueble/listing-123/",
        "address": "Calle Mayor 1",
        "city": "Madrid",
        "region": "Madrid",
        "postal_code": "28013",
        "location_wkt": "POINT(-3.7038 40.4168)",
        "asking_price": Decimal("450000"),
        "currency": "EUR",
        "asking_price_eur": Decimal("450000"),
        "price_per_m2_eur": Decimal("5625"),
        "property_category": PropertyCategory.RESIDENTIAL,
        "property_type": "residential",
        "built_area_m2": Decimal("80"),
        "usable_area_m2": Decimal("75"),
        "plot_area_m2": Decimal("0.01"),
        "bedrooms": 3,
        "bathrooms": 2,
        "floor_number": 2,
        "total_floors": 4,
        "parking_spaces": 1,
        "has_lift": True,
        "has_pool": False,
        "year_built": 2005,
        "condition": "good",
        "energy_rating": "A",
        "status": ListingStatus.ACTIVE,
        "description_orig": "Sunny apartment in Madrid",
        "images_count": 12,
        "first_seen_at": _dt(),
        "last_seen_at": _dt(),
        "published_at": _dt(),
    }
    payload.update(overrides)
    return NormalizedListing.model_validate(payload)


def test_compute_completeness_for_fully_populated_listing() -> None:
    listing = _listing()

    assert compute_completeness(listing) == 1.0


def test_compute_completeness_for_minimal_listing() -> None:
    listing = _listing(
        address=None,
        region=None,
        postal_code=None,
        price_per_m2_eur=None,
        property_category=None,
        property_type=None,
        usable_area_m2=None,
        plot_area_m2=None,
        bedrooms=None,
        bathrooms=None,
        floor_number=None,
        total_floors=None,
        parking_spaces=None,
        has_lift=None,
        has_pool=None,
        year_built=None,
        condition=None,
        energy_rating=None,
        description_orig=None,
        published_at=None,
    )

    assert compute_completeness(listing) < 0.5


def test_compute_completeness_moves_by_one_field() -> None:
    base = _listing(description_orig=None)
    enriched = _listing()

    assert compute_completeness(enriched) - compute_completeness(base) == pytest.approx(1 / 26, abs=1e-4)
