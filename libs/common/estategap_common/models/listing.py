"""Listing and RawListing Pydantic models."""

from datetime import datetime
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel


class ListingType(str, Enum):
    RESIDENTIAL = "RESIDENTIAL"
    COMMERCIAL = "COMMERCIAL"
    INDUSTRIAL = "INDUSTRIAL"
    LAND = "LAND"


class ListingStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SOLD = "SOLD"
    WITHDRAWN = "WITHDRAWN"
    EXPIRED = "EXPIRED"


class Listing(BaseModel):
    id: str
    external_id: str
    portal: str
    country_code: str
    listing_type: ListingType
    status: ListingStatus
    price: Decimal
    currency_code: str
    price_eur: Decimal
    area_sqm: float
    latitude: float
    longitude: float
    zone_id: str | None = None
    created_at: datetime
    updated_at: datetime


class RawListing(BaseModel):
    external_id: str
    portal: str
    country_code: str
    raw_json: str
    scraped_at: datetime
