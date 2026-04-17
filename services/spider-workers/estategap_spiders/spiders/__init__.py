"""Spider registry and discovery helpers."""

from __future__ import annotations

from .base import BaseSpider

REGISTRY: dict[tuple[str, str], type[BaseSpider]] = {}

from . import es_fotocasa, es_idealista  # noqa: E402,F401
from . import (  # noqa: E402,F401
    fr_bienici,
    fr_leboncoin,
    fr_seloger,
    gb_rightmove,
    it_idealista,
    it_immobiliare,
    nl_funda,
    us_redfin,
    us_realtor,
    us_zillow,
)


def get_spider(country: str, portal: str) -> type[BaseSpider] | None:
    return REGISTRY.get((country.strip().lower(), portal.strip().lower()))


__all__ = ["BaseSpider", "REGISTRY", "get_spider"]
