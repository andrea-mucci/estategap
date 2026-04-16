"""Alert models."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import Field

from ._base import EstateGapModel


class AlertRule(EstateGapModel):
    id: UUID
    user_id: UUID
    name: str
    filters: dict[str, Any] = Field(default_factory=dict)
    channels: dict[str, Any] = Field(default_factory=lambda: {"email": True})
    active: bool = True
    last_triggered_at: datetime | None = None
    trigger_count: int = 0
    created_at: datetime
    updated_at: datetime


class AlertLog(EstateGapModel):
    id: UUID
    rule_id: UUID
    listing_id: UUID
    country: str
    channel: str
    status: str = "pending"
    error_message: str | None = None
    sent_at: datetime | None = None
    created_at: datetime
