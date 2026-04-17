"""LeBonCoin parser helpers."""

from __future__ import annotations

import json
from typing import Any

from bs4 import BeautifulSoup, Tag

from ._eu_utils import clean_text, extract_float, extract_int, full_url, price_to_cents


def detect_seller_type(card: Tag) -> str:
    owner_type = clean_text(card.get("data-owner-type"))
    if owner_type:
        return "pro" if owner_type.lower().startswith("pro") else "private"
    badges = " ".join(text.strip().lower() for text in card.stripped_strings)
    return "pro" if "pro" in badges else "private"


def parse_listing_card(card: Tag) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    raw = clean_text(card.get("data-listing"))
    if raw:
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {}
    title = payload.get("title") if isinstance(payload, dict) else None
    city = payload.get("city") if isinstance(payload, dict) else None
    region = payload.get("region") if isinstance(payload, dict) else None
    postal_code = payload.get("postal_code") if isinstance(payload, dict) else None
    return {
        "price": {"value": price_to_cents(payload.get("price") or card.get("data-price"))},
        "attributes": {
            "rooms_count": extract_int(payload.get("rooms_count") or card.get("data-rooms")),
            "square": extract_float(payload.get("square") or card.get("data-square")),
            "real_estate_type": clean_text(payload.get("real_estate_type") or card.get("data-property-type")),
        },
        "location": {
            "lng": extract_float(payload.get("lng") or card.get("data-lng")),
            "lat": extract_float(payload.get("lat") or card.get("data-lat")),
            "city": clean_text(city or card.get("data-city")),
            "region": clean_text(region or card.get("data-region")),
            "postal_code": clean_text(postal_code or card.get("data-postal-code")),
        },
        "owner": {"type": detect_seller_type(card)},
        "url": full_url("https://www.leboncoin.fr", payload.get("url") or card.get("data-url")),
        "description": clean_text(title or payload.get("description")),
    }


def parse_search_cards(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    return [parse_listing_card(card) for card in soup.select("[data-testid='listing-card'], article[data-url]")]


__all__ = ["detect_seller_type", "parse_listing_card", "parse_search_cards"]
