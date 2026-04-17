# Research: Enrichment & Change Detection Services

**Feature**: 013-enrichment-change-detection
**Phase**: 0 — Research & Decision Log
**Date**: 2026-04-17

---

## 1. Catastro INSPIRE WFS Integration

**Decision**: Use the Catastro INSPIRE WFS `GetFeature` endpoint with a bounding-box filter derived from the listing's geocoordinate.

**Rationale**:
- The Spanish Catastro publishes building footprints and cadastral data via an open INSPIRE-compliant WFS service (`http://ovc.catastro.meh.es/INSPIRE/wfsCP.aspx`).
- Querying by bounding box (`BBOX` filter with a ~30m radius around the listing point) returns all cadastral parcels intersecting that box. The closest parcel by centroid is chosen.
- The WFS returns GML 3.2. Python's `lxml` or `xml.etree.ElementTree` is sufficient for parsing; no heavyweight GIS library is needed for the extraction step.
- Rate limit: the service is documented to tolerate ~1 req/s for automated clients. An `asyncio.Semaphore(1)` combined with a `asyncio.sleep(1)` after each release enforces this.
- Authentication: none required; the endpoint is openly accessible.

**Alternatives considered**:
- Catastro REST API (OVCServicio): less structured output, not INSPIRE-compliant.
- Pre-downloading all cadastral data for Spain: ~40 GB file, impractical for initial rollout.

**GML fields mapped**:
| GML element | DB column |
|---|---|
| `cp:CadastralParcel/cp:inspireId/base:localId` | `cadastral_ref` |
| `cp:CadastralParcel/cp:areaValue` | `official_built_area_m2` |
| `bu-core2d:Building/bu-base:dateOfConstruction/bu-base:yearOfConstruction` | `year_built` (overrides portal value only if null) |
| `cp:CadastralParcel/cp:geometry` | `building_geometry_wkt` (GML → WKT via `shapely`) |

---

## 2. POI Data: Pre-loaded PostGIS vs. Overpass API

**Decision**: Primary path — pre-loaded PostGIS `pois` table populated from OpenStreetMap PBF extracts. Fallback — Overpass API with an in-memory `dict` cache keyed by `(zone_id, category)`.

**Rationale**:
- Querying PostGIS with `ST_DWithin` + `ST_Distance` on an indexed spatial column is O(log n) and returns results in <10 ms for typical listing volumes.
- The Overpass API has documented rate limits (~1 req/2s) and 30s timeout; using it as primary for millions of listings would be impractical.
- OSM `amenity=subway_entrance` / `railway=station` / `aeroway=aerodrome` / `leisure=park` / `natural=beach` covers all required categories.
- PBF extracts for Spain (~1.5 GB) can be loaded with `pyosmium` (the `osmium` Python binding) into PostGIS. This is an out-of-band pre-load job, not part of this feature's runtime.

**Overpass fallback cache**: 5-second TTL using `cachetools.TTLCache` per zone (zone_id from the listing). Cache miss → Overpass query → store result. Prevents duplicate calls for listings in the same zone during a batch run.

**Alternatives considered**:
- `geopy` Nominatim for POI lookup: does not support category-filtered nearest-neighbour queries.
- Google Places API: paid; rate limits prohibitive at scale; not open-source aligned.

**PostGIS `pois` table schema**:
```sql
CREATE TABLE pois (
    id          BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    osm_id      BIGINT,
    country     CHAR(2)     NOT NULL,
    category    TEXT        NOT NULL,  -- metro, train, airport, park, beach
    name        TEXT,
    location    geometry(POINT, 4326) NOT NULL
);
CREATE INDEX pois_location_gist ON pois USING GIST (location);
CREATE INDEX pois_country_category ON pois (country, category);
```

**Distance calculation**: `ST_Distance(listing.location::geography, poi.location::geography)` returns metres directly using PostGIS geography type — no separate Haversine implementation needed.

---

## 3. Change Detection Trigger Mechanism

**Decision**: Subscribe to `scraper.cycle.completed.{country}.{portal}` NATS subject. Parse `ScrapeCycleEvent` containing `cycle_id`, `portal`, `country`, `completed_at`. Use `completed_at` as the boundary timestamp: listings for that source with `last_seen_at >= completed_at - cycle_window` are "in scope" for the current cycle.

**Rationale**:
- The scrape orchestrator already publishes a cycle-complete event (confirmed in `services/scrape-orchestrator/` source). It is the authoritative signal that a full portal pass is done and change detection can safely run.
- Using `last_seen_at` as the membership test is idempotent: re-running the detector for the same `completed_at` produces the same result because DB updates are idempotent (upsert semantics) and NATS events carry deduplication keys.
- `cycle_window` defaults to 2× the portal's configured scrape interval to tolerate slow spiders.

