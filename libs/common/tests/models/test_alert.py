from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError

from estategap_common.models import AlertLog, AlertRule


def _aware_datetime() -> datetime:
    return datetime(2026, 4, 17, 8, 0, tzinfo=timezone.utc)


def _alert_rule_payload() -> dict[str, object]:
    return {
        "id": uuid4(),
        "user_id": uuid4(),
        "name": "Madrid 3BR under 500k",
        "filters": {"country": "ES", "city": "Madrid"},
        "active": True,
        "trigger_count": 0,
        "created_at": _aware_datetime(),
        "updated_at": _aware_datetime(),
    }


def test_alert_rule_valid_construction() -> None:
    rule = AlertRule(**_alert_rule_payload())

    assert rule.name == "Madrid 3BR under 500k"
    assert rule.channels == {"email": True}


def test_alert_rule_filters_accept_arbitrary_dict() -> None:
    rule = AlertRule(**_alert_rule_payload(), filters={"nested": {"deal_tier_max": 2}})

    assert rule.filters["nested"] == {"deal_tier_max": 2}


def test_alert_rule_rejects_naive_created_at() -> None:
    payload = _alert_rule_payload()
    payload["created_at"] = datetime(2026, 4, 17, 8, 0)

    with pytest.raises(ValidationError, match="timezone"):
        AlertRule(**payload)


def test_alert_log_status_rejects_invalid_value() -> None:
    with pytest.raises(ValidationError):
        AlertLog(
            id=uuid4(),
            rule_id=uuid4(),
            listing_id=uuid4(),
            country="ES",
            channel="email",
            status="queued",
            created_at=_aware_datetime(),
        )
