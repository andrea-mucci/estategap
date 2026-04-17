from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import uuid4

from estategap_common.models import AlertRule, DealTier, Listing, SubscriptionTier, User, Zone, ZoneLevel


class ListingFactory:
    @classmethod
    def build(cls, **overrides: object) -> Listing:
        now = datetime.now(UTC)
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
            "asking_price": Decimal("450000"),
            "currency": "EUR",
            "asking_price_eur": Decimal("450000"),
            "price_per_m2_eur": Decimal("5625"),
            "property_category": "residential",
            "property_type": "apartment",
            "built_area_m2": Decimal("80"),
            "bedrooms": 3,
            "bathrooms": 2,
            "status": "active",
            "deal_score": Decimal("91"),
            "deal_tier": DealTier.GREAT_DEAL,
            "first_seen_at": now,
            "last_seen_at": now,
            "created_at": now,
            "updated_at": now,
            "images_count": 5,
        }
        payload.update(overrides)
        return Listing.model_validate(payload)


class ZoneFactory:
    @classmethod
    def build(cls, **overrides: object) -> Zone:
        now = datetime.now(UTC)
        payload: dict[str, object] = {
            "id": uuid4(),
            "name": "Salamanca",
            "name_local": "Salamanca",
            "country_code": "ES",
            "level": ZoneLevel.NEIGHBOURHOOD,
            "population": 150000,
            "area_km2": Decimal("5.2"),
            "slug": "madrid-salamanca",
            "created_at": now,
            "updated_at": now,
        }
        payload.update(overrides)
        return Zone.model_validate(payload)


class UserFactory:
    @classmethod
    def build(cls, **overrides: object) -> User:
        now = datetime.now(UTC)
        payload: dict[str, object] = {
            "id": uuid4(),
            "email": "analyst@estategap.com",
            "display_name": "Alex Analyst",
            "subscription_tier": SubscriptionTier.PRO,
            "alert_limit": 25,
            "email_verified": True,
            "email_verified_at": now,
            "created_at": now,
            "updated_at": now,
        }
        payload.update(overrides)
        return User.model_validate(payload)


class AlertRuleFactory:
    @classmethod
    def build(cls, **overrides: object) -> AlertRule:
        now = datetime.now(UTC)
        payload: dict[str, object] = {
            "id": uuid4(),
            "user_id": uuid4(),
            "name": "Madrid apartments under 500k",
            "filters": {"price_eur": {"lte": 500000}, "bedrooms": {"gte": 2}},
            "channels": {"email": True},
            "active": True,
            "trigger_count": 0,
            "last_triggered_at": now - timedelta(days=1),
            "created_at": now,
            "updated_at": now,
        }
        payload.update(overrides)
        return AlertRule.model_validate(payload)


__all__ = [
    "AlertRuleFactory",
    "ListingFactory",
    "UserFactory",
    "ZoneFactory",
]
