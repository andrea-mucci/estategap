# Implementation Plan: Enrichment & Change Detection Services

**Branch**: `013-enrichment-change-detection` | **Date**: 2026-04-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/013-enrichment-change-detection/spec.md`

## Summary

Add two Python services to the pipeline — an **Enricher** that attaches Catastro cadastral data and OpenStreetMap POI distances to deduplicated listings, and a **Change Detector** that compares portal scrape snapshots against DB state to detect price drops, delistings, and re-listings.

Both services are packaged inside `services/pipeline` (same repo/image as the normalizer and deduplicator, deployed with different Kubernetes `command` overrides). A new Alembic migration adds enrichment columns to `listings` and creates the `pois` table.

## Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: nats-py 2.6+, asyncpg 0.29+, httpx 0.27+, lxml 5.x (GML parsing), shapely 2.x (WKT conversion), pyosmium 3.7+ (OSM PBF loading), cachetools 5.x (Overpass TTL cache), pydantic-settings 2.2+, pydantic v2, structlog 24.x, prometheus-client 0.20+, estategap-common (shared models)  
**Storage**: PostgreSQL 16 + PostGIS 3.4 (`listings` partitioned table + new `pois` table); NATS JetStream (existing streams)  
**Testing**: pytest + pytest-asyncio, testcontainers (PostgreSQL + NATS), unittest.mock for external API mocking  
**Target Platform**: Linux container (Kubernetes, estategap-pipeline namespace)  
**Project Type**: Async Python microservices (NATS consumers)  
**Performance Goals**: Enrich 1,000 Madrid listings/hour sustained; change detection for 10,000 active listings in <30s per cycle  
**Constraints**: Catastro API ≤1 req/s; Overpass API ≤1 req/2s; enrichment must be idempotent  
**Scale/Scope**: Spain initial rollout; architecture supports adding FR, IT, PT enrichers via plugin registry

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Polyglot Architecture | ✅ PASS | Python services inside `services/pipeline` — correct workload profile for data pipeline |
| II. Event-Driven Communication | ✅ PASS | Both services communicate exclusively via NATS JetStream; no direct HTTP between services |
| III. Country-First Data Sovereignty | ✅ PASS | All NATS subjects include country suffix; DB queries filtered by country; EUR normalisation preserved |
| IV. ML-Powered Intelligence | ✅ PASS | Enriched fields (POI distances, cadastral area) feed downstream ML scorer; no changes to ML layer |
| V. Code Quality Discipline | ✅ PASS | Pydantic v2 models, asyncio+httpx, structlog, ruff+mypy strict, pytest+testcontainers |
| VI. Security & Ethical Scraping | ✅ PASS | Catastro rate limit enforced (1 req/s Semaphore); Overpass is publicly accessible open data |
| VII. Kubernetes-Native Deployment | ✅ PASS | New Helm service entries; same Dockerfile as pipeline; command override per Deployment |

**Post-design re-check**: All gates still pass. No constitution violations introduced.

## Project Structure

### Documentation (this feature)

```text
specs/013-enrichment-change-detection/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0: technology decisions
├── data-model.md        # Phase 1: entities, schema, configs
├── quickstart.md        # Phase 1: dev setup and manual acceptance tests
├── contracts/
│   └── nats-subjects.md # NATS subject/stream contracts
└── tasks.md             # Phase 2 output (/speckit.tasks — not yet created)
```

### Source Code

The enricher and change detector live inside the existing `services/pipeline` package, following the normalizer/deduplicator pattern:

```text
services/pipeline/
├── alembic/versions/
│   └── 015_enrichment.py          # NEW: adds enrichment cols + pois table
├── src/pipeline/
│   ├── enricher/                  # NEW package
│   │   ├── __init__.py
│   │   ├── __main__.py            # Entry: python -m pipeline.enricher
│   │   ├── config.py              # EnricherSettings (pydantic-settings)
│   │   ├── service.py             # EnricherService (NATS consumer + orchestrator)
│   │   ├── base.py                # BaseEnricher ABC + EnrichmentResult + registry
│   │   ├── catastro.py            # SpainCatastroEnricher
│   │   ├── poi.py                 # POIDistanceCalculator
│   │   └── poi_loader.py          # CLI: loads OSM PBF into pois table
│   └── change_detector/           # NEW package
│       ├── __init__.py
│       ├── __main__.py            # Entry: python -m pipeline.change_detector
│       ├── config.py              # ChangeDetectorSettings
│       ├── consumer.py            # NATS consumer for scraper.cycle.completed.*
│       └── detector.py            # Core detection logic (price/delist/relist)
├── tests/
│   ├── unit/
│   │   ├── test_catastro_enricher.py    # NEW
│   │   ├── test_poi_calculator.py       # NEW
│   │   └── test_change_detector.py      # NEW
│   └── integration/
│       ├── test_enricher_integration.py        # NEW
│       └── test_change_detector_integration.py # NEW
└── pyproject.toml                 # Add: lxml, shapely, pyosmium, cachetools
```

**Shared model changes** (`libs/common/estategap_common/models/listing.py`):
- Add `PriceChangeEvent` Pydantic model (extends existing `PriceChange`)
- Add enrichment fields to `NormalizedListing` (all Optional, default None)

**Helm changes** (`helm/estategap/values.yaml`):
- Add `services.pipeline.enricher` deployment entry
- Add `services.pipeline.change-detector` deployment entry
- Add `scraper-cycle` NATS stream for `scraper.cycle.completed.>` subjects

## Complexity Tracking

No constitution violations — table left intentionally empty.

---

## Phase 0: Research

✅ **Completed** — see [research.md](research.md)

Key decisions:
- Catastro WFS via `httpx` + `lxml` GML parsing; `shapely` for geometry WKT conversion
- PostGIS `pois` table as primary POI source; Overpass API as fallback with `cachetools.TTLCache`
- Change detection triggered by `scraper.cycle.completed.{country}.{portal}` NATS event
- Plugin registry via `@register_enricher(country)` class decorator

---

## Phase 1: Design & Contracts

✅ **Completed**

### Artifacts produced

| Artifact | Path | Status |
|---|---|---|
| Data model & DB schema | [data-model.md](data-model.md) | ✅ Done |
| NATS contracts | [contracts/nats-subjects.md](contracts/nats-subjects.md) | ✅ Done |
| Dev quickstart | [quickstart.md](quickstart.md) | ✅ Done |

### Key design decisions

1. **Enricher lives inside `services/pipeline`** — same Dockerfile, same NATS/DB config; just a new `python -m pipeline.enricher` command. Avoids a new service image for what is functionally the next stage in the pipeline.

2. **Change detector is event-triggered, not cron-based** — subscribes to `scraper.cycle.completed.*` so detection runs exactly once per scrape cycle, with backpressure from NATS JetStream. The fallback timer catches missed events.

3. **Alembic migration 015 adds enrichment columns to the listings parent table** — PostGIS partitioned tables inherit columns added to the parent, so a single `ALTER TABLE listings ADD COLUMN` applies to all country partitions.

4. **`pois` table is not partitioned by country** — POI queries always filter by `country` with a B-tree index; the table is expected to be <10M rows (country × category × feature density), well within non-partitioned PostGIS limits.

5. **`PriceChangeEvent` is added to `estategap_common`** — alert engine and any future subscriber share the same model with no drift.

6. **Enrichment is idempotent** — the DB `UPDATE` uses `enrichment_status = 'completed'` as a guard: already-completed listings are skipped by the consumer query unless re-enrichment is explicitly requested.
