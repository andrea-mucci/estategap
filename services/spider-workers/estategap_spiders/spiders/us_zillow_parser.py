"""Parser helpers for Zillow US listing pages."""

from __future__ import annotations

import json
from typing import Any

from ._eu_utils import clean_text, extract_float, extract_int, full_url
from .us_utils import extract_school_rating, parse_hoa_cents, parse_tax_assessed_cents, sqft_to_m2


def _page_props(next_data: dict[str, Any]) -> dict[str, Any]:
    props = next_data.get("props")
    if not isinstance(props, dict):
        return {}
    page_props = props.get("pageProps")
    return page_props if isinstance(page_props, dict) else {}


def _coerce_cache_entry(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            payload = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return payload if isinstance(payload, dict) else {}
    return {}


def _extract_address(payload: dict[str, Any]) -> dict[str, Any]:
    address = payload.get("address") if isinstance(payload.get("address"), dict) else {}
    region = clean_text(
        address.get("state")
        or address.get("stateAbbreviation")
        or payload.get("state")
        or payload.get("stateAbbreviation")
    )
    return {
        "address": clean_text(address.get("streetAddress") or payload.get("streetAddress")),
        "city": clean_text(address.get("city") or payload.get("city")),
        "region": region,
        "postal_code": clean_text(address.get("zipcode") or payload.get("zipcode")),
    }


def _school_rating(payload: dict[str, Any]) -> float | None:
    schools = payload.get("schools")
    if isinstance(schools, list):
        return extract_school_rating([school.get("rating") for school in schools if isinstance(school, dict)])
    return extract_school_rating(payload.get("schoolRating"))


def _base_payload(payload: dict[str, Any]) -> dict[str, Any]:
    area_sqft = extract_float(
        payload.get("livingArea")
        or payload.get("livingAreaValue")
        or payload.get("area")
        or payload.get("areaValue")
    )
    lot_size_sqft = extract_float(
        payload.get("lotAreaValue")
        or payload.get("lotSize")
        or payload.get("lotArea")
        or payload.get("lotSizeSqFt")
    )
    source_url = full_url(
        "https://www.zillow.com",
        payload.get("detailUrl") or payload.get("hdpUrl") or payload.get("propertyUrl") or payload.get("url"),
    )
    lat_long = payload.get("latLong") if isinstance(payload.get("latLong"), dict) else {}
    latitude = extract_float(lat_long.get("latitude") or payload.get("latitude"))
    longitude = extract_float(lat_long.get("longitude") or payload.get("longitude"))
    school_rating = _school_rating(payload)
    return {
        "external_id": clean_text(payload.get("zpid") or payload.get("id")),
        "source_url": source_url,
        "price_usd_cents": int(payload["unformattedPrice"]) * 100
        if payload.get("unformattedPrice") is not None
        else None,
        "currency": "USD",
        "area_sqft": area_sqft,
        "area_m2": sqft_to_m2(area_sqft),
        "bedrooms": extract_int(payload.get("beds") or payload.get("bedrooms")),
        "bathrooms": extract_float(payload.get("baths") or payload.get("bathrooms")),
        "hoa_fees_monthly_usd": parse_hoa_cents(
            payload.get("monthlyHoaFee") or payload.get("hoaFee") or payload.get("monthlyHoaTotal")
        ),
        "lot_size_sqft": lot_size_sqft,
        "lot_size_m2": sqft_to_m2(lot_size_sqft),
        "plot_area_m2": sqft_to_m2(lot_size_sqft),
        "tax_assessed_value_usd": parse_tax_assessed_cents(
            payload.get("taxAssessedValue") or payload.get("taxAssessedAmount")
        ),
        "school_rating": school_rating,
        "zestimate_usd_cents": parse_tax_assessed_cents(payload.get("zestimate")),
        "property_type": clean_text(payload.get("homeType") or payload.get("propertyType") or payload.get("homeTypeText")),
        "lat": latitude,
        "lon": longitude,
        "images_count": len(payload.get("photos") or []),
        "description_orig": clean_text(payload.get("description")),
        **_extract_address(payload),
    }


def parse_search_results(next_data: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract flat search-card payloads from Zillow __NEXT_DATA__."""

    search_state = (
        _page_props(next_data)
        .get("searchPageState", {})
        .get("cat1", {})
        .get("searchResults", {})
        .get("listResults", [])
    )
    results: list[dict[str, Any]] = []
    for item in search_state:
        if not isinstance(item, dict):
            continue
        payload = _base_payload(item)
        if payload.get("source_url") or payload.get("external_id"):
            results.append(payload)
    return results


def parse_listing_detail(next_data: dict[str, Any]) -> dict[str, Any]:
    """Extract a full listing payload from Zillow GDP cache data."""

    cache = _page_props(next_data).get("componentProps", {}).get("gdpClientCache", {})
    if not isinstance(cache, dict):
        return {}
    for value in cache.values():
        entry = _coerce_cache_entry(value)
        candidate = entry.get("property") if isinstance(entry.get("property"), dict) else entry
        if not isinstance(candidate, dict):
            continue
        payload = _base_payload(candidate)
        tax_history = candidate.get("taxHistory")
        if isinstance(tax_history, list) and tax_history:
            latest = next((item for item in tax_history if isinstance(item, dict)), {})
            payload["tax_assessed_value_usd"] = parse_tax_assessed_cents(
                latest.get("taxPaid") or latest.get("value") or payload.get("tax_assessed_value_usd")
            )
            payload["tax_history"] = tax_history
        if payload.get("external_id") or payload.get("source_url"):
            return payload
    return {}


__all__ = ["parse_listing_detail", "parse_search_results"]
