# Data Model: US Portal Spiders & Country-Specific ML Models

**Feature**: 026-us-spiders-country-ml  
**Date**: 2026-04-17

---

## Overview

This feature extends three existing data domains:

1. **Listings** — new US-specific columns on the existing `listings` partitioned table
2. **Zones** — no schema change; existing `zones` table supports US TIGER/Line imports
3. **Model Versions** — three new columns on `model_versions` to track transfer learning state

No new tables are required. All changes are additive (new nullable columns + new partition value).

---

## 1. Listings Table Extensions

The existing `listings` table is partitioned by `country`. A new partition `listings_us` will be created automatically when the first US listing is inserted (PostgreSQL list partitioning).

### New Nullable Columns (added via Alembic migration)

```sql
-- US-specific spider fields
ALTER TABLE listings ADD COLUMN IF NOT EXISTS hoa_fees_monthly_usd    INTEGER;   -- cents
ALTER TABLE listings ADD COLUMN IF NOT EXISTS lot_size_sqft            NUMERIC(10,2);
ALTER TABLE listings ADD COLUMN IF NOT EXISTS lot_size_m2              NUMERIC(10,2);
ALTER TABLE listings ADD COLUMN IF NOT EXISTS tax_assessed_value_usd   INTEGER;   -- cents
ALTER TABLE listings ADD COLUMN IF NOT EXISTS school_rating            NUMERIC(3,1); -- 0–10
ALTER TABLE listings ADD COLUMN IF NOT EXISTS zestimate_reference_usd  INTEGER;   -- cents, Zillow only
ALTER TABLE listings ADD COLUMN IF NOT EXISTS compete_score            SMALLINT;  -- 0–100, Redfin only
ALTER TABLE listings ADD COLUMN IF NOT EXISTS mls_id                   TEXT;      -- Realtor.com only

-- Existing area_sqft stored for traceability (already present? verify migration)
ALTER TABLE listings ADD COLUMN IF NOT EXISTS built_area_sqft          NUMERIC(10,2);
```

**Rationale for cents storage**: Consistent with existing `asking_price` and `last_sold_price` which are stored as integer cents in the source currency.

### Existing Columns Used

| Column | Usage |
|--------|-------|
| `country` | `"US"` for all US listings |
| `asking_price` | USD cents |
| `asking_price_eur` | EUR cents (converted via exchange rate service) |
| `built_area_m2` | m² (converted from sqft × 0.092903) |
| `currency` | `"USD"` |
| `source_portal` | `"zillow"` / `"redfin"` / `"realtor_com"` |
| `location` | PostGIS POINT (lng, lat) |
| `zone_id` | FK → `zones.id` (ZIP-level zone after import) |

---

## 2. Zones Table (No Schema Change)

The existing `zones` table already has all required columns. New US zones are inserted with:

| Column | US Value |
|--------|---------|
| `country` | `"US"` |
| `level` | `"state"` / `"county"` / `"city"` / `"zipcode"` / `"neighbourhood"` |
| `name` | Human-readable name from TIGER/Line `NAME` field |
| `code` | FIPS code (state: 2-digit, county: 5-digit, ZIP: 5-digit ZCTA) |
| `geometry` | PostGIS MULTIPOLYGON from shapefile |
| `parent_id` | FK to parent zone (resolved by `ST_Within`) |

---

## 3. Model Versions Table Extensions

```sql
ALTER TABLE model_versions ADD COLUMN IF NOT EXISTS transfer_learned   BOOLEAN NOT NULL DEFAULT FALSE;
ALTER TABLE model_versions ADD COLUMN IF NOT EXISTS base_country        CHAR(2);    -- 'ES' if transfer from Spain
ALTER TABLE model_versions ADD COLUMN IF NOT EXISTS confidence          TEXT NOT NULL DEFAULT 'full';
  -- CHECK confidence IN ('full', 'transfer', 'insufficient_data')
```

### Confidence State Machine

```
[no model]
    │
    ├─ count >= 5000 ──────────────────→ full (independent training)
    │
    ├─ 1000 <= count < 5000
    │   └─ transfer from Spain ──→ MAPE <= 20% → transfer
    │                           └─ MAPE >  20% → insufficient_data
    │
    └─ count < 1000 ──────────────────→ (no model trained, zone-median only)

insufficient_data ──→ count >= 5000 ──→ full (retrain)
transfer          ──→ count >= 5000 ──→ full (retrain)
```