**Fallback**: If no cycle event arrives within `2 × scrape_interval`, the change detector runs on a timer querying for listings where `last_seen_at < NOW() - interval` — this prevents stale delistings from being missed if the orchestrator event is lost.

**Alternatives considered**:
- Polling DB on a cron: not event-driven; adds unnecessary load and latency.
- Consuming from the `normalized.listings.*` stream and tracking seen IDs per cycle: complex state management; does not handle delistings reliably since unlisted items produce no messages.

---

## 4. Price Drop Event Payload

**Decision**: `PriceChangeEvent` published to `listings.price-change.{country}`:

```json
{
  "listing_id": "uuid",
  "country": "ES",
  "portal": "idealista",
  "old_price": 300000.00,
  "new_price": 290000.00,
  "currency": "EUR",
  "old_price_eur": 300000.00,
  "new_price_eur": 290000.00,
  "drop_percentage": 3.33,
  "recorded_at": "2026-04-17T10:00:00Z"
}
```

**Rationale**:
- The alert engine consumes `listings.price-change.>` (stream `price-changes`, retention 90 days). It needs both original currency and EUR-normalised values for multi-currency user alerts.
- `drop_percentage` is pre-computed as `(old - new) / old * 100` to simplify downstream alert threshold checks.
- Only price drops (new < old) produce events. Price increases update the DB but do not publish events (not a current alerting use case).

---

## 5. DB Schema Additions

**New columns on `listings` table** (via new Alembic migration `015_enrichment.py`):

| Column | Type | Description |
|---|---|---|
| `cadastral_ref` | `VARCHAR(30)` | Catastro reference code |
| `official_built_area_m2` | `NUMERIC(10,2)` | Official area from Catastro |
| `area_discrepancy_flag` | `BOOLEAN` | True if portal area differs >10% from official |
| `building_geometry_wkt` | `TEXT` | Building footprint polygon in WKT |
| `enrichment_status` | `VARCHAR(20)` | `pending` / `completed` / `partial` / `failed` |
| `enrichment_attempted_at` | `TIMESTAMPTZ` | When enrichment was last run |
| `dist_metro_m` | `INTEGER` | Distance in metres to nearest metro station |
| `dist_train_m` | `INTEGER` | Distance in metres to nearest train station |
| `dist_airport_m` | `INTEGER` | Distance in metres to nearest airport |
| `dist_park_m` | `INTEGER` | Distance in metres to nearest park |
| `dist_beach_m` | `INTEGER` | Distance in metres to nearest beach |

**New table** `pois` (see section 2 above for DDL).

---

## 6. Enricher Plugin Registry Pattern

**Decision**: Use a module-level `dict[str, list[type[BaseEnricher]]]` populated at import time, with a `@register_enricher(country)` class decorator.

```python
_REGISTRY: dict[str, list[type[BaseEnricher]]] = {}

def register_enricher(country: str):
    def decorator(cls):
        _REGISTRY.setdefault(country, []).append(cls)
        return cls
    return decorator

@register_enricher("ES")
class SpainCatastroEnricher(BaseEnricher): ...
```

**Rationale**:
- Explicit and inspectable — no metaclass magic.
- Zero runtime overhead vs. dynamic discovery.
- Adding a new country enricher requires no changes to core code, only a new module with the decorator.

---

## 7. Testing Strategy

**Unit tests**:
- `test_catastro_enricher.py` — mock `httpx.AsyncClient`, assert GML parsing correctness and area discrepancy logic.
- `test_poi_calculator.py` — mock asyncpg cursor, assert distance result for known coordinates.
- `test_change_detector.py` — mock DB query results, assert price-history rows and NATS events for each scenario.

**Integration tests** (testcontainers PostgreSQL + NATS):
- `test_enricher_integration.py` — seed listing, seed POIs, run enricher, assert DB state.
- `test_change_detector_integration.py` — seed listings, simulate cycle event, assert price_history + delisted_at updates.

**Note**: Catastro WFS calls are always mocked in tests (external API). A separate manual acceptance test document (`quickstart.md`) covers live verification against 10 real Madrid listings.

---

## 8. Deployment: New Helm Service Entries

Two new Kubernetes Deployments needed under `services.pipeline` namespace (estategap-pipeline):

- **enricher**: consumes `listings.deduplicated.*`, publishes `listings.enriched.*`
- **change-detector**: consumes `scraper.cycle.completed.*`, publishes `listings.price-change.*`

Both reuse the same Docker image as the pipeline service (same repo, different `python -m` command) with Kubernetes `command` override. This follows the existing normalizer/deduplicator pattern.
