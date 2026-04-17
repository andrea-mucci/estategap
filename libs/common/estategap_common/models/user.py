"""User-account Pydantic models."""

from __future__ import annotations

from enum import Enum
from uuid import UUID

from ._base import AwareDatetime, EstateGapModel


class SubscriptionTier(str, Enum):
    FREE = "free"
    BASIC = "basic"
    PRO = "pro"
    GLOBAL = "global"
    API = "api"


class Subscription(EstateGapModel):
    user_id: UUID
    tier: SubscriptionTier
    stripe_customer_id: str | None = None
    stripe_sub_id: str | None = None
    starts_at: AwareDatetime
    ends_at: AwareDatetime | None = None
    alert_limit: int


class User(EstateGapModel):
    id: UUID
    email: str
    password_hash: str | None = None
    oauth_provider: str | None = None
    oauth_subject: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    subscription_tier: SubscriptionTier = SubscriptionTier.FREE
    stripe_customer_id: str | None = None
    stripe_sub_id: str | None = None
    subscription_ends_at: AwareDatetime | None = None
    alert_limit: int = 3
    email_verified: bool = False
    email_verified_at: AwareDatetime | None = None
    last_login_at: AwareDatetime | None = None
    deleted_at: AwareDatetime | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime


__all__ = ["Subscription", "SubscriptionTier", "User"]
