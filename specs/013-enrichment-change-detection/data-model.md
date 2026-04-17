# Data Model: Enrichment & Change Detection Services

**Feature**: 013-enrichment-change-detection
**Phase**: 1 — Design
**Date**: 2026-04-17

---

## Entities

### 1. BaseEnricher (Abstract Interface)

Location: `services/pipeline/src/pipeline/enricher/base.py`

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

from estategap_common.models.listing import NormalizedListing

EnrichmentStatus = Literal["completed", "partial", "no_match", "failed"]

@dataclass
class EnrichmentResult:
    status: EnrichmentStatus
    updates: dict[str, object]          # column name → new value for DB update
    error: str | None = None            # populated on "failed" status

class BaseEnricher(ABC):
    @abstractmethod
    async def enrich(self, listing: NormalizedListing) -> EnrichmentResult:
        """
        Attempt to enrich the listing.
        Must not raise; return EnrichmentResult with status="failed" on error.
        """
```

---

### 2. SpainCatastroEnricher

Location: `services/pipeline/src/pipeline/enricher/catastro.py`

**Input**: `NormalizedListing` with `location_wkt` set (WGS-84 POINT)

**Output** (`EnrichmentResult.updates`):

| Field | Type | Source |
|---|---|---|
| `cadastral_ref` | `str` | `cp:CadastralParcel/cp:inspireId/base:localId` |
| `official_built_area_m2` | `Decimal` | `cp:CadastralParcel/cp:areaValue` |
| `area_discrepancy_flag` | `bool` | Computed: `abs(portal_area - official_area) / official_area > 0.10` |
| `building_geometry_wkt` | `str` | `cp:CadastralParcel/cp:geometry` → Shapely WKT |
| `year_built` | `int \| None` | `bu-base:yearOfConstruction` (only if listing.year_built is None) |
| `enrichment_status` | `str` | `"completed"` or `"no_match"` or `"failed"` |
| `enrichment_attempted_at` | `datetime` | `datetime.utcnow()` |

**Rate limiter**: `asyncio.Semaphore(1)` + `asyncio.sleep(1.0)` after each request.

**GML Namespace map**:
```python
NS = {
    "cp": "http://inspire.jrc.ec.europa.eu/schemas/cp/4.0",
    "base": "http://inspire.jrc.ec.europa.eu/schemas/base/3.3",
    "bu-core2d": "http://inspire.jrc.ec.europa.eu/schemas/bu-core2d/4.0",
    "bu-base": "http://inspire.jrc.ec.europa.eu/schemas/bu-base/4.0",
    "gml": "http://www.opengis.net/gml/3.2",
}
```

---

### 3. POIDistanceCalculator

Location: `services/pipeline/src/pipeline/enricher/poi.py`

**Input**: listing `location_wkt`, `country` code, asyncpg connection pool.

**Output** (`EnrichmentResult.updates`):

| Field | Type | Description |
|---|---|---|
| `dist_metro_m` | `int \| None` | Metres to nearest `amenity=subway_entrance` or `railway=subway_station` |
| `dist_train_m` | `int \| None` | Metres to nearest `railway=station` |
| `dist_airport_m` | `int \| None` | Metres to nearest `aeroway=aerodrome` |
| `dist_park_m` | `int \| None` | Metres to nearest `leisure=park` |
| `dist_beach_m` | `int \| None` | Metres to nearest `natural=beach` |

**PostGIS query pattern**:
```sql
SELECT
    ST_Distance(
        ST_GeographyFromText($1),
        location::geography
    )::int AS dist_m
FROM pois
WHERE country = $2
  AND category = $3
ORDER BY location <-> ST_GeographyFromText($1)
LIMIT 1;
```

**Fallback** (Overpass API):
- Endpoint: `https://overpass-api.de/api/interpreter`
- Query: `[out:json]; node[{tag}](around:5000,{lat},{lon}); out 1;`
- Cache: `cachetools.TTLCache(maxsize=1024, ttl=300)` keyed by `(lat_rounded, lon_rounded, category)`

---

### 4. EnricherService (Orchestrator)

Location: `services/pipeline/src/pipeline/enricher/service.py`

**Responsibilities**:
1. Consume `listings.deduplicated.{country}` from NATS (durable consumer: `enricher`).
2. For each message, load the `NormalizedListing`.
3. Look up registry: `REGISTRY.get(country, [])` → list of enricher instances.
4. Run all enrichers concurrently per listing (using `asyncio.gather`).
5. Merge `EnrichmentResult.updates` from all enrichers (later enrichers win on conflict, POI always last).
6. Run `POIDistanceCalculator`.
7. Write merged updates to DB via asyncpg UPDATE.
8. Publish enriched listing to `listings.enriched.{country}`.
9. Ack the NATS message.

---

### 5. ChangeDetector

Location: `services/pipeline/src/pipeline/change_detector/detector.py`

**Trigger**: NATS subject `scraper.cycle.completed.{country}.{portal}`

**ScrapeCycleEvent** (Pydantic model):
```python
class ScrapeCycleEvent(EstateGapModel):
    cycle_id: str
    portal: str
    country: str
    completed_at: datetime
    listing_ids: list[str] = []   # UUIDs of listings seen in this cycle; may be empty
```

