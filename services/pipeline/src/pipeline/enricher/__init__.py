"""Enrichment service package."""

from .base import BaseEnricher, EnrichmentResult, register_enricher
from .catastro import SpainCatastroEnricher
from .config import EnricherSettings
from .poi import POIDistanceCalculator
from .service import EnricherService

__all__ = [
    "BaseEnricher",
    "EnricherService",
    "EnrichmentResult",
    "EnricherSettings",
    "POIDistanceCalculator",
    "SpainCatastroEnricher",
    "register_enricher",
]
