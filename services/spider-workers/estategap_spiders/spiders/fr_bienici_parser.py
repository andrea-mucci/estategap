"""Bien'ici parser helpers."""

from __future__ import annotations

import json
import re
from typing import Any

from ._eu_utils import clean_text, extract_float, extract_int, full_url, price_to_cents


_STATE_RE = re.compile(
    r"window\.__PRELOADED_STATE__\s*=\s*(?P<payload>\{.*?\});",
    re.DOTALL,
)


def extract_preloaded_state(html: str) -> dict[str, Any]:
    match = _STATE_RE.search(html)
    if match is None:
        return {}
    try:
        payload = json.loads(match.group("payload"))
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def parse_listing(data: dict[str, Any]) -> dict[str, Any]:
    bien = data.get("bien") if isinstance(data.get("bien"), dict) else data
    dpe = bien.get("dpe") if isinstance(bien.get("dpe"), dict) else {}
    return {
        "bien": {
            "prixAffiche": price_to_cents(bien.get("prixAffiche")),
            "nbPieces": extract_int(bien.get("nbPieces")),
            "surfaceTotal": extract_float(bien.get("surfaceTotal")),
            "typeBien": clean_text(bien.get("typeBien")),
            "dpe": {"classe": clean_text(dpe.get("classe"))},
            "adresse": clean_text(bien.get("adresse")),
            "ville": clean_text(bien.get("ville")),
            "region": clean_text(bien.get("region")),
            "codePostal": clean_text(bien.get("codePostal")),
            "latitude": extract_float(bien.get("latitude")),
            "longitude": extract_float(bien.get("longitude")),
        },
        "url": full_url("https://www.bienici.com", bien.get("url")),
        "description": clean_text(bien.get("description")),
    }


__all__ = ["extract_preloaded_state", "parse_listing"]
