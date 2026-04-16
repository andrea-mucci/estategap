"""Reference-data Pydantic models."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field

from ._base import EstateGapModel


class Country(EstateGapModel):
    code: str
    name: str
    currency: str
    active: bool = True
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class Portal(EstateGapModel):
    id: UUID
    name: str
    country_code: str
    base_url: str
    spider_class: str
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime


class ExchangeRate(EstateGapModel):
    currency: str
    date: date
    rate_to_eur: Decimal
    fetched_at: datetime
