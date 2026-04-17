"""Rightmove parser helpers."""

from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from ._eu_utils import clean_text, extract_float, extract_int, load_json_ld_blocks


def parse_json_ld(html: str) -> dict[str, Any]:
    for block in load_json_ld_blocks(html):
        offers = block.get("offers") if isinstance(block.get("offers"), dict) else {}
        if offers.get("priceCurrency") != "GBP":
            continue
        return {
            "json_ld": block,
            "currency": "GBP",
        }
    return {}


def parse_uk_fields(soup: BeautifulSoup) -> dict[str, Any]:
    council_tax = soup.select_one(".dp-council-tax, [data-testid='council-tax-band']")
    epc = soup.select_one(".dp-epc-rating, [data-testid='epc-rating']")
    tenure = soup.select_one(".dp-tenure, [data-testid='tenure']")
    years = soup.select_one("[data-testid='leasehold-years']")
    council_text = clean_text(council_tax.get_text(" ", strip=True) if council_tax else None)
    epc_text = clean_text(epc.get_text(" ", strip=True) if epc else None)
    return {
        "councilTaxBand": council_text[-1] if council_text else None,
        "epcRating": epc_text[-1] if epc_text else None,
        "energyRating": epc_text[-1] if epc_text else None,
        "tenure": clean_text(tenure.get_text(" ", strip=True) if tenure else None),
        "leaseholdYearsRemaining": extract_int(years.get_text(" ", strip=True) if years else None),
    }


__all__ = ["parse_json_ld", "parse_uk_fields"]
