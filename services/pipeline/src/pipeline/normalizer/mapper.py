"""Portal-mapping loader and raw payload translator for the normalizer."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

import yaml

from . import transforms


DECIMAL_TARGETS = {
    "asking_price",
    "asking_price_eur",
    "built_area",
    "built_area_m2",
    "plot_area_m2",
    "price_per_m2_eur",
    "usable_area_m2",
    "_lat",
    "_lon",
}
INTEGER_TARGETS = {
    "bathrooms",
    "bedrooms",
    "leasehold_years_remaining",
    "floor_number",
    "images_count",
    "parking_spaces",
    "total_floors",
    "year_built",
}
BOOLEAN_TARGETS = {"has_lift", "has_pool"}


@dataclass(slots=True, frozen=True)
class FieldMapping:
    """One raw-field to normalized-field translation rule."""

    target: str
    transform: str | None = None


@dataclass(slots=True, frozen=True)
class PortalMapping:
    """All translation rules required for one portal/country pair."""

    portal: str
    country: str
    fields: dict[str, FieldMapping]
    property_type_map: dict[str, str]
    condition_map: dict[str, str]
    currency_field: str | None
    area_unit_field: str | None
    country_uses_pieces: bool
    expected_fields: tuple[str, ...]


class PortalMapper:
    """Load mapping YAML files and apply them to raw listing payloads."""

    _TRANSFORMS = {
        "map_condition": transforms.map_condition,
        "map_property_type": transforms.map_property_type,
    }

    def __init__(self, mappings: dict[tuple[str, str], PortalMapping]) -> None:
        self._mappings = mappings

    @classmethod
    def load_all(cls, mappings_dir: Path) -> dict[tuple[str, str], PortalMapping]:
        """Load and validate every portal mapping from a directory."""

        loaded: dict[tuple[str, str], PortalMapping] = {}
        for mapping_path in sorted(mappings_dir.glob("*.yaml")):
            with mapping_path.open("r", encoding="utf-8") as handle:
                raw = yaml.safe_load(handle) or {}
            portal = raw.get("portal")
            country = raw.get("country")
            fields_block = raw.get("fields")
            if not isinstance(portal, str) or not isinstance(country, str) or not isinstance(fields_block, dict):
                raise ValueError(f"Invalid mapping file: {mapping_path}")
            fields: dict[str, FieldMapping] = {}
            for source_field, definition in fields_block.items():
                if not isinstance(source_field, str) or not isinstance(definition, dict):
                    raise ValueError(f"Invalid field mapping in {mapping_path}")
                target = definition.get("target")
                transform = definition.get("transform")
                if not isinstance(target, str):
                    raise ValueError(f"Invalid target in {mapping_path} for {source_field!r}")
                if transform is not None and not isinstance(transform, str):
                    raise ValueError(f"Invalid transform in {mapping_path} for {source_field!r}")
                fields[source_field] = FieldMapping(target=target, transform=transform)
            mapping = PortalMapping(
                portal=portal,
                country=country.upper(),
                fields=fields,
                property_type_map={str(key): str(value) for key, value in (raw.get("property_type_map") or {}).items()},
                condition_map={str(key): str(value) for key, value in (raw.get("condition_map") or {}).items()},
                currency_field=raw.get("currency_field") if isinstance(raw.get("currency_field"), str) else None,
                area_unit_field=raw.get("area_unit_field") if isinstance(raw.get("area_unit_field"), str) else None,
                country_uses_pieces=bool(raw.get("country_uses_pieces", False)),
                expected_fields=tuple(
                    str(field) for field in raw.get("expected_fields", []) if isinstance(field, str)
                ),
            )
            loaded[(mapping.country, mapping.portal)] = mapping
        return loaded

    def get(self, country: str, portal: str) -> PortalMapping | None:
        """Return the mapping for a portal, if one was loaded."""

        return self._mappings.get((country.upper(), portal))

    def apply(
        self,
        mapping: PortalMapping,
        raw_json: dict[str, Any],
        exchange_rates: dict[str, Decimal] | None = None,
    ) -> dict[str, Any]:
        """Translate a raw portal payload into the normalized listing shape."""

        mapped: dict[str, Any] = {}
        for source_field, rule in mapping.fields.items():
            value = _extract_value(raw_json, source_field)
            if value is None:
                continue
            value = _coerce_value(rule.target, value)
            if rule.transform:
                transform_fn = self._TRANSFORMS.get(rule.transform)
                if transform_fn is None:
                    raise ValueError(f"Unsupported transform {rule.transform!r}")
                if rule.transform == "map_property_type":
                    value = transform_fn(str(value), mapping.property_type_map)
                elif rule.transform == "map_condition":
                    value = transform_fn(str(value), mapping.condition_map)
            mapped[rule.target] = value

        currency = "EUR"
        if mapping.currency_field:
            raw_currency = _extract_value(raw_json, mapping.currency_field)
            if raw_currency is not None:
                currency = str(raw_currency).upper()
        mapped["currency"] = currency

        area_unit = "m2"
        if mapping.area_unit_field:
            raw_area_unit = _extract_value(raw_json, mapping.area_unit_field)
            if raw_area_unit is not None:
                area_unit = str(raw_area_unit).lower()
        mapped["area_unit"] = area_unit

        asking_price = mapped.get("asking_price")
        if asking_price is not None:
            if not isinstance(asking_price, Decimal):
                asking_price = _to_decimal(asking_price)
                mapped["asking_price"] = asking_price
            if exchange_rates is None:
                exchange_rates = {"EUR": Decimal("1")}
            mapped["asking_price_eur"] = transforms.currency_convert(asking_price, currency, exchange_rates)

        built_area = mapped.get("built_area")
        if built_area is not None:
            if not isinstance(built_area, Decimal):
                built_area = _to_decimal(built_area)
                mapped["built_area"] = built_area
            mapped["built_area_m2"] = transforms.area_to_m2(built_area, area_unit)

        if mapping.country_uses_pieces and mapped.get("bedrooms") is not None:
            mapped["bedrooms"] = transforms.pieces_to_bedrooms(int(mapped["bedrooms"]))

        latitude = mapped.pop("_lat", None)
        longitude = mapped.pop("_lon", None)
        if latitude is not None and longitude is not None:
            mapped["location_wkt"] = f"POINT({longitude} {latitude})"

        property_type = mapped.get("property_type")
        if isinstance(property_type, str):
            mapped["property_category"] = property_type

        asking_price_eur = mapped.get("asking_price_eur")
        built_area_m2 = mapped.get("built_area_m2")
        if isinstance(asking_price_eur, Decimal) and isinstance(built_area_m2, Decimal) and built_area_m2 > 0:
            mapped["price_per_m2_eur"] = (asking_price_eur / built_area_m2).quantize(Decimal("0.01"))

        return mapped


def _extract_value(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _coerce_value(target: str, value: Any) -> Any:
    if value is None:
        return None
    if target in DECIMAL_TARGETS:
        return _to_decimal(value)
    if target in INTEGER_TARGETS:
        if isinstance(value, bool):
            return int(value)
        return int(value)
    if target in BOOLEAN_TARGETS:
        return _to_bool(value)
    return value


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "y", "si"}:
            return True
        if normalized in {"0", "false", "no", "n"}:
            return False
    return bool(value)


__all__ = ["FieldMapping", "PortalMapper", "PortalMapping"]
