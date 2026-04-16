"""AlertRule Pydantic model."""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from .listing import ListingType


class AlertRule(BaseModel):
    id: str
    user_id: str
    country_code: str
    zone_ids: list[str]
    listing_types: list[ListingType]
    max_price_eur: Decimal | None = None
    min_area_sqm: float | None = None
    min_deal_score: float | None = None
    active: bool = True
    created_at: datetime
