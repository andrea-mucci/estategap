"""Listing and price-history Pydantic models."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, field_validator

from ._base import AwareDatetime, EstateGapModel, validate_country_code, validate_currency_code
from .scoring import DealTier, ShapValue

EnrichmentState = Literal["pending", "completed", "partial", "no_match", "failed"]


class PropertyCategory(str, Enum):
    """Supported listing category values shared across services."""

    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    LAND = "land"


class ListingStatus(str, Enum):
    """Persisted listing lifecycle states."""

    ACTIVE = "active"
    DELISTED = "delisted"
    SOLD = "sold"


class RawListing(EstateGapModel):
    """Raw listing payload emitted by a scraper before normalization."""

    external_id: str
    portal: str
    country_code: str
    raw_json: dict[str, Any]
    scraped_at: AwareDatetime

    @field_validator("country_code")
    @classmethod
    def _validate_country_code(cls, value: str) -> str:
        return validate_country_code(value)


class NormalizedListing(EstateGapModel):
    """Validated listing data ready for database insertion."""

    id: UUID
    canonical_id: UUID | None = None
    country: str
    source: str
    source_id: str
    source_url: str
    portal_id: UUID | None = None
    address: str | None = None
    city: str | None = None
    region: str | None = None
    postal_code: str | None = None
    location_wkt: str | None = None
    zone_id: UUID | None = None
    asking_price: Decimal
    currency: str
    asking_price_eur: Decimal
    price_per_m2_eur: Decimal | None = None
    property_category: PropertyCategory | None = None
    property_type: str | None = None
    built_area_sqft: Decimal | None = None
    built_area_m2: Decimal
    usable_area_m2: Decimal | None = None
    plot_area_m2: Decimal | None = None
    lot_size_sqft: Decimal | None = None
    lot_size_m2: Decimal | None = None
    bedrooms: int | None = None
    bathrooms: int | None = None
    floor_number: int | None = None
    total_floors: int | None = None
    parking_spaces: int | None = None
    has_lift: bool | None = None
    has_pool: bool | None = None
    year_built: int | None = None
    council_tax_band: str | None = None
    epc_rating: str | None = None
    tenure: str | None = None
    leasehold_years_remaining: int | None = None
    seller_type: str | None = None
    omi_zone_code: str | None = None
    omi_price_min_eur_m2: Decimal | None = None
    omi_price_max_eur_m2: Decimal | None = None
    omi_period: str | None = None
    price_vs_omi: Decimal | None = None
    bag_id: str | None = None
    official_area_m2: Decimal | None = None
    dvf_nearby_count: int | None = None
    dvf_median_price_m2: Decimal | None = None
    uk_lr_match_count: int | None = None
    uk_lr_last_price_gbp: int | None = None
    uk_lr_last_date: date | None = None
    cadastral_ref: str | None = None
    official_built_area_m2: Decimal | None = None
    area_discrepancy_flag: bool | None = None
    building_geometry_wkt: str | None = None
    enrichment_status: EnrichmentState | None = None
    enrichment_attempted_at: AwareDatetime | None = None
    dist_metro_m: int | None = None
    dist_train_m: int | None = None
    dist_airport_m: int | None = None
    dist_park_m: int | None = None
    dist_beach_m: int | None = None
    hoa_fees_monthly_usd: int | None = None
    tax_assessed_value_usd: int | None = None
    school_rating: Decimal | None = None
    zestimate_reference_usd: int | None = None
    compete_score: int | None = None
    mls_id: str | None = None
    condition: str | None = None
    energy_rating: str | None = None
    status: ListingStatus = ListingStatus.ACTIVE
    description_orig: str | None = None
    images_count: int = 0
    data_completeness: float | None = None
    first_seen_at: AwareDatetime
    last_seen_at: AwareDatetime
    published_at: AwareDatetime | None = None
    raw_hash: str | None = None

    @field_validator("country")
    @classmethod
    def _validate_country(cls, value: str) -> str:
        return validate_country_code(value)

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, value: str) -> str:
        return validate_currency_code(value)

    @field_validator("asking_price", "built_area_m2")
    @classmethod
    def _validate_positive_decimals(cls, value: Decimal, info: Any) -> Decimal:
        if value <= 0:
            raise ValueError(f"{info.field_name} must be greater than zero")
        return value


class Listing(NormalizedListing):
    """Full persisted listing record shared by the API, pipeline, and ML layers."""

    neighborhood: str | None = None
    district: str | None = None
    toilets: int | None = None
    has_garden: bool | None = None
    terrace_area_m2: Decimal | None = None
    garage_area_m2: Decimal | None = None
    last_renovated: int | None = None
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
    deal_tier: DealTier | None = None
    confidence_low: Decimal | None = None
    confidence_high: Decimal | None = None
    shap_features: list[ShapValue] | None = None
    comparable_ids: list[UUID] | None = None
    model_version: str | None = None
    scored_at: AwareDatetime | None = None
    days_on_market: int | None = None
    description_lang: str | None = None
    delisted_at: AwareDatetime | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class PriceHistory(EstateGapModel):
    """A single listing price-change event."""

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
    recorded_at: AwareDatetime
    source: str | None = None

    @field_validator("country")
    @classmethod
    def _validate_country(cls, value: str) -> str:
        return validate_country_code(value)

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, value: str) -> str:
        return validate_currency_code(value)


PriceChange = PriceHistory


class PriceChangeEvent(EstateGapModel):
    """Price-drop event emitted for downstream consumers."""

    listing_id: UUID
    country: str
    portal: str
    old_price: Decimal
    new_price: Decimal
    currency: str
    old_price_eur: Decimal | None = None
    new_price_eur: Decimal | None = None
    drop_percentage: Decimal
    recorded_at: AwareDatetime

    @field_validator("country")
    @classmethod
    def _validate_country(cls, value: str) -> str:
        return validate_country_code(value)

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, value: str) -> str:
        return validate_currency_code(value)


class ScrapeCycleEvent(EstateGapModel):
    """Cycle-completion event emitted by the scrape orchestrator."""

    cycle_id: str
    portal: str
    country: str
    completed_at: AwareDatetime
    listing_ids: list[str] = Field(default_factory=list)

    @field_validator("country")
    @classmethod
    def _validate_country(cls, value: str) -> str:
        return validate_country_code(value)


__all__ = [
    "EnrichmentState",
    "Listing",
    "ListingStatus",
    "NormalizedListing",
    "PriceChange",
    "PriceChangeEvent",
    "PriceHistory",
    "PropertyCategory",
    "RawListing",
    "ScrapeCycleEvent",
]
