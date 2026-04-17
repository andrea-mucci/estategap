"""Parser helpers for Realtor.com HTML pages."""

from __future__ import annotations

import json
import re
from typing import Any

from ._eu_utils import clean_text, extract_float, extract_int, full_url, load_json_ld_blocks, price_to_cents
from .us_utils import sqft_to_m2


_WINDOW_DATA_RE = re.compile(r"window\.__data__\s*=\s*(\{.*?\});", re.DOTALL)


def parse_json_ld(ld_blocks: list[dict[str, Any]]) -> dict[str, Any]:
    """Extract Realtor.com listing fields from JSON-LD blocks."""

    for block in ld_blocks:
        block_type = str(block.get("@type") or "")
        if "RealEstateListing" not in block_type and "Residence" not in block_type:
            continue
        offers = block.get("offers") if isinstance(block.get("offers"), dict) else {}
        address = block.get("address") if isinstance(block.get("address"), dict) else {}
        geo = block.get("geo") if isinstance(block.get("geo"), dict) else {}
        floor_size = block.get("floorSize") if isinstance(block.get("floorSize"), dict) else {}
        area_sqft = extract_float(floor_size.get("value"))
        return {
            "source_url": full_url("https://www.realtor.com", block.get("url")),
            "price_usd_cents": price_to_cents(offers.get("price")),
            "currency": "USD",
            "area_sqft": area_sqft,
            "area_m2": sqft_to_m2(area_sqft),
            "bedrooms": extract_int(block.get("numberOfBedrooms") or block.get("numberOfRooms")),
            "bathrooms": extract_float(block.get("numberOfBathroomsTotal")),
            "property_type": clean_text(block.get("@type")),
            "lat": extract_float(geo.get("latitude")),
            "lon": extract_float(geo.get("longitude")),
            "address": clean_text(address.get("streetAddress")),
            "city": clean_text(address.get("addressLocality")),
            "region": clean_text(address.get("addressRegion")),
            "postal_code": clean_text(address.get("postalCode")),
            "school_district": clean_text(block.get("schoolDistrict")),
            "mls_id": clean_text(block.get("mlsNumber") or block.get("identifier")),
            "description_orig": clean_text(block.get("description")),
        }
    return {}


def _search_key(payload: Any, target: str) -> Any:
    if isinstance(payload, dict):
        for key, value in payload.items():
            if key == target:
                return value
            result = _search_key(value, target)
            if result is not None:
                return result
    if isinstance(payload, list):
        for item in payload:
            result = _search_key(item, target)
            if result is not None:
                return result
    return None


def parse_window_data(html: str) -> dict[str, Any]:
    """Extract supplementary fields from ``window.__data__``."""

    match = _WINDOW_DATA_RE.search(html)
    if match is None:
        return {}
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return {}
    return {
        "crime_index": extract_float(_search_key(payload, "crimeIndex")),
        "school_district": clean_text(_search_key(payload, "schoolDistrict")),
        "mls_id": clean_text(_search_key(payload, "mlsNumber")),
    }


def parse_listing_page(html: str) -> dict[str, Any]:
    """Parse a full Realtor.com listing page."""

    payload = parse_json_ld(load_json_ld_blocks(html))
    payload.update({key: value for key, value in parse_window_data(html).items() if value is not None})
    return payload


__all__ = ["parse_json_ld", "parse_listing_page", "parse_window_data"]
