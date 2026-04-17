"""Idealista Italy parser helpers."""

from __future__ import annotations

from typing import Any

from ._eu_utils import (
    clean_text,
    extract_float,
    extract_int,
    full_url,
    load_json_ld_blocks,
    price_to_cents,
)


def parse_api_response(item: dict[str, Any]) -> dict[str, Any]:
    images = item.get("multimedia", {}).get("images", []) if isinstance(item.get("multimedia"), dict) else []
    return {
        "prezzo": price_to_cents(item.get("price") or item.get("prezzo")),
        "superficie": extract_float(item.get("size") or item.get("superficie")),
        "locali": extract_int(item.get("rooms") or item.get("locali")),
        "bagni": extract_int(item.get("bathrooms") or item.get("bagni")),
        "piano": extract_int(item.get("floor") or item.get("piano")),
        "annoCostruzione": extract_int(item.get("constructionYear") or item.get("annoCostruzione")),
        "classeEnergetica": clean_text(
            ((item.get("energyCertification") or {}).get("energyConsumption") or {}).get("rating")
        ),
        "tipologiaImmobile": clean_text(item.get("propertyType") or item.get("tipologiaImmobile")),
        "statoImmobile": clean_text(item.get("status") or item.get("statoImmobile")),
        "riscaldamento": clean_text(item.get("heatingType") or item.get("riscaldamento")),
        "latitudine": extract_float(item.get("latitude") or item.get("latitudine")),
        "longitudine": extract_float(item.get("longitude") or item.get("longitudine")),
        "url": full_url("https://www.idealista.it", item.get("url") or item.get("link")),
        "indirizzo": clean_text(item.get("address") or item.get("indirizzo")),
        "comune": clean_text(item.get("municipality") or item.get("comune")),
        "provincia": clean_text(item.get("province") or item.get("provincia")),
        "codicePostale": clean_text(item.get("postalCode") or item.get("codicePostale")),
        "numFoto": len(images),
        "publishedAt": clean_text(item.get("publicationDate")),
    }


def parse_detail_page(html: str) -> dict[str, Any]:
    for block in load_json_ld_blocks(html):
        address = block.get("address") if isinstance(block.get("address"), dict) else {}
        geo = block.get("geo") if isinstance(block.get("geo"), dict) else {}
        offers = block.get("offers") if isinstance(block.get("offers"), dict) else {}
        return {
            "prezzo": price_to_cents(offers.get("price")),
            "superficie": extract_float(
                (block.get("floorSize") or {}).get("value")
                if isinstance(block.get("floorSize"), dict)
                else None
            ),
            "locali": extract_int(block.get("numberOfRooms")),
            "bagni": extract_int(block.get("numberOfBathroomsTotal")),
            "classeEnergetica": clean_text(
                block.get("energyEfficiencyScaleMin") or block.get("energyEfficiencyScaleMax")
            ),
            "tipologiaImmobile": clean_text(block.get("@type")),
            "latitudine": extract_float(geo.get("latitude")),
            "longitudine": extract_float(geo.get("longitude")),
            "url": clean_text(block.get("url")),
            "indirizzo": clean_text(address.get("streetAddress")),
            "comune": clean_text(address.get("addressLocality")),
            "provincia": clean_text(address.get("addressRegion")),
            "codicePostale": clean_text(address.get("postalCode")),
            "numFoto": len(block.get("image", []) if isinstance(block.get("image"), list) else []),
        }
    return {}


__all__ = ["parse_api_response", "parse_detail_page"]
