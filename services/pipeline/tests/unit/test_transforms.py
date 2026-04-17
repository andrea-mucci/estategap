from __future__ import annotations

from decimal import Decimal

import pytest

from pipeline.normalizer.transforms import (
    area_to_m2,
    currency_convert,
    map_condition,
    map_property_type,
    pieces_to_bedrooms,
)


def test_currency_convert_uses_latest_rate() -> None:
    assert currency_convert(Decimal("100"), "GBP", {"GBP": Decimal("1.17")}) == Decimal("117.00")


def test_currency_convert_rejects_missing_rate() -> None:
    with pytest.raises(ValueError, match="Missing exchange rate"):
        currency_convert(Decimal("100"), "CHF", {})


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        (Decimal("80"), "m2", Decimal("80.00")),
        (Decimal("100"), "sqft", Decimal("9.29")),
        (Decimal("100"), "ft2", Decimal("9.29")),
        (Decimal("0"), "m2", Decimal("0.00")),
    ],
)
def test_area_to_m2(value: Decimal, unit: str, expected: Decimal) -> None:
    assert area_to_m2(value, unit) == expected


def test_area_to_m2_rejects_unknown_units() -> None:
    with pytest.raises(ValueError, match="Unsupported area unit"):
        area_to_m2(Decimal("10"), "acre")


def test_map_property_type_uses_mapping_table() -> None:
    type_map = {"piso": "residential", "1": "residential"}
    assert map_property_type("piso", type_map) == "residential"
    assert map_property_type("1", type_map) == "residential"


def test_map_property_type_requires_known_values() -> None:
    with pytest.raises(ValueError, match="Unsupported portal property type"):
        map_property_type("castle", {})


def test_map_condition_returns_none_for_unknown_values() -> None:
    condition_map = {"good": "good", "new": "new"}
    assert map_condition("good", condition_map) == "good"
    assert map_condition("missing", condition_map) is None


@pytest.mark.parametrize(
    ("pieces", "expected"),
    [
        (1, 0),
        (4, 3),
        (0, 0),
    ],
)
def test_pieces_to_bedrooms(pieces: int, expected: int) -> None:
    assert pieces_to_bedrooms(pieces) == expected
