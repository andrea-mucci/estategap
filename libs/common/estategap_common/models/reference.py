"""Reference-data Pydantic models."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator

from ._base import (
    AwareDatetime,
    EstateGapModel,
    validate_country_code,
    validate_currency_code,
)


class Country(EstateGapModel):
    code: str
    name: str
    currency: str
    active: bool = True
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @field_validator("code")
    @classmethod
    def _validate_code(cls, value: str) -> str:
        return validate_country_code(value)

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, value: str) -> str:
        return validate_currency_code(value)


class Portal(EstateGapModel):
    id: UUID
    name: str
    country_code: str
    base_url: str
    spider_class: str
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)
    created_at: AwareDatetime
    updated_at: AwareDatetime

    @field_validator("country_code")
    @classmethod
    def _validate_country_code(cls, value: str) -> str:
        return validate_country_code(value)


class ExchangeRate(EstateGapModel):
    currency: str
    date: date
    rate_to_eur: Decimal
    fetched_at: AwareDatetime

    @field_validator("currency")
    @classmethod
    def _validate_currency(cls, value: str) -> str:
        return validate_currency_code(value)


__all__ = ["Country", "ExchangeRate", "Portal"]
