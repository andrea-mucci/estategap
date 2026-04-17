"""Zone Pydantic model."""

from __future__ import annotations

from decimal import Decimal
from enum import IntEnum
from uuid import UUID

from pydantic import field_validator

from ._base import AwareDatetime, EstateGapModel, validate_country_code


class ZoneLevel(IntEnum):
    COUNTRY = 0
    REGION = 1
    PROVINCE = 2
    CITY = 3
    NEIGHBOURHOOD = 4


class Zone(EstateGapModel):
    id: UUID
    name: str
    name_local: str | None = None
    country_code: str
    level: ZoneLevel
    parent_id: UUID | None = None
    geometry_wkt: str | None = None
    bbox_wkt: str | None = None
    population: int | None = None
    area_km2: Decimal | None = None
    slug: str | None = None
    osm_id: int | None = None
    created_at: AwareDatetime | None = None
    updated_at: AwareDatetime | None = None

    @field_validator("country_code")
    @classmethod
    def _validate_country_code(cls, value: str) -> str:
        return validate_country_code(value)


__all__ = ["Zone", "ZoneLevel"]
