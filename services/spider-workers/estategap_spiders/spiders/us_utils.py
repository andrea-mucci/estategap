"""Shared helpers for US portal spiders."""

from __future__ import annotations

import re
from collections.abc import Iterable
from typing import Any


SQFT_TO_M2 = 0.092903
_NUMBER_RE = re.compile(r"-?\d+(?:\.\d+)?")


def _parse_number(raw: Any) -> float | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return float(raw)
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, str):
        match = _NUMBER_RE.search(raw.replace(",", ""))
        if match is None:
            return None
        return float(match.group())
    return None


def _parse_currency_cents(raw: Any) -> int | None:
    if raw is None:
        return None
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, int):
        return raw if abs(raw) >= 1_000 else raw * 100
    if isinstance(raw, float):
        return int(round(raw * 100))
    if isinstance(raw, str):
        cleaned = (
            raw.replace("$", "")
            .replace("USD", "")
            .replace("usd", "")
            .replace("/mo", "")
            .replace("/month", "")
            .replace("per month", "")
            .replace(",", "")
            .strip()
        )
        match = _NUMBER_RE.search(cleaned)
        if match is None:
            return None
        return int(round(float(match.group()) * 100))
    return None


def sqft_to_m2(sqft: Any) -> float | None:
    """Convert square feet into square metres."""

    value = _parse_number(sqft)
    if value is None:
        return None
    return round(value * SQFT_TO_M2, 2)


def extract_school_rating(raw: Any) -> float | None:
    """Normalise school ratings into a 0–10 float."""

    if raw is None:
        return None
    if isinstance(raw, Iterable) and not isinstance(raw, (str, bytes, dict)):
        ratings = [extract_school_rating(item) for item in raw]
        filtered = [rating for rating in ratings if rating is not None]
        if not filtered:
            return None
        return round(sum(filtered) / len(filtered), 1)
    value = _parse_number(raw)
    if value is None:
        return None
    if value > 10:
        value = value / 10 if value <= 100 else 10.0
    return round(max(0.0, min(value, 10.0)), 1)


def parse_hoa_cents(raw: Any) -> int | None:
    """Parse a HOA fee string into USD cents."""

    return _parse_currency_cents(raw)


def parse_tax_assessed_cents(raw: Any) -> int | None:
    """Parse a tax-assessed value string into USD cents."""

    return _parse_currency_cents(raw)


__all__ = [
    "SQFT_TO_M2",
    "extract_school_rating",
    "parse_hoa_cents",
    "parse_tax_assessed_cents",
    "sqft_to_m2",
]
