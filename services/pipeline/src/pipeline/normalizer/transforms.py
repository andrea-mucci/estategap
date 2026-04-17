"""Pure transform helpers used by the normalizer mapping layer."""

from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


_M2_PER_SQFT = Decimal("0.09290304")
_TWO_DP = Decimal("0.01")


def _quantize(value: Decimal) -> Decimal:
    return value.quantize(_TWO_DP, rounding=ROUND_HALF_UP)


def currency_convert(amount: Decimal, from_currency: str, rates: dict[str, Decimal]) -> Decimal:
    """Convert a listing amount into EUR using the latest cached exchange rates."""

    currency = from_currency.upper()
    if currency == "EUR":
        return _quantize(amount)
    try:
        rate = rates[currency]
    except KeyError as exc:
        raise ValueError(f"Missing exchange rate for currency {currency!r}") from exc
    return _quantize(amount * rate)


def area_to_m2(value: Decimal, unit: str) -> Decimal:
    """Convert an area measurement into square metres."""

    normalized = unit.lower()
    if normalized == "m2":
        return _quantize(value)
    if normalized in {"sqft", "ft2"}:
        return _quantize(value * _M2_PER_SQFT)
    raise ValueError(f"Unsupported area unit {unit!r}")


def map_property_type(portal_type: str, type_map: dict[str, str]) -> str:
    """Map a portal-specific property type to the canonical taxonomy."""

    candidates = (portal_type, portal_type.lower(), str(portal_type), str(portal_type).lower())
    for candidate in candidates:
        if candidate in type_map:
            return type_map[candidate]
    raise ValueError(f"Unsupported portal property type {portal_type!r}")


def map_condition(portal_condition: str, condition_map: dict[str, str]) -> str | None:
    """Map a portal-specific condition to the canonical condition value."""

    candidates = (
        portal_condition,
        portal_condition.lower(),
        str(portal_condition),
        str(portal_condition).lower(),
    )
    for candidate in candidates:
        if candidate in condition_map:
            return condition_map[candidate]
    return None


def pieces_to_bedrooms(pieces: int) -> int:
    """Convert French ``pieces`` counts into bedrooms by dropping the living room."""

    return max(0, pieces - 1)


__all__ = [
    "area_to_m2",
    "currency_convert",
    "map_condition",
    "map_property_type",
    "pieces_to_bedrooms",
]
