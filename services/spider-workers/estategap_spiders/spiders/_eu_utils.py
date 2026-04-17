"""Shared parsing helpers for EU portal spiders."""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin


_NUMBER_RE = re.compile(r"-?\d+(?:[.,]\d+)?")


def now_utc() -> datetime:
    return datetime.now(UTC)


def extract_int(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    match = _NUMBER_RE.search(str(value).replace(".", "").replace(" ", ""))
    if match is None:
        return None
    return int(float(match.group().replace(",", ".")))


def extract_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().lower()
    text = text.replace("m²", "").replace("€", "").replace("£", "")
    text = re.sub(r"[^0-9,.\-]", "", text)
    if not text:
        return None
    if text.count(",") == 1 and text.count(".") > 1:
        text = text.replace(".", "").replace(",", ".")
    elif "," in text and "." not in text:
        text = text.replace(",", ".")
    else:
        text = text.replace(",", "")
    try:
        return float(text)
    except ValueError:
        return None


def price_to_cents(value: Any) -> int | None:
    amount = extract_float(value)
    return int(amount * 100) if amount is not None else None


def clean_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def full_url(base_url: str, value: Any) -> str | None:
    text = clean_text(value)
    return urljoin(base_url, text) if text else None


def load_json_ld_blocks(html: str) -> list[dict[str, Any]]:
    pattern = re.compile(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(?P<body>.*?)</script>',
        re.IGNORECASE | re.DOTALL,
    )
    blocks: list[dict[str, Any]] = []
    for match in pattern.finditer(html):
        body = match.group("body").strip()
        if not body:
            continue
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, list):
            blocks.extend(item for item in payload if isinstance(item, dict))
        elif isinstance(payload, dict):
            blocks.append(payload)
    return blocks


def extract_external_id(url: str, *, fallback: str | None = None) -> str:
    match = re.search(r"/(\d+)(?:/)?$", url)
    if match:
        return match.group(1)
    return fallback or url.rstrip("/").rsplit("/", 1)[-1]


__all__ = [
    "clean_text",
    "extract_external_id",
    "extract_float",
    "extract_int",
    "full_url",
    "load_json_ld_blocks",
    "now_utc",
    "price_to_cents",
]
