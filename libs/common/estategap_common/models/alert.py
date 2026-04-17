"""Alert models."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from ._base import AwareDatetime, EstateGapModel


class AlertRule(EstateGapModel):
    id: UUID
    user_id: UUID
    name: str
    filters: dict[str, Any] = Field(default_factory=dict)
    channels: dict[str, bool] = Field(default_factory=lambda: {"email": True})
    active: bool = True
    last_triggered_at: AwareDatetime | None = None
    trigger_count: int = 0
    created_at: AwareDatetime
    updated_at: AwareDatetime


class AlertLog(EstateGapModel):
    id: UUID
    rule_id: UUID
    listing_id: UUID
    country: str
    channel: str
    status: Literal["pending", "sent", "failed"] = "pending"
    error_message: str | None = None
    sent_at: AwareDatetime | None = None
    created_at: AwareDatetime


__all__ = ["AlertLog", "AlertRule"]
