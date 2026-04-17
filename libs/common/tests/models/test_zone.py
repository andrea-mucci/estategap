from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from estategap_common.models import Zone, ZoneLevel


def _aware_datetime() -> datetime:
    return datetime(2026, 4, 17, 8, 0, tzinfo=timezone.utc)


def test_zone_valid_construction() -> None:
    zone = Zone(
        id=uuid4(),
        name="Madrid",
        country_code="ES",
        level=ZoneLevel.CITY,
        geometry_wkt=None,
        bbox_wkt=None,
        area_km2=Decimal("604.31"),
        created_at=_aware_datetime(),
        updated_at=_aware_datetime(),
    )

    assert zone.level is ZoneLevel.CITY
    assert zone.area_km2 == Decimal("604.31")


def test_zone_level_enum_values() -> None:
    assert ZoneLevel.COUNTRY == 0
    assert ZoneLevel.NEIGHBOURHOOD == 4


def test_zone_nullable_geometry_fields_accept_none() -> None:
    zone = Zone(
        id=uuid4(),
        name="Madrid",
        country_code="ES",
        level=ZoneLevel.CITY,
        geometry_wkt=None,
        bbox_wkt=None,
    )

    assert zone.geometry_wkt is None
    assert zone.bbox_wkt is None


def test_zone_country_code_allowlist_validation() -> None:
    with pytest.raises(ValidationError, match="Unsupported ISO 3166-1 alpha-2 code"):
        Zone(id=uuid4(), name="Madrid", country_code="XX", level=ZoneLevel.CITY)
