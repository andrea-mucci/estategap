"""Search + alert finalization helpers."""

from __future__ import annotations

from typing import Any


def criteria_to_search_params(criteria: dict[str, Any]) -> dict[str, Any]:
    """Map normalized criteria keys into a downstream search payload."""

    params: dict[str, Any] = {}
    for key in ("location", "property_type", "deal_type", "country_code", "style"):
        value = criteria.get(key)
        if value:
            params[key] = value
    price_range = criteria.get("price_range")
    if isinstance(price_range, dict):
        if price_range.get("min") is not None:
            params["price_min"] = price_range["min"]
        if price_range.get("max") is not None:
            params["price_max"] = price_range["max"]
    size_range = criteria.get("size_range")
    if isinstance(size_range, dict):
        if size_range.get("min") is not None:
            params["size_min"] = size_range["min"]
        if size_range.get("max") is not None:
            params["size_max"] = size_range["max"]
    amenities = criteria.get("amenities")
    if amenities:
        params["amenities"] = amenities
    extras = criteria.get("extras")
    if extras:
        params["extras"] = extras
    return params


class CriteriaFinalizer:
    """Execute the downstream listing-search and alert-creation flow."""

    def __init__(self, gateway_client: Any | None = None) -> None:
        self._gateway_client = gateway_client

    async def finalize(
        self,
        session_id: str,
        criteria: dict[str, Any],
        gateway_stub: Any | None = None,
    ) -> tuple[list[str], str]:
        client = gateway_stub or self._gateway_client
        if client is None:
            return [], ""

        search_payload = criteria_to_search_params(criteria)
        listing_ids: list[str] = []
        search_result = await client.search_listings(search_payload)
        if isinstance(search_result, dict):
            listing_ids = [str(value) for value in search_result.get("listing_ids", [])]
        elif search_result is not None:
            listing_ids = [str(value) for value in getattr(search_result, "listing_ids", [])]

        alert_result = await client.create_alert_rule(
            {
                "session_id": session_id,
                "criteria": criteria,
                "listing_ids": listing_ids,
            }
        )
        if isinstance(alert_result, dict):
            alert_rule_id = str(alert_result.get("alert_rule_id", ""))
        else:
            alert_rule_id = str(getattr(alert_result, "alert_rule_id", ""))
        return listing_ids, alert_rule_id
