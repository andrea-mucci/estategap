"""User-account Pydantic models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from ._base import EstateGapModel


class SubscriptionTier(str, Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


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
    subscription_ends_at: datetime | None = None
    alert_limit: int = 3
    email_verified: bool = False
    email_verified_at: datetime | None = None
    last_login_at: datetime | None = None
    deleted_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
