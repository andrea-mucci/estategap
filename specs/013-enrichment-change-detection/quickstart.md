# Quickstart: Enrichment & Change Detection Services

**Feature**: 013-enrichment-change-detection
**Date**: 2026-04-17

---

## Prerequisites

- PostgreSQL 16 + PostGIS 3.4 running locally (or via testcontainers)
- NATS JetStream running locally (`nats-server -js`)
- `uv` installed
- Python 3.12+
- A Spanish listing record in the `listings` table with a valid `location` geometry

---

## 1. Run Alembic Migration

```bash
cd services/pipeline
uv run alembic upgrade head
```

This applies migration `015_enrichment.py` which adds the enrichment columns and creates the `pois` table.

---

## 2. Pre-load POI Data (Spain)

```bash
# Download Spain OSM PBF extract (Geofabrik)
curl -O https://download.geofabrik.de/europe/spain-latest.osm.pbf

# Load POIs into PostGIS
cd services/pipeline
uv run python -m pipeline.enricher.poi_loader \
    --pbf spain-latest.osm.pbf \
    --country ES \
    --database-url "$DATABASE_URL"
```

The loader uses `pyosmium` to stream the PBF file and inserts `amenity=subway_entrance`, `railway=station`, `aeroway=aerodrome`, `leisure=park`, `natural=beach` features into the `pois` table.

---

## 3. Run the Enricher Service

```bash
cd services/pipeline
DATABASE_URL=postgresql://... NATS_URL=nats://localhost:4222 \
uv run python -m pipeline.enricher
```

The service:
1. Connects to NATS and subscribes to `listings.deduplicated.>` (durable `enricher`)
2. Connects to PostgreSQL via asyncpg pool
3. For each message: runs `SpainCatastroEnricher` + `POIDistanceCalculator`
4. Updates the listing record in DB
5. Publishes to `listings.enriched.{country}`

---

## 4. Run the Change Detector Service

```bash
cd services/pipeline
DATABASE_URL=postgresql://... NATS_URL=nats://localhost:4222 \
uv run python -m pipeline.change_detector
```

The service:
1. Subscribes to `scraper.cycle.completed.>` (durable `change-detector`)
2. On each event: queries active listings for the portal/country
3. Compares against cycle snapshot
4. Writes `price_history` rows, updates listing status
5. Publishes `PriceChangeEvent` to `listings.price-change.{country}`

---

## 5. Manual Acceptance Test: Catastro Enrichment

To verify against real Catastro data:

```bash
# Insert a real Madrid listing (Calle Gran Vía 28, 28013 Madrid)
# coordinates: 40.4200, -3.7048
cd services/pipeline
uv run python -m pipeline.enricher.test_acceptance \
    --lat 40.4200 --lon -3.7048 \
    --portal-area 120.0
```

Expected output:
```
cadastral_ref: 3665603VK4736D0001UY
official_built_area_m2: 118.5
area_discrepancy_flag: false  (|120.0 - 118.5| / 118.5 = 1.3% < 10%)
year_built: 1952
```

Repeat for 10 sample listings in Madrid and verify POI distances against Google Maps.

---

## 6. Manual Acceptance Test: Price Drop Detection

```bash
# Seed a listing at €300,000
# Simulate a scrape cycle where the listing appears at €290,000
# Publish a cycle.completed event
cd services/pipeline
uv run python -m pipeline.change_detector.test_acceptance \
    --portal idealista --country ES \
    --listing-id <uuid> \
    --old-price 300000 --new-price 290000
```

Verify:
```sql
SELECT * FROM price_history WHERE listing_id = '<uuid>';
-- Should show: old_price=300000, new_price=290000, drop=10000

SELECT asking_price FROM listings WHERE id = '<uuid>';
-- Should show: 290000
```

Check NATS:
```bash
nats sub "listings.price-change.es"
# Should receive PriceChangeEvent with drop_percentage=3.33
```

---

## 7. Run Tests

```bash
cd services/pipeline

# Unit tests only (no external services needed)
uv run pytest tests/unit/ -v

# Integration tests (requires Docker for testcontainers)
uv run pytest tests/integration/ -v -m "enricher or change_detector"
```
