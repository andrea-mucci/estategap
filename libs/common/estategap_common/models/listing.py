"""Listing and price-history Pydantic models."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID

from ._base import EstateGapModel
from .scoring import ShapValue


class ListingType(str, Enum):
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    LAND = "land"


class ListingStatus(str, Enum):
    ACTIVE = "active"
    SOLD = "sold"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"


class Listing(EstateGapModel):
    id: UUID
    canonical_id: UUID | None = None
    country: str
    source: str
    source_id: str
    source_url: str
    portal_id: UUID | None = None
    address: str | None = None
    neighborhood: str | None = None
    district: str | None = None
    city: str | None = None
    region: str | None = None
    postal_code: str | None = None
    location_wkt: str | None = None
    zone_id: UUID | None = None
    asking_price: Decimal | None = None
    currency: str = "EUR"
    asking_price_eur: Decimal | None = None
    price_per_m2_eur: Decimal | None = None
    property_category: ListingType | None = None
    property_type: str | None = None
    built_area: Decimal | None = None
    area_unit: str = "m2"
    built_area_m2: Decimal | None = None
    usable_area_m2: Decimal | None = None
    plot_area_m2: Decimal | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    toilets: int | None = None
    floor_number: int | None = None
    total_floors: int | None = None
    parking_spaces: int | None = None
    has_lift: bool | None = None
    has_pool: bool | None = None
    has_garden: bool | None = None
    terrace_area_m2: Decimal | None = None
    garage_area_m2: Decimal | None = None
    year_built: int | None = None
    last_renovated: int | None = None
    condition: str | None = None
    energy_rating: str | None = None
    energy_rating_kwh: Decimal | None = None
    co2_rating: str | None = None
    co2_kg_m2: Decimal | None = None
    frontage_m: Decimal | None = None
    ceiling_height_m: Decimal | None = None
    loading_docks: int | None = None
    power_kw: Decimal | None = None
    office_area_m2: Decimal | None = None
    warehouse_area_m2: Decimal | None = None
    buildability_index: Decimal | None = None
    urban_classification: str | None = None
    land_use: str | None = None
    estimated_price: Decimal | None = None
    deal_score: Decimal | None = None
    deal_tier: int | None = None
    confidence_low: Decimal | None = None
    confidence_high: Decimal | None = None
    shap_features: list[ShapValue] | None = None
    model_version: str | None = None
    scored_at: datetime | None = None
    days_on_market: int | None = None
    status: ListingStatus
    description_orig: str | None = None
    description_lang: str | None = None
    images_count: int = 0
    first_seen_at: datetime
    last_seen_at: datetime
    published_at: datetime | None = None
    delisted_at: datetime | None = None
    raw_hash: str | None = None
    created_at: datetime
    updated_at: datetime


class PriceChange(EstateGapModel):
    id: int
    listing_id: UUID
    country: str
    old_price: Decimal | None = None
    new_price: Decimal
    currency: str
    old_price_eur: Decimal | None = None
    new_price_eur: Decimal | None = None
    change_type: str = "price_change"
    old_status: ListingStatus | None = None
    new_status: ListingStatus | None = None
    recorded_at: datetime
    source: str | None = None


class RawListing(EstateGapModel):
    external_id: str
    portal: str
    country_code: str
    raw_json: str | dict[str, Any]
    scraped_at: datetime
