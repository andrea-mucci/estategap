"""Funda parser helpers."""

from __future__ import annotations

import json
import re
from typing import Any

from ._eu_utils import clean_text, extract_float, extract_int, full_url, price_to_cents


_NUXT_RE = re.compile(
    r'<script[^>]+id=["\']nuxt-data["\'][^>]*>(?P<payload>.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


def extract_nuxt_data(html: str) -> dict[str, Any]:
    match = _NUXT_RE.search(html)
    if match is None:
        return {}
    try:
        payload = json.loads(match.group("payload").strip())
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_listing(item: dict[str, Any]) -> dict[str, Any]:
    price = item.get("price") if isinstance(item.get("price"), dict) else {"amount": item.get("price")}
    return {
        "price": {"amount": price_to_cents(price.get("amount"))},
        "livingArea": extract_float(item.get("livingArea")),
        "numberOfRooms": extract_int(item.get("numberOfRooms")),
        "constructionYear": extract_int(item.get("constructionYear")),
        "energyLabel": clean_text(item.get("energyLabel")),
        "bag_id": clean_text(item.get("bag_id")),
        "latitude": extract_float(item.get("latitude")),
        "longitude": extract_float(item.get("longitude")),
        "propertyType": clean_text(item.get("propertyType")),
        "url": full_url("https://www.funda.nl", item.get("url")),
        "description": clean_text(item.get("description")),
        "address": clean_text(item.get("address")),
        "city": clean_text(item.get("city")),
        "region": clean_text(item.get("region")),
        "postalCode": clean_text(item.get("postalCode")),
    }


__all__ = ["extract_nuxt_data", "parse_listing"]
