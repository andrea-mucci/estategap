"""Parser helpers for Redfin US API responses."""

from __future__ import annotations

from typing import Any

from ._eu_utils import clean_text, extract_float, extract_int, full_url, price_to_cents
from .us_utils import extract_school_rating, parse_hoa_cents, parse_tax_assessed_cents, sqft_to_m2


def parse_school_data(schools: list[dict[str, Any]]) -> float | None:
    """Average Redfin school ratings on a 0–10 scale."""

    return extract_school_rating(
        [school.get("rating") or school.get("greatSchoolsRating") for school in schools if isinstance(school, dict)]
    )


def parse_above_fold(payload: dict[str, Any]) -> dict[str, Any]:
    """Flatten Redfin's above-the-fold response into the raw listing shape."""

    root = payload.get("payload") if isinstance(payload.get("payload"), dict) else payload
    main = root.get("mainHouseInfo") if isinstance(root.get("mainHouseInfo"), dict) else root
    address = root.get("addressInfo") if isinstance(root.get("addressInfo"), dict) else {}
    area_sqft = extract_float(main.get("sqFt") or main.get("livingArea") or main.get("sqFtInfo"))
    lot_size_sqft = extract_float(main.get("lotSizeSqFt") or main.get("lotSize"))
    return {
        "external_id": clean_text(main.get("propertyId") or main.get("homeId")),
        "source_url": full_url("https://www.redfin.com", main.get("url") or root.get("url")),
        "price_usd_cents": price_to_cents(main.get("price")),
        "currency": "USD",
        "area_sqft": area_sqft,
        "area_m2": sqft_to_m2(area_sqft),
        "bedrooms": extract_int(main.get("beds") or main.get("bedrooms")),
        "bathrooms": extract_float(main.get("baths") or main.get("bathrooms")),
        "hoa_fees_monthly_usd": parse_hoa_cents(main.get("monthlyHoaDues")),
        "lot_size_sqft": lot_size_sqft,
        "lot_size_m2": sqft_to_m2(lot_size_sqft),
        "plot_area_m2": sqft_to_m2(lot_size_sqft),
        "tax_assessed_value_usd": parse_tax_assessed_cents(
            main.get("taxAssessedValue") or root.get("taxInfo", {}).get("assessedValue")
        ),
        "school_rating": parse_school_data(root.get("schoolsData") or []),
        "compete_score": extract_int(main.get("competeScore")),
        "property_type": clean_text(main.get("propertyType") or main.get("homeType")),
        "lat": extract_float(main.get("latitude") or root.get("latitude")),
        "lon": extract_float(main.get("longitude") or root.get("longitude")),
        "images_count": len(root.get("photosInfo", {}).get("photos", [])),
        "description_orig": clean_text(root.get("marketingRemarks") or main.get("description")),
        "address": clean_text(address.get("streetLine") or root.get("streetLine")),
        "city": clean_text(address.get("city") or root.get("city")),
        "region": clean_text(address.get("stateCode") or root.get("stateCode")),
        "postal_code": clean_text(address.get("zip") or root.get("zip")),
    }


__all__ = ["parse_above_fold", "parse_school_data"]