---

## 4. Country Feature Configuration (YAML, not DB)

Stored as files in `services/ml/estategap_ml/config/`. Not persisted in PostgreSQL.

### Schema of `features_{country}.yaml`

```yaml
# Required fields
country: str             # ISO-2 country code, lowercase (e.g., "us", "es")
description: str         # Human-readable description

# Feature lists (all items are column names in the training dataset)
base_features: list[str]              # Shared across all countries
country_specific_features: list[str] # Optional; only present in this country
optional_features: list[str]         # Present in subset of listings; imputed if missing

# Encoding rules for categorical columns
encoding_rules:
  {column_name}:
    categories: list[str]   # Ordered category list
    strategy: str           # "onehot" | "label" | "ordinal"

# Columns to exclude from this country's model (even if present in DB)
feature_drops: list[str]
```

### Entity: CountryFeatureConfig (in-memory Pydantic model)

```python
class EncodingRule(BaseModel):
    categories: list[str]
    strategy: Literal["onehot", "label", "ordinal"]

class CountryFeatureConfig(BaseModel):
    country: str
    description: str
    base_features: list[str]
    country_specific_features: list[str] = []
    optional_features: list[str] = []
    encoding_rules: dict[str, EncodingRule] = {}
    feature_drops: list[str] = []

    @property
    def all_features(self) -> list[str]:
        return self.base_features + self.country_specific_features
```

---

## 5. Feature Sets Per Country

### Base Features (all countries)

```
area_m2, bedrooms, bathrooms, floor_number, building_age_years,
zone_median_price_eur_m2, dist_to_center_km, dist_to_transit_km,
property_type_encoded, photo_count, is_new_construction
```

### Country-Specific Extensions

| Country | Additional Features |
|---------|-------------------|
| Spain (ES) | `energy_cert_encoded`, `has_elevator`, `community_fees_monthly`, `orientation_encoded` |
| France (FR) | `dpe_rating`, `dvf_median_transaction_price_eur_m2`, `pieces_count` |
| UK (GB) | `council_tax_band_encoded`, `epc_rating`, `leasehold_flag`, `land_registry_last_price_gbp_m2` |
| USA (US) | `hoa_fees_monthly_usd`, `lot_size_m2`, `tax_assessed_value_usd`, `school_rating`, `zestimate_reference_usd` |
| Italy (IT) | `ape_rating`, `omi_zone_min_price_eur_m2`, `omi_zone_max_price_eur_m2` |
| Netherlands (NL) | *(base features only; transfer from ES)* |

---

## 6. Raw Listing Model (Spider Output)

Spider parsers produce a `RawUSListing` dict (same `RawListing` TypedDict structure as EU spiders) with these additional keys:

```python
class RawUSListing(TypedDict, total=False):
    # Standard fields (all spiders)
    external_id: str
    source_url: str
    portal: str               # "zillow" | "redfin" | "realtor_com"
    country: str              # "US"
    price_usd_cents: int
    area_sqft: float
    area_m2: float            # pre-computed by us_utils.sqft_to_m2
    bedrooms: int | None
    bathrooms: float | None
    lat: float
    lon: float
    property_type: str
    scraped_at: str           # ISO-8601
    
    # US-specific optional fields
    hoa_fees_monthly_usd_cents: int | None
    lot_size_sqft: float | None
    lot_size_m2: float | None
    tax_assessed_value_usd_cents: int | None
    school_rating: float | None       # 0–10 normalised
    zestimate_usd_cents: int | None   # Zillow only
    compete_score: int | None         # Redfin only (0–100)
    mls_id: str | None                # Realtor.com only
    tax_history: list[dict] | None    # [{year, amount_usd_cents}]
```

---

## 7. Migrations

One Alembic migration file required:

**`services/pipeline/alembic/versions/026_add_us_listing_fields.py`**

Adds the 8 new nullable columns to `listings` and the 3 new columns to `model_versions`. Reversible (`upgrade` / `downgrade`). No data backfill needed (all nullable).