**Detection algorithm**:

```
cycle_listing_ids = event.listing_ids
                    OR
                    SELECT id FROM listings
                    WHERE source = portal
                      AND country = country
                      AND last_seen_at >= completed_at - cycle_window
                      AND last_seen_at <= completed_at

active_listings = SELECT id, asking_price, currency, asking_price_eur, status
                  FROM listings
                  WHERE source = portal
                    AND country = country
                    AND status = 'active'

For each listing in active_listings:
    if listing.id NOT IN cycle_listing_ids:
        → DELIST: UPDATE status='delisted', delisted_at=NOW()

For each listing_id in cycle_listing_ids:
    current = active_listings[listing_id]
    scraped = fetch new price from DB (last_seen_at = completed_at row)
    if current.asking_price != scraped.asking_price:
        → PRICE CHANGE: INSERT price_history, UPDATE asking_price
        if new_price < old_price:
            → PUBLISH PriceChangeEvent

For each listing in cycle_listing_ids where status = 'delisted':
    → RELIST: UPDATE status='active', delisted_at=NULL
```

---

### 6. PriceChangeEvent (NATS Message)

Location: `libs/common/estategap_common/models/listing.py` (extend existing `PriceChange`)

```python
class PriceChangeEvent(EstateGapModel):
    listing_id: UUID
    country: str                      # ISO 3166-1 alpha-2
    portal: str
    old_price: Decimal
    new_price: Decimal
    currency: str                     # ISO 4217
    old_price_eur: Decimal | None
    new_price_eur: Decimal | None
    drop_percentage: Decimal          # (old - new) / old * 100; positive = drop
    recorded_at: datetime
```

Published to: `listings.price-change.{country_lower}`

---

## Database Schema Changes

### Migration: `015_enrichment.py`

**ALTER TABLE listings** — add enrichment columns (applied to parent + all partitions):

```sql
ALTER TABLE listings
    ADD COLUMN IF NOT EXISTS cadastral_ref            VARCHAR(30),
    ADD COLUMN IF NOT EXISTS official_built_area_m2   NUMERIC(10,2),
    ADD COLUMN IF NOT EXISTS area_discrepancy_flag     BOOLEAN,
    ADD COLUMN IF NOT EXISTS building_geometry_wkt    TEXT,
    ADD COLUMN IF NOT EXISTS enrichment_status         VARCHAR(20)  DEFAULT 'pending',
    ADD COLUMN IF NOT EXISTS enrichment_attempted_at   TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS dist_metro_m              INTEGER,
    ADD COLUMN IF NOT EXISTS dist_train_m              INTEGER,
    ADD COLUMN IF NOT EXISTS dist_airport_m            INTEGER,
    ADD COLUMN IF NOT EXISTS dist_park_m               INTEGER,
    ADD COLUMN IF NOT EXISTS dist_beach_m              INTEGER;

CREATE INDEX IF NOT EXISTS listings_enrichment_status
    ON listings (country, enrichment_status)
    WHERE enrichment_status = 'pending';
```

**CREATE TABLE pois**:

```sql
CREATE TABLE IF NOT EXISTS pois (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    osm_id      BIGINT,
    country     CHAR(2)                      NOT NULL,
    category    VARCHAR(20)                  NOT NULL,
    name        TEXT,
    location    geometry(POINT, 4326)        NOT NULL,
    created_at  TIMESTAMPTZ                  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS pois_location_gist
    ON pois USING GIST (location);

CREATE INDEX IF NOT EXISTS pois_country_category
    ON pois (country, category);
```

---

## State Transitions

### Listing Enrichment Status

```
pending → completed   (all enrichers succeeded)
pending → partial     (some enrichers succeeded, some failed or no_match)
pending → failed      (all enrichers failed after retries)
completed → pending   (re-enrichment triggered, e.g., after new enricher added)
```

### Listing Status (change detector)

```
active → delisted     (not seen in latest scrape cycle)
delisted → active     (reappears in latest scrape cycle)
active → active       (seen in cycle; price may have changed — status unchanged)
```

---

## Configuration Models

### EnricherSettings (pydantic-settings)

```python
class EnricherSettings(BaseSettings):
    database_url:          str       # DATABASE_URL
    nats_url:              str       # NATS_URL
    catastro_rate_limit:   float = 1.0   # ENRICHER_CATASTRO_RATE_LIMIT (req/s)
    overpass_url:          str = "https://overpass-api.de/api/interpreter"
    overpass_cache_ttl:    int = 300     # ENRICHER_OVERPASS_CACHE_TTL seconds
    metrics_port:          int = 9103   # ENRICHER_METRICS_PORT
    log_level:             str = "INFO"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```

### ChangeDetectorSettings (pydantic-settings)

```python
class ChangeDetectorSettings(BaseSettings):
    database_url:        str       # DATABASE_URL
    nats_url:            str       # NATS_URL
    cycle_window_hours:  int = 6   # CHANGE_DETECTOR_CYCLE_WINDOW_HOURS
    fallback_interval_h: int = 12  # CHANGE_DETECTOR_FALLBACK_INTERVAL_HOURS
    metrics_port:        int = 9104  # CHANGE_DETECTOR_METRICS_PORT
    log_level:           str = "INFO"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
```
