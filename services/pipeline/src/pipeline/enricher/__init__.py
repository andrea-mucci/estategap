"""Enrichment service package."""

from .base import BaseEnricher, EnrichmentResult, register_enricher
from .catastro import SpainCatastroEnricher
from .config import EnricherSettings
from .fr_dvf import FranceDVFEnricher
from .gb_land_registry import UKLandRegistryEnricher
from .it_omi import ItalyOMIEnricher
from .nl_bag import NetherlandsBAGEnricher
from .poi import POIDistanceCalculator
from .service import EnricherService

__all__ = [
    "BaseEnricher",
    "EnricherService",
    "EnrichmentResult",
    "EnricherSettings",
    "FranceDVFEnricher",
    "ItalyOMIEnricher",
    "NetherlandsBAGEnricher",
    "POIDistanceCalculator",
    "SpainCatastroEnricher",
    "UKLandRegistryEnricher",
    "register_enricher",
]
