# Quickstart: EU Portals & Enrichment

**Feature**: 025-eu-portals-enrichment  
**Date**: 2026-04-17

---

## Prerequisites

```bash
# Python environment (spider-workers service)
cd services/spider-workers
uv sync

# Python environment (pipeline service)
cd services/pipeline
uv sync

# PostgreSQL with PostGIS running
# Redis running
# NATS JetStream running
```

---

## 1. Run Database Migrations

```bash
cd services/pipeline
uv run alembic upgrade head
```

This applies migrations for:
- `025_eu_listing_fields` — new fields on listings table
- `025_dvf_transactions` — France DVF table
- `026_uk_price_paid` — UK Land Registry table
- `027_omi_zones` — Italy OMI zone price bands

---

## 2. Import Zone Hierarchies

Download GADM GeoPackages from gadm.org and place in `/data/gadm/`:

```bash
# Import zones for all 4 new countries
uv run python scripts/import_gadm_zones.py --country IT --file /data/gadm/gadm41_ITA.gpkg
uv run python scripts/import_gadm_zones.py --country FR --file /data/gadm/gadm41_FRA.gpkg
uv run python scripts/import_gadm_zones.py --country GB --file /data/gadm/gadm41_GBR.gpkg
uv run python scripts/import_gadm_zones.py --country NL --file /data/gadm/gadm41_NLD.gpkg
```

Verify via API:
```bash
curl "http://localhost:8080/zones?country=FR&level=1"
# Should return 13 French metropolitan regions
```

---

## 3. Import Enrichment Reference Data (one-time bulk loads)

### France DVF
```bash
# Downloads ~2GB CSV from data.gouv.fr, geocodes, and imports
uv run python scripts/import_dvf.py --year-from 2020 --year-to 2024
# Full import (2014–2024) takes ~3 hours
uv run python scripts/import_dvf.py --year-from 2014 --year-to 2024
```

### UK Land Registry
```bash
# Downloads complete CSV from gov.uk (~5GB), imports to uk_price_paid
uv run python scripts/import_uk_land_registry.py --complete
# Incremental monthly update:
uv run python scripts/import_uk_land_registry.py --monthly 2026-03
```

### Italy OMI
```bash
# Downloads and parses OMI semi-annual data from Agenzia delle Entrate
uv run python scripts/import_omi.py --period 2024-H2
```

---

## 4. Run a Spider

```bash
cd services/spider-workers

# Test Immobiliare.it spider for Rome
uv run python -m estategap_spiders.cli scrape --country IT --portal immobiliare --zone roma --pages 5

# Test Rightmove for London
uv run python -m estategap_spiders.cli scrape --country GB --portal rightmove --zone london --pages 5

# Test Funda for Amsterdam (rate-limited: ~2s/request)
uv run python -m estategap_spiders.cli scrape --country NL --portal funda --zone amsterdam --pages 3
```

---

## 5. Test Enrichers

```bash
cd services/pipeline

# Test France DVF enricher against a Paris listing (by listing ID)
uv run python -m pipeline.cli enrich --listing-id <uuid> --country FR

# Test UK Land Registry enricher
uv run python -m pipeline.cli enrich --listing-id <uuid> --country GB

# Test Italy OMI enricher
uv run python -m pipeline.cli enrich --listing-id <uuid> --country IT

# Test Netherlands BAG enricher
uv run python -m pipeline.cli enrich --listing-id <uuid> --country NL
```

---

## 6. Run Tests

```bash
# Spider worker tests
cd services/spider-workers
uv run pytest tests/ -v -k "it_ or fr_ or gb_ or nl_"

# Pipeline enricher tests
cd services/pipeline
uv run pytest tests/enricher/ -v -k "dvf or land_registry or omi or bag"

# Integration tests (requires testcontainers Docker)
uv run pytest tests/integration/ -v --country IT
uv run pytest tests/integration/ -v --country FR
uv run pytest tests/integration/ -v --country GB
uv run pytest tests/integration/ -v --country NL
```

---

## 7. Playwright Setup (SeLoger & LeBonCoin)

SeLoger and LeBonCoin spiders require Playwright with Chromium:

```bash
cd services/spider-workers
uv run playwright install chromium
uv run playwright install-deps chromium
```

Verify Playwright works:
```bash
uv run python -m estategap_spiders.cli scrape --country FR --portal seloger --zone paris --pages 1 --debug
```

---

## Environment Variables

```bash
# Spider worker config (add to .env or Kubernetes Sealed Secret)
IMMOBILIARE_API_TOKEN=...     # Immobiliare.it partner API token (optional; falls back to HTML)
IDEALISTA_IT_API_TOKEN=...    # Separate from ES token

# Proxy manager (existing)
PROXY_MANAGER_ADDR=localhost:50051

# Database (existing)
DATABASE_URL=postgresql://user:pass@localhost:5432/estategap

# Redis (existing)
REDIS_URL=redis://localhost:6379/0
```

---

## Acceptance Criteria Verification

```bash
# Check completeness ≥75% per portal (run after scraping 1000+ listings)
uv run python scripts/check_completeness.py --country IT --portal immobiliare
uv run python scripts/check_completeness.py --country FR --portal seloger
uv run python scripts/check_completeness.py --country GB --portal rightmove
uv run python scripts/check_completeness.py --country NL --portal funda

# Check DVF enrichment rate for Paris
uv run python scripts/check_enrichment_rate.py --country FR --city paris --enricher dvf
# Expected: ≥60%

# Check UK Land Registry match rate for London
uv run python scripts/check_enrichment_rate.py --country GB --city london --enricher land_registry
# Expected: ≥70%
```
