from __future__ import annotations

import os
from datetime import datetime, timezone

from aiokafka import AIOKafkaProducer
from pydantic import BaseModel, Field


DEFAULT_KAFKA_BROKERS = os.getenv("KAFKA_BROKERS", "localhost:9092")
DEFAULT_TOPIC_PREFIX = os.getenv("KAFKA_TOPIC_PREFIX", "estategap.")


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


def _normalize_topic_prefix(topic_prefix: str) -> str:
    trimmed = topic_prefix.strip() or "estategap."
    return trimmed if trimmed.endswith(".") else f"{trimmed}."


async def publish_scored_listing(
    bootstrap_servers: str | None,
    event: ScoredListingEvent,
    *,
    topic_prefix: str | None = None,
) -> None:
    producer = AIOKafkaProducer(
        bootstrap_servers=[
            broker.strip()
            for broker in (bootstrap_servers or DEFAULT_KAFKA_BROKERS).split(",")
            if broker.strip()
        ]
    )
    await producer.start()
    try:
        await producer.send_and_wait(
            f"{_normalize_topic_prefix(topic_prefix or DEFAULT_TOPIC_PREFIX)}scored-listings",
            event.model_dump_json().encode("utf-8"),
            key=event.country_code.encode("utf-8"),
        )
    finally:
        await producer.stop()
