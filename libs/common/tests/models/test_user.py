from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from estategap_common.models import Subscription, SubscriptionTier, User


def _aware_datetime() -> datetime:
    return datetime(2026, 4, 17, 8, 0, tzinfo=timezone.utc)


def _user_payload() -> dict[str, object]:
    return {
        "id": uuid4(),
        "email": "user@example.com",
        "password_hash": None,
        "oauth_provider": "google",
        "oauth_subject": "104824398127364892",
        "display_name": "Alice",
        "avatar_url": None,
        "subscription_tier": SubscriptionTier.PRO,
        "stripe_customer_id": "cus_abc123",
        "stripe_sub_id": "sub_xyz789",
        "subscription_ends_at": _aware_datetime(),
        "alert_limit": 50,
        "email_verified": True,
        "email_verified_at": _aware_datetime(),
        "last_login_at": _aware_datetime(),
        "deleted_at": None,
        "created_at": _aware_datetime(),
        "updated_at": _aware_datetime(),
    }


def test_user_valid_with_optional_fields() -> None:
    user = User(**_user_payload())

    assert user.subscription_tier is SubscriptionTier.PRO
    assert user.oauth_provider == "google"


def test_subscription_tier_serializes_as_lowercase_string() -> None:
    payload = json.loads(User(**_user_payload()).model_dump_json())

    assert payload["subscription_tier"] == "pro"


def test_subscription_construction() -> None:
    subscription = Subscription(
        user_id=uuid4(),
        tier=SubscriptionTier.GLOBAL,
        stripe_customer_id="cus_abc123",
        stripe_sub_id="sub_xyz789",
        starts_at=_aware_datetime(),
        ends_at=None,
        alert_limit=200,
    )

    assert subscription.tier is SubscriptionTier.GLOBAL
    assert subscription.ends_at is None


def test_user_rejects_naive_datetime() -> None:
    payload = _user_payload()
    payload["created_at"] = datetime(2026, 4, 17, 8, 0)

    with pytest.raises(ValidationError, match="timezone"):
        User(**payload)


def test_deleted_at_round_trips_as_null() -> None:
    payload = json.loads(User(**_user_payload()).model_dump_json())

    assert payload["deleted_at"] is None
