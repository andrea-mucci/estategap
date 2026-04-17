from __future__ import annotations

from uuid import uuid4

import pytest

pytest.importorskip("asyncpg")
pd = pytest.importorskip("pandas")

from estategap_ml.features.zone_stats import ZoneStats


@pytest.fixture
def sample_zone_id() -> object:
    return uuid4()


@pytest.fixture
def zone_stats_bundle(sample_zone_id: object) -> tuple[dict[object, ZoneStats], dict[str, ZoneStats], ZoneStats]:
    zone_stats = {
        sample_zone_id: ZoneStats(
            zone_id=sample_zone_id,
            median_price_m2=5000.0,
            listing_density=25,
            avg_income=42000.0,
        )
    }
    city_stats = {
        "madrid": ZoneStats(
            zone_id=None,
            median_price_m2=4200.0,
            listing_density=14,
            avg_income=39000.0,
        )
    }
    country_stats = ZoneStats(
        zone_id=None,
        median_price_m2=3100.0,
        listing_density=100,
        avg_income=33000.0,
    )
    return zone_stats, city_stats, country_stats


@pytest.fixture
def sample_training_frame(sample_zone_id: object) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "id": uuid4(),
                "country": "es",
                "city": "Madrid",
                "zone_id": sample_zone_id,
                "lat": 40.4168,
                "lon": -3.7038,
                "asking_price_eur": 350000.0,
                "final_price_eur": 340000.0,
                "price_per_m2_eur": 4375.0,
                "built_area_m2": 80.0,
                "usable_area_m2": 72.0,
                "bedrooms": 3,
                "bathrooms": 2,
                "floor_number": 6,
                "total_floors": 8,
                "has_lift": True,
                "parking_spaces": 1,
                "property_type": "apartment",
                "property_category": "residential",
                "energy_cert": "A",
                "condition": "new",
                "building_year": 2015,
                "community_fees_eur": 120.0,
                "photo_count": 12,
                "days_on_market": 45,
                "listed_at": "2025-06-15T00:00:00Z",
                "status": "sold",
                "dist_metro_m": 250.0,
                "dist_train_m": 600.0,
                "dist_beach_m": 10000.0,
            }
        ]
    )
