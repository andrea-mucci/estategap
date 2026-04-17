# Quickstart: Normalize & Deduplicate Pipeline

**Feature**: 012-normalize-dedup-pipeline | **Date**: 2026-04-17

## Prerequisites

- Python 3.12 + `uv`
- PostgreSQL 16 + PostGIS 3.4 running locally (or via docker-compose)
- NATS server with JetStream enabled running locally
- `services/pipeline/` dependencies installed

## Install Dependencies

```bash
cd services/pipeline
uv sync
```

New dependencies added for this feature: `asyncpg`, `nats-py`, `rapidfuzz`, `pyyaml`,
`pydantic-settings`, `structlog`, `prometheus-client`.

## Run Database Migration

```bash
cd services/pipeline
uv run alembic upgrade head
```

This applies migration `014_pipeline_quarantine.py`:
- Creates the `quarantine` table
- Adds `data_completeness` column to `listings`

## Environment Variables

Both services share these environment variables (set via `.env` or Kubernetes Secret):

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/estategap

# NATS
NATS_URL=nats://localhost:4222

# Normalizer-specific
NORMALIZER_BATCH_SIZE=50           # messages per DB flush (default: 50)
NORMALIZER_BATCH_TIMEOUT=1.0       # seconds to wait before flushing partial batch
NORMALIZER_MAPPINGS_DIR=config/mappings   # path to portal mapping YAML files
NORMALIZER_METRICS_PORT=9101

# Deduplicator-specific
DEDUPLICATOR_PROXIMITY_METERS=50   # PostGIS search radius
DEDUPLICATOR_AREA_TOLERANCE=0.10   # ±10% area difference threshold
DEDUPLICATOR_ADDRESS_THRESHOLD=85  # rapidfuzz ratio threshold
DEDUPLICATOR_METRICS_PORT=9102
```

## Run the Normalizer

```bash
cd services/pipeline
uv run python -m pipeline.normalizer
```

The normalizer subscribes to `raw.listings.*`, processes messages in batches of 50, and
publishes to `normalized.listings.*`.

## Run the Deduplicator

```bash
cd services/pipeline
uv run python -m pipeline.deduplicator
```

The deduplicator subscribes to `normalized.listings.*`, runs three-stage matching, updates
`canonical_id`, and publishes to `deduplicated.listings.*`.

## Run Tests

```bash
cd services/pipeline

# Unit tests (no infrastructure required)
uv run pytest tests/unit/ -v

# Integration tests (requires Docker for testcontainers)
uv run pytest tests/integration/ -v
```

Integration tests spin up a real PostgreSQL + PostGIS container and a NATS test server
automatically via testcontainers.

## Publish a Test Raw Listing

```bash
# Requires NATS CLI (brew install nats-io/nats-tools/nats)
nats pub raw.listings.es '{
  "external_id": "test-123",
  "portal": "idealista",
  "country_code": "ES",
  "raw_json": {
    "precio": 250000,
    "tipologia": "piso",
    "superficie": 80,
    "habitaciones": 3,
    "banos": 2,
    "latitud": 40.4168,
    "longitud": -3.7038,
    "url": "https://www.idealista.com/inmueble/test-123/",
    "municipio": "Madrid",
    "provincia": "Madrid",
    "codigoPostal": "28001"
  },
  "scraped_at": "2026-04-17T10:00:00Z"
}'
```

Expected outcome: a row appears in `listings` with `source='idealista'`, `source_id='test-123'`,
`asking_price_eur=250000`, `built_area_m2=80`, `city='Madrid'`, `data_completeness` > 0.

## Verify Deduplication

```bash
# Publish the same listing from Fotocasa
nats pub raw.listings.es '{
  "external_id": "foto-456",
  "portal": "fotocasa",
  "country_code": "ES",
  "raw_json": {
    "price": 252000,
    "propertyTypeId": 1,
    "surface": 80,
    "rooms": 3,
    "bathrooms": 2,
    "latitude": 40.41685,
    "longitude": -3.70378,
    "detailUrl": "https://www.fotocasa.es/es/alquiler/piso/foto-456",
    "city": "Madrid",
    "province": "Madrid",
    "postalCode": "28001",
    "address": "Calle Mayor 5"
  },
  "scraped_at": "2026-04-17T10:01:00Z"
}'

# Query after processing
psql $DATABASE_URL -c "
  SELECT source, source_id, canonical_id
  FROM listings
  WHERE source IN ('idealista', 'fotocasa')
  ORDER BY created_at;
"
```

Expected: both rows have the same `canonical_id` (equal to the Idealista listing's `id`).

## Prometheus Metrics

Both services expose metrics on their configured ports:

```
# Normalizer (port 9101)
pipeline_messages_processed_total{service="normalizer", portal="idealista", country="ES"} 1042
pipeline_messages_quarantined_total{service="normalizer", portal="idealista", reason="invalid_price"} 3
pipeline_batch_duration_seconds{service="normalizer"} histogram

# Deduplicator (port 9102)
pipeline_messages_processed_total{service="deduplicator", portal="idealista", country="ES"} 1042
pipeline_batch_duration_seconds{service="deduplicator"} histogram
```

## Adding a New Portal Mapping

1. Create `services/pipeline/config/mappings/<country>_<portal>.yaml`
2. Follow the schema in `specs/012-normalize-dedup-pipeline/contracts/portal-mapping-schema.md`
3. Restart the normalizer — it loads all YAML files at startup

No code changes required.
