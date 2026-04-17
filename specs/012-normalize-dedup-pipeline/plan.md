# Implementation Plan: Normalize & Deduplicate Pipeline

**Branch**: `012-normalize-dedup-pipeline` | **Date**: 2026-04-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/012-normalize-dedup-pipeline/spec.md`

## Summary

Add two long-lived async Python consumers to `services/pipeline/` that transform raw scraped
listings into normalized, deduplicated database rows. The **Normalizer** consumes `raw.listings.*`
from NATS JetStream, maps portal-specific fields via YAML configs, converts currencies and units,
validates with Pydantic, batch-upserts to PostgreSQL, and re-publishes to `normalized.listings.*`.
The **Deduplicator** consumes `normalized.listings.*`, runs a three-stage PostGIS + feature +
Levenshtein matching pipeline, stamps matching records with a shared `canonical_id`, and publishes
to `deduplicated.listings.*`.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: nats-py (JetStream consumer), asyncpg (batch upsert), pydantic v2
(validation), rapidfuzz (Levenshtein), pydantic-settings (config), structlog (logging),
prometheus-client (metrics), PyYAML (mapping configs), unicodedata (stdlib accent stripping)
**Storage**: PostgreSQL 16 + PostGIS 3.4 (`listings` partitioned table + new `quarantine` table +
`data_completeness` column); `exchange_rates` table (read-only)
**Testing**: pytest + pytest-asyncio; testcontainers (PostgreSQL + PostGIS); NATS test server
**Target Platform**: Linux container (Kubernetes)
**Project Type**: Microservice sub-modules within existing `services/pipeline/` Python package
**Performance Goals**: 100 listings/second sustained at DB write layer; batch size 50
**Constraints**: Manual NATS ack — only ack after successful DB write; NAK on failure for
redelivery. Dedup query must complete in < 50 ms per listing (PostGIS index coverage).
**Scale/Scope**: Initial scope: Idealista ES + Fotocasa ES; architecture supports all portals
via YAML mapping config files.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Polyglot — Python for data pipeline | PASS | Both services are Python 3.12 |
| I. Service isolation — no cross-service imports | PASS | Only `libs/common` (`estategap_common`) used |
| II. NATS JetStream for async events | PASS | Consuming `raw.listings.*`, publishing `normalized.listings.*` and `deduplicated.listings.*` |
| II. No direct HTTP between services | PASS | Pipeline reads DB directly; no REST calls to other services |
| III. Country-partitioned tables | PASS | Inserting into existing `listings` table (already partitioned by `country`) |
| III. Prices in original + EUR | PASS | `asking_price` + `asking_price_eur` both written |
| III. Areas in source unit + m² | PASS | `built_area` + `built_area_m2` both written |
| V. Pydantic v2 for all data models | PASS | `NormalizedListing` from `libs/common`, `QuarantineRecord` new |
| V. asyncio + asyncpg | PASS | No ORM; raw asyncpg with batch inserts |
| V. structlog for logging | PASS | JSON structured logs with correlation fields |
| V. ruff + mypy strict | PASS | Inherited from pipeline service `pyproject.toml` |
| V. pytest + pytest-asyncio + testcontainers | PASS | Integration tests use real PostgreSQL |
| VI. No secrets in code | PASS | All credentials via pydantic-settings env vars |
| VII. Dockerfile per service | PASS | Extending existing `services/pipeline/Dockerfile` |

**Gate result**: ALL PASS — proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/012-normalize-dedup-pipeline/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   ├── nats-subjects.md
│   └── portal-mapping-schema.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
services/pipeline/
├── src/pipeline/
│   ├── normalizer/
│   │   ├── __init__.py
│   │   ├── config.py          # NormalizerSettings (pydantic-settings)
│   │   ├── consumer.py        # NATS JetStream consumer loop + batch logic
│   │   ├── mapper.py          # PortalMapper: load YAML config, apply field mappings
│   │   ├── transforms.py      # currency_convert, area_to_m2, map_property_type,
│   │   │                      #   map_condition, pieces_to_bedrooms
│   │   └── writer.py          # asyncpg batch upsert to listings + quarantine
│   ├── deduplicator/
│   │   ├── __init__.py
│   │   ├── config.py          # DeduplicatorSettings (pydantic-settings)
│   │   ├── consumer.py        # NATS JetStream consumer loop
│   │   ├── matcher.py         # three-stage match: PostGIS → feature → Levenshtein
│   │   └── address.py         # normalize_address(): lowercase, strip accents, stopwords
│   ├── metrics.py             # shared Prometheus counter/histogram definitions
│   └── db/
│       ├── models.py          # existing; add data_completeness column mapping
│       └── types.py           # existing
├── config/
│   └── mappings/
│       ├── es_idealista.yaml  # Idealista ES field mapping config
│       └── es_fotocasa.yaml   # Fotocasa ES field mapping config
├── alembic/versions/
│   └── 014_pipeline_quarantine.py  # ADD: quarantine table + data_completeness column
├── tests/
│   ├── unit/
│   │   ├── test_transforms.py
│   │   ├── test_mapper.py
│   │   └── test_address.py
│   └── integration/
│       ├── conftest.py        # testcontainers postgres+postgis fixture
│       ├── test_normalizer_writer.py
│       └── test_deduplicator_matcher.py
├── pyproject.toml             # add: rapidfuzz, pyyaml, nats-py, prometheus-client
└── Dockerfile                 # existing; update CMD for normalizer/deduplicator entrypoints
```

**Structure Decision**: Sub-modules within the existing `services/pipeline/` service. This avoids
creating a fourth Python service (constitution Principle I warns against service proliferation) and
reuses the existing Alembic infra, asyncpg pool setup, and Docker build context. Each sub-module
(`normalizer/`, `deduplicator/`) is a separate Python entry point (`python -m pipeline.normalizer`,
`python -m pipeline.deduplicator`) launched as independent Kubernetes Deployments from the same
container image.

## Complexity Tracking

> No constitution violations requiring justification.
