"""SeLoger parser helpers."""

from __future__ import annotations

from typing import Any

from parsel import Selector

from ._eu_utils import clean_text, extract_float, full_url, load_json_ld_blocks


def parse_json_ld(html: str) -> dict[str, Any]:
    for block in load_json_ld_blocks(html):
        if clean_text(block.get("@type")) not in {"RealEstateListing", "Apartment", "House"}:
            continue
        address = block.get("address") if isinstance(block.get("address"), dict) else {}
        geo = block.get("geo") if isinstance(block.get("geo"), dict) else {}
        return {
            "json_ld": block,
            "energyEfficiencyScaleMin": clean_text(
                block.get("energyEfficiencyScaleMin") or block.get("energyEfficiencyScaleMax")
            ),
            "latitude": extract_float(geo.get("latitude")),
            "longitude": extract_float(geo.get("longitude")),
            "url": full_url("https://www.seloger.com", block.get("url")),
            "description": clean_text(block.get("description")),
            "images_count": len(block.get("image", []) if isinstance(block.get("image"), list) else []),
            "address": clean_text(address.get("streetAddress")),
        }
    return {}


def parse_search_page(html: str) -> list[dict[str, Any]]:
    selector = Selector(html)
    urls = selector.css("article[data-url]::attr(data-url), a[data-testid='sl-link']::attr(href)").getall()
    return [{"url": full_url("https://www.seloger.com", url)} for url in urls if clean_text(url)]


__all__ = ["parse_json_ld", "parse_search_page"]
