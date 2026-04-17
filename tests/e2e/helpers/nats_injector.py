from __future__ import annotations

from datetime import datetime, timezone
from nats.aio.client import Client as NATS
from pydantic import BaseModel, Field


class ScoredListingEvent(BaseModel):
    listing_id: str
    country_code: str
    lat: float = 0
    lon: float = 0
    property_type: str = "apartment"
    price_eur: float
    area_m2: float
    bedrooms: int | None = None
    features: list[str] = Field(default_factory=list)
    deal_score: float
    deal_tier: int
    estimated_price_eur: float
    model_version: str = "e2e-fixture"
    scored_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    title: str = "Fixture listing"
    city: str = "Madrid"
    image_url: str | None = None


async def publish_scored_listing(nats_url: str, event: ScoredListingEvent) -> None:
    nc = NATS()
    await nc.connect(servers=[nats_url])
    try:
        await nc.publish("scored.listings", event.model_dump_json().encode("utf-8"))
        await nc.flush()
    finally:
        await nc.drain()
