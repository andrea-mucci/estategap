"""Spider registry and discovery helpers."""

from __future__ import annotations

from .base import BaseSpider

REGISTRY: dict[tuple[str, str], type[BaseSpider]] = {}

from . import es_fotocasa, es_idealista  # noqa: E402,F401


def get_spider(country: str, portal: str) -> type[BaseSpider] | None:
    return REGISTRY.get((country.strip().lower(), portal.strip().lower()))


__all__ = ["BaseSpider", "REGISTRY", "get_spider"]
