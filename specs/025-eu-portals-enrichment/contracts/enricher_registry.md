# Contract: Enricher Registry Extensions

**Feature**: 025-eu-portals-enrichment  
**Interface type**: Internal Python module contract  
**Existing interface**: `services/pipeline/src/pipeline/enricher/__init__.py`

---

## New Enricher Registrations

The following enricher classes must be imported in `enricher/__init__.py`:

```python
from pipeline.enricher.fr_dvf import FranceDVFEnricher          # noqa: F401
from pipeline.enricher.gb_land_registry import UKLandRegistryEnricher  # noqa: F401
from pipeline.enricher.it_omi import ItalyOMIEnricher            # noqa: F401
from pipeline.enricher.nl_bag import NetherlandsBAGEnricher      # noqa: F401
```

## Required Decorator + Interface

```python
@register_enricher("FR")   # or "GB", "IT", "NL"
class FranceDVFEnricher(BaseEnricher):
    async def enrich(self, listing: NormalizedListing) -> EnrichmentResult:
        ...
```

## Enricher-to-Country Mapping

| Enricher Class | Country Code | Registered For |
|---------------|-------------|----------------|
| `FranceDVFEnricher` | `FR` | All FR listings |
| `UKLandRegistryEnricher` | `GB` | All GB listings |
| `ItalyOMIEnricher` | `IT` | All IT listings |
| `NetherlandsBAGEnricher` | `NL` | All NL listings |

## EnrichmentResult Updates Contract

### FranceDVFEnricher
```python
EnrichmentResult(
    status="completed" | "partial" | "no_match" | "failed",
    updates={
        "dvf_nearby_count": int,        # 0–5
        "dvf_median_price_m2": Decimal, # EUR/m²; None if no_match
    }
)
```
Requires: `listing.location_wkt` is set (coordinates available).

### UKLandRegistryEnricher
```python
EnrichmentResult(
    status="completed" | "partial" | "no_match" | "failed",
    updates={
        "uk_lr_match_count": int,
        "uk_lr_last_price_gbp": int,    # pence; None if no_match
        "uk_lr_last_date": date,         # None if no_match
    }
)
```
Requires: `listing.postal_code` is set.

### ItalyOMIEnricher
```python
EnrichmentResult(
    status="completed" | "partial" | "no_match" | "failed",
    updates={
        "omi_zone_code": str,
        "omi_price_min_eur_m2": Decimal,
        "omi_price_max_eur_m2": Decimal,
        "omi_period": str,              # e.g., "2024-H1"
        "price_vs_omi": Decimal,        # ratio; None if price unavailable
    }
)
```
Requires: `listing.location_wkt` is set.

### NetherlandsBAGEnricher
```python
EnrichmentResult(
    status="completed" | "partial" | "no_match" | "failed",
    updates={
        "bag_id": str,
        "year_built": int,
        "official_area_m2": Decimal,
        "building_geometry_wkt": str,   # WKT polygon
    }
)
```
Requires: `listing.postal_code` and `listing.address` are set; or `listing.bag_id` pre-populated by Funda spider.
