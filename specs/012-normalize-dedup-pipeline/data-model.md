# Data Model: Normalize & Deduplicate Pipeline

**Phase**: 1 | **Feature**: 012-normalize-dedup-pipeline | **Date**: 2026-04-17

## Existing Entities (consumed, not redefined)

### RawListing (`libs/common/estategap_common/models/listing.py`)

Input payload from NATS `raw.listings.*`. Key fields:

| Field | Type | Notes |
|-------|------|-------|
| `external_id` | str | Portal's own listing identifier |
| `portal` | str | Portal slug (e.g., `idealista`, `fotocasa`) |
| `country_code` | str | ISO 3166-1 alpha-2 (validated) |
| `raw_json` | dict | Full portal-specific payload |
| `scraped_at` | AwareDatetime | UTC timestamp |

### NormalizedListing (`libs/common/estategap_common/models/listing.py`)

Pydantic model used for validation before DB write. Key constraints:

| Field | Required | Notes |
|-------|----------|-------|
| `id` | yes | Generated UUID |
| `country` | yes | Validated ISO-3166 |
| `source` | yes | Portal slug |
| `source_id` | yes | Portal's listing ID |
| `source_url` | yes | Canonical URL |
| `asking_price` | yes | Must be > 0 |
| `currency` | yes | Validated 3-char currency code |
| `asking_price_eur` | yes | Converted from `asking_price` |
| `built_area_m2` | yes | Must be > 0 |
| `location_wkt` | no | `POINT(lon lat)` WKT if GPS available |

Validation rules enforced by Pydantic:
- `asking_price > 0` and `built_area_m2 > 0` (field validators)
- `country` must be valid ISO-3166 (via `validate_country_code`)
- `currency` must be valid ISO-4217 (via `validate_currency_code`)

### ExchangeRate (`services/pipeline/src/pipeline/db/models.py`)

Read-only by normalizer.

| Field | Type | Notes |
|-------|------|-------|
| `currency` | CHAR(3) | Primary key |
| `date` | Date | Primary key — most recent date used as fallback |
| `rate_to_eur` | NUMERIC(12,6) | Multiply source price by this to get EUR |
| `fetched_at` | TIMESTAMPTZ | When ECB rate was fetched |

---

## New Entities

### Quarantine (new table: `quarantine`)

Persists rejected listings with full context for replay/debug.

| Column | Type | Notes |
|--------|------|-------|
| `id` | BIGINT IDENTITY | Primary key |
| `source` | VARCHAR(30) | Portal slug (e.g., `idealista`) |
| `source_id` | VARCHAR(80) | Portal's listing ID (may be null if not parsed) |
| `country` | CHAR(2) | Country code (may be null if not parsed) |
| `portal` | VARCHAR(30) | Same as source (redundant for query convenience) |
| `reason` | VARCHAR(50) | Reject reason: `invalid_price`, `missing_location`, `no_mapping_config`, `validation_error`, `invalid_json` |
| `error_detail` | TEXT | Pydantic error string or exception message |
| `raw_payload` | JSONB | Full `raw_json` from the NATS message for replay |
| `quarantined_at` | TIMESTAMPTZ | DEFAULT NOW() |

**Index**: `(source, country, quarantined_at DESC)` for ops dashboards.

**Partitioning**: Not partitioned — quarantine volume is much smaller than listings and
queries are primarily by date range for operational review.

---

### PortalMapping (in-memory, loaded from YAML at startup)

Not persisted. Loaded once per portal at service startup.

```python
@dataclass
class FieldMapping:
    target: str                  # unified field name
    transform: str | None        # name of transform function, or None

@dataclass
class PortalMapping:
    portal: str
    country: str
    fields: dict[str, FieldMapping]       # source_field → FieldMapping
    property_type_map: dict[str, str]     # portal_type → canonical type
    currency_field: str                   # which source field holds the currency code
    area_unit_field: str | None           # which source field holds the area unit
```

---

## Modified Entities

### listings (existing table, migration 014)

Two additive changes:

| Column | Type | Default | Notes |
|--------|------|---------|-------|
| `data_completeness` | NUMERIC(4,2) | NULL | Fraction of completeness fields populated; backfilled on upsert |

The `canonical_id` column already exists (`UUID`, nullable). The deduplicator writes this column
via `UPDATE listings SET canonical_id = $1 WHERE id = $2 AND country = $3`.

---

## Completeness Field List

The following fields are used to compute `data_completeness`. Score = non-null count / 26.

```python
COMPLETENESS_FIELDS = [
    "address", "city", "region", "postal_code", "location_wkt",
    "asking_price", "asking_price_eur", "price_per_m2_eur",
    "property_category", "property_type",
    "built_area_m2", "usable_area_m2", "plot_area_m2",
    "bedrooms", "bathrooms", "floor_number", "total_floors",
    "parking_spaces", "has_lift", "has_pool",
    "year_built", "condition", "energy_rating",
    "description_orig", "images_count", "published_at",
]
```

---

## Transform Function Signatures

All transform functions are pure, synchronous, and raise `ValueError` on invalid input.

```python
def currency_convert(amount: Decimal, from_currency: str, rates: dict[str, Decimal]) -> Decimal:
    """Convert amount to EUR using rates dict {currency: rate_to_eur}."""

def area_to_m2(value: Decimal, unit: str) -> Decimal:
    """Convert area to m². Supported units: 'm2', 'sqft', 'ft2'."""
    # 1 sqft = 0.09290304 m²

def map_property_type(portal_type: str, type_map: dict[str, str]) -> str:
    """Map portal-specific type string to canonical taxonomy.
    Canonical values: residential, commercial, industrial, land."""

def map_condition(portal_condition: str, country: str) -> str:
    """Map portal condition string to canonical condition.
    Canonical values: new, good, needs_renovation."""

def pieces_to_bedrooms(pieces: int) -> int:
    """France only: pièces - 1 = bedrooms (living room counts as a pièce)."""
    return max(0, pieces - 1)
```

---

## Data Flow Diagram

```
NATS raw.listings.<country>
        │
        ▼
   Normalizer consumer
        │ batch=50
        ├─── [invalid] ──→ quarantine table
        │
        ├─── [valid]  ──→ listings table (upsert)
        │                  + data_completeness computed
        │
        ▼
NATS normalized.listings.<country>
        │
        ▼
   Deduplicator consumer
        │
        ├── Stage 1: PostGIS ST_DWithin(50m)
        ├── Stage 2: feature similarity (area ±10%, rooms, type)
        └── Stage 3: rapidfuzz address ratio > 85
                │
                ├─── [match]    → UPDATE canonical_id on both records
                └─── [no match] → SET canonical_id = own id
                        │
                        ▼
        NATS deduplicated.listings.<country>
```
