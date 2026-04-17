"""Base abstractions for country-specific enrichment plugins."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

from estategap_common.models import NormalizedListing

EnrichmentStatus = Literal["completed", "partial", "no_match", "failed"]


@dataclass(slots=True)
class EnrichmentResult:
    """Result of an enricher run against a single listing."""

    status: EnrichmentStatus
    updates: dict[str, object] = field(default_factory=dict)
    error: str | None = None


class BaseEnricher(ABC):
    """Interface implemented by all per-country enrichers."""

    @abstractmethod
    async def enrich(self, listing: NormalizedListing) -> EnrichmentResult:
        """Return listing field updates without raising."""


_REGISTRY: dict[str, list[type[BaseEnricher]]] = {}


def register_enricher(country: str):
    """Register an enricher class for a country code."""

    normalized_country = country.upper()

    def decorator(cls: type[BaseEnricher]) -> type[BaseEnricher]:
        _REGISTRY.setdefault(normalized_country, []).append(cls)
        return cls

    return decorator


def get_registered_enrichers(country: str) -> list[type[BaseEnricher]]:
    """Return all enricher classes configured for a country."""

    return list(_REGISTRY.get(country.upper(), ()))


__all__ = [
    "BaseEnricher",
    "EnrichmentResult",
    "EnrichmentStatus",
    "get_registered_enrichers",
    "register_enricher",
]
