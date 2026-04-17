"""Human-readable labels for SHAP feature explanations."""

from __future__ import annotations

FEATURE_LABELS: dict[str, str] = {
    "lat": "Latitude of {value:.4f} {direction} the estimate",
    "lon": "Longitude of {value:.4f} {direction} the estimate",
    "dist_metro_m": "{value:,.0f}m to the nearest metro {direction} the estimate",
    "dist_train_m": "{value:,.0f}m to the nearest train {direction} the estimate",
    "dist_beach_m": "{value:,.0f}m to the nearest beach {direction} the estimate",
    "zone_median_price_m2": "Zone median price of {value:,.0f}€/m² {direction} the estimate",
    "zone_listing_density": "Zone listing density of {value:,.0f} homes {direction} the estimate",
    "zone_avg_income": "Zone average income of {value:,.0f}€ {direction} the estimate",
    "built_area_m2": "{value:.0f}m² built area {direction} the estimate",
    "usable_area_m2": "{value:.0f}m² usable area {direction} the estimate",
    "bedrooms": "{value:.0f} bedrooms {direction} the estimate",
    "bathrooms": "{value:.0f} bathrooms {direction} the estimate",
    "floor_number": "Floor {value:.0f} {direction} the estimate",
    "total_floors": "Building height of {value:.0f} floors {direction} the estimate",
    "has_lift": "Lift availability {direction} the estimate",
    "parking_spaces": "{value:.0f} parking spaces {direction} the estimate",
    "building_age_years": "Building age of {value:.0f} years {direction} the estimate",
    "community_fees_eur": "Community fees of {value:,.0f}€ {direction} the estimate",
    "month_sin": "Seasonality at listing month {direction} the estimate",
    "month_cos": "Seasonality cycle position {direction} the estimate",
    "usable_built_ratio": "Usable-to-built area ratio of {value:.2f} {direction} the estimate",
    "price_per_m2_eur": "Asking price of {value:,.0f}€/m² {direction} the estimate",
    "photo_count": "{value:.0f} photos {direction} the estimate",
    "has_photos": "Photo availability {direction} the estimate",
    "data_completeness": "Listing data completeness of {value:.0%} {direction} the estimate",
    "has_energy_cert": "Energy certificate availability {direction} the estimate",
    "energy_cert": "Energy certificate grade {direction} the estimate",
    "energy_cert_encoded": "Energy certificate grade {direction} the estimate",
    "condition": "Property condition {direction} the estimate",
    "condition_encoded": "Property condition {direction} the estimate",
    "property_type_apartment": "Apartment property type {direction} the estimate",
    "property_type_house": "House property type {direction} the estimate",
    "property_type_studio": "Studio property type {direction} the estimate",
    "property_type_penthouse": "Penthouse property type {direction} the estimate",
    "property_type_duplex": "Duplex property type {direction} the estimate",
    "property_type_other": "Other property type {direction} the estimate",
}


def render_label(feature_name: str, value: float, shap_value: float) -> str:
    """Render a stable label for a SHAP feature."""

    direction = "pushes estimate up" if shap_value > 0 else "pulls estimate down"
    template = FEATURE_LABELS.get(
        feature_name,
        f"{feature_name.replace('_', ' ').title()} {{direction}} the estimate",
    )
    try:
        return template.format(value=value, shap_value=shap_value, direction=direction)
    except (KeyError, ValueError):
        return f"{feature_name.replace('_', ' ').title()} {direction} the estimate"


__all__ = ["FEATURE_LABELS", "render_label"]
