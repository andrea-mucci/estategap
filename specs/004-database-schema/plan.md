# Implementation Plan: PostgreSQL Database Schema

**Branch**: `004-database-schema` | **Date**: 2026-04-16 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `specs/004-database-schema/spec.md`

## Summary

Implement the complete PostgreSQL 16 + PostGIS 3.4 database schema for EstateGap via 10 versioned, reversible Alembic migrations managed from `services/pipeline/`. The schema covers 13 tables plus one materialized view, uses LIST partitioning on `listings` by country code, stores JSONB for flexible structured blobs (alert filters, ML metrics, criteria snapshots), and provides PostGIS GIST-indexed geometry columns for spatial queries. Seed data for 5 countries and 10 portals is delivered in the final migration.

---

## Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: Alembic 1.13+, SQLAlchemy 2.0, asyncpg 0.29, psycopg2-binary (Alembic sync driver), GeoAlchemy2 0.14 (PostGIS type support)  
**Storage**: PostgreSQL 16 + PostGIS 3.4, Redis 7 (out of scope for this feature)  
**Testing**: pytest + pytest-asyncio, testcontainers-python (postgres image with PostGIS)  
**Target Platform**: Linux (Kubernetes pod, CloudNativePG-managed cluster)  
**Project Type**: Database migration module inside `services/pipeline/`  
**Performance Goals**: Partition-pruned single-country scans; spatial queries via GIST index; `zone_statistics` refresh < 5 s on 100k listings  
**Constraints**: Migrations must be reversible for empty tables; no ORM at runtime (asyncpg direct queries); `gen_random_uuid()` via pgcrypto  
**Scale/Scope**: Target 10M+ listings across 8 countries; partitioned schema must support efficient per-country queries

---

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Polyglot Service Architecture | ✅ Pass | Migrations in Python (pipeline service); Go models added separately in `libs/pkg/` |
| II. Event-Driven Communication | ✅ Pass | Schema only; no inter-service comms in this feature |
| III. Country-First Data Sovereignty | ✅ Pass | LIST partitioning by country; dual-currency pricing; dual-unit areas; full price history audit trail |
| IV. ML-Powered Intelligence | ✅ Pass | `ml_model_versions` table; SHAP values JSONB in listings; `deal_score`, `deal_tier`, confidence bounds |
| V. Code Quality Discipline | ✅ Pass | ruff + mypy on migration code; pytest + testcontainers for integration tests |
| VI. Security & Ethical Scraping | ✅ Pass | `users` table includes hashed passwords, GDPR-ready `deleted_at` soft-delete; no secrets in migrations |
| VII. Kubernetes-Native Deployment | ✅ Pass | Migrations run as a Kubernetes Job (init-container or pre-upgrade hook); no cluster-level changes |

---

## Project Structure

### Documentation (this feature)

```text
specs/004-database-schema/
├── plan.md              ← this file
├── spec.md              ← feature specification
├── research.md          ← Phase 0: technology decisions
├── data-model.md        ← Phase 1: entity/table design
├── quickstart.md        ← Phase 1: local dev setup
├── contracts/
│   └── schema-overview.md   ← table contracts and index catalogue
└── tasks.md             ← Phase 2 output (created by /speckit.tasks)
```

### Source Code Layout

```text
services/pipeline/
├── alembic.ini                    ← Alembic configuration
├── alembic/
│   ├── env.py                     ← migration environment (asyncpg URL)
│   ├── script.py.mako             ← revision template
│   └── versions/
│       ├── 001_extensions.py      ← postgis, pg_trgm, pgcrypto
│       ├── 002_reference_tables.py ← countries, portals, exchange_rates
│       ├── 003_listings.py        ← listings (partitioned) + price_history
│       ├── 004_zones.py           ← zones (PostGIS MultiPolygon)
│       ├── 005_users.py           ← users
│       ├── 006_alerts.py          ← alert_rules + alert_log
│       ├── 007_ai.py              ← ai_conversations + ai_messages
│       ├── 008_ml_models.py       ← ml_model_versions
│       ├── 009_zone_statistics.py ← materialized view + refresh fn
│       └── 010_seed_data.py       ← countries + portals seed rows
├── pyproject.toml                 ← adds alembic, geoalchemy2, psycopg2-binary
├── src/
│   └── pipeline/
│       └── db/
│           ├── models.py          ← SQLAlchemy 2.0 declarative models (migration-gen only)
│           └── types.py           ← custom types (Geometry, JSONB aliases)

libs/common/
└── estategap_common/
    └── models/                    ← existing Pydantic models; update/extend here
        ├── listing.py             ← extend with full 50+ field schema
        ├── zone.py                ← extend with level enum
        ├── alert.py               ← extend with alert_log
        ├── conversation.py        ← extend with criteria_snapshot
        ├── scoring.py             ← extend with model_version registry fields
        ├── user.py                ← NEW: User, SubscriptionTier
        ├── reference.py           ← NEW: Country, Portal, ExchangeRate
        └── ml.py                  ← NEW: MlModelVersion

tests/
└── integration/
    └── test_schema/
        ├── conftest.py            ← testcontainers postgres+postgis fixture
        ├── test_migrations.py     ← upgrade head + downgrade all round-trip
        ├── test_partitioning.py   ← partition pruning EXPLAIN tests
        ├── test_spatial.py        ← GIST index usage + spatial queries
        ├── test_constraints.py    ← uniqueness, FK, partial index
        └── test_seed_data.py      ← verify seed rows present
```

**Structure Decision**: All migration code lives inside `services/pipeline/` as the pipeline service owns schema evolution. Shared Pydantic models live in `libs/common/estategap_common/models/` and are updated to mirror the full DB schema. No new service or module is introduced.

---

## Complexity Tracking

No constitution violations. The schema complexity is inherent to the domain (multi-country, multi-entity platform) and is not introduced by the implementation approach.

---

## Phase 0: Research

See [research.md](./research.md) for full findings. Key decisions summarised:

| Topic | Decision | Rationale |
|-------|----------|-----------|
| Migration driver | Alembic with `psycopg2` sync URL for migrations, `asyncpg` for runtime | Alembic's `env.py` works best with sync drivers; asyncpg is used by all services at runtime |
| ORM role | SQLAlchemy 2.0 declarative models used only for migration autogenerate; not imported at runtime | Avoids ORM overhead at runtime; asyncpg raw queries are 3× faster |
| PostGIS types | GeoAlchemy2 `Geometry` column type in SQLAlchemy models | Provides correct DDL for `GEOMETRY(Point, 4326)` and `GEOMETRY(MultiPolygon, 4326)` |
| Partitioned table DDL | Raw SQL in `op.execute()` inside Alembic migration | SQLAlchemy 2.0 does not support `PARTITION BY LIST` DDL natively; raw SQL is correct approach |
| UUID generation | `gen_random_uuid()` via pgcrypto server-side default | Avoids client-side UUID generation; consistent with the constitution's pgcrypto extension requirement |
| JSONB indexing | GIN index on `alert_rules.filters` only; other JSONB columns queried by key not full-text | GIN on filters enables `@>` containment queries for alert matching |
| Generated column | `days_on_market` as `GENERATED ALWAYS AS (EXTRACT(DAY FROM COALESCE(delisted_at, NOW()) - published_at)) STORED` | Eliminates application-layer computation; automatically kept in sync |
| Materialized view refresh | `REFRESH MATERIALIZED VIEW CONCURRENTLY` via a `refresh_zone_statistics()` PL/pgSQL function | Allows reads during refresh; stored function callable from any service or cron job |
| Testcontainers image | `postgis/postgis:16-3.4` Docker image | Official image with both PostgreSQL 16 and PostGIS 3.4 pre-installed |

---

## Phase 1: Design & Contracts

### Data Model

See [data-model.md](./data-model.md) for full entity definitions. Summary:

**Reference Group**

| Table | PK | Key Columns | Indexes |
|-------|----|------------|---------|
| `countries` | `code CHAR(2)` | `name, currency, active, config JSONB` | PK |
| `portals` | `id UUID` | `name, country_code FK, base_url, spider_class, enabled, config JSONB` | PK, `(country_code, enabled)` |
| `exchange_rates` | `(currency, date)` composite | `rate_to_eur NUMERIC(12,6)` | PK |

**Listings Group**

| Table | PK | Partition | Key Columns |
|-------|----|-----------|------------|
| `listings` | `id UUID` | LIST(country) | 50+ cols; `location GEOMETRY(Point,4326)`; `UNIQUE(source,source_id)` |
| `listings_es` | inherits | FOR VALUES IN ('ES') | — |
| `listings_fr` | inherits | FOR VALUES IN ('FR') | — |
| `listings_it` | inherits | FOR VALUES IN ('IT') | — |
| `listings_pt` | inherits | FOR VALUES IN ('PT') | — |
| `listings_de` | inherits | FOR VALUES IN ('DE') | — |
| `listings_gb` | inherits | FOR VALUES IN ('GB') | — |
| `listings_nl` | inherits | FOR VALUES IN ('NL') | — |
| `listings_us` | inherits | FOR VALUES IN ('US') | — |
| `listings_other` | inherits | DEFAULT | — |
| `price_history` | `id BIGSERIAL` | — | `listing_id UUID FK, old_price, new_price, currency, recorded_at`; INDEX `(listing_id, recorded_at DESC)` |

**Geographic Group**

| Table | PK | Key Columns | Indexes |
|-------|----|------------|---------|
| `zones` | `id UUID` | `name, country_code, level SMALLINT, parent_id UUID self-ref, geometry GEOMETRY(MultiPolygon,4326)` | GIST(geometry), `(country_code, level)` |

**User Group**

| Table | PK | Key Columns | Indexes |
|-------|----|------------|---------|
| `users` | `id UUID` | `email UNIQUE, password_hash, oauth_provider, subscription_tier, stripe_customer_id, deleted_at` | `email`, `stripe_customer_id` |

**Alert Group**

| Table | PK | Key Columns | Indexes |
|-------|----|------------|---------|
| `alert_rules` | `id UUID` | `user_id FK, name, filters JSONB, channels JSONB, active, last_triggered_at` | GIN(filters), `(user_id, active)` |
| `alert_log` | `id UUID` | `rule_id FK, listing_id, channel, status, sent_at, error_message` | `(rule_id, sent_at DESC)` |

**AI Group**

| Table | PK | Key Columns | Indexes |
|-------|----|------------|---------|
| `ai_conversations` | `id UUID` | `user_id FK, language, criteria_state JSONB, alert_rule_id, turn_count, status` | `(user_id, status)` |
| `ai_messages` | `id BIGSERIAL` | `conversation_id FK, role, content, criteria_snapshot JSONB, visual_refs JSONB, tokens_used` | `(conversation_id, id)` |

**ML Group**

| Table | PK | Key Columns | Indexes |
|-------|----|------------|---------|
| `ml_model_versions` | `id UUID` | `country_code, algorithm, version_tag UNIQUE, artifact_path, dataset_ref, metrics JSONB, status, trained_at` | `(country_code, status)`, UNIQUE(version_tag) |

**Materialized View**

| View | Refresh | Key Columns |
|------|---------|------------|
| `zone_statistics` | CONCURRENTLY via `refresh_zone_statistics()` | `zone_id, listing_count, median_price_m2_eur, total_volume_eur, active_listings, refreshed_at` |

### Key Index Catalogue

```sql
-- Listings (applied to each partition automatically via parent)
CREATE INDEX ON listings USING GIST (location);
CREATE INDEX ON listings (country, status, deal_tier);
CREATE INDEX ON listings (city, status) WHERE status = 'active';
CREATE INDEX ON listings (deal_tier) WHERE status = 'active';   -- partial
CREATE INDEX ON listings USING GIN (description gin_trgm_ops); -- full-text (pg_trgm)

-- Price history
CREATE INDEX ON price_history (listing_id, recorded_at DESC);

-- Zones
CREATE INDEX ON zones USING GIST (geometry);
CREATE INDEX ON zones (country_code, level);

-- Alert rules
CREATE INDEX ON alert_rules USING GIN (filters);
CREATE INDEX ON alert_rules (user_id, active);

-- Alert log
CREATE INDEX ON alert_log (rule_id, sent_at DESC);

-- AI
CREATE INDEX ON ai_conversations (user_id, status);
CREATE INDEX ON ai_messages (conversation_id, id);

-- ML models
CREATE INDEX ON ml_model_versions (country_code, status);
```

### Contracts

See [contracts/schema-overview.md](./contracts/schema-overview.md) for the full table contracts and migration dependency graph.

---

## Migration Execution Order

```
001_extensions        → enables postgis, pg_trgm, pgcrypto
002_reference_tables  → countries, portals, exchange_rates
003_listings          → listings (partitioned) + all indexes + price_history
004_zones             → zones (PostGIS geometry)
005_users             → users
006_alerts            → alert_rules + alert_log
007_ai                → ai_conversations + ai_messages
008_ml_models         → ml_model_versions
009_zone_statistics   → materialized view + refresh function
010_seed_data         → INSERT countries (ES, IT, PT, FR, GB) + 10 portals
```

Each migration has an `upgrade()` and `downgrade()` function. Downgrades are tested on empty tables. `010_seed_data` downgrade deletes the seed rows.

---

## Quickstart

See [quickstart.md](./quickstart.md) for the full local setup guide. Summary:

```bash
# 1. Start local PostgreSQL + PostGIS
docker run -d --name estategap-db \
  -e POSTGRES_USER=estategap \
  -e POSTGRES_PASSWORD=estategap \
  -e POSTGRES_DB=estategap \
  -p 5432:5432 \
  postgis/postgis:16-3.4

# 2. Install dependencies (from services/pipeline/)
cd services/pipeline
uv sync

# 3. Run migrations
DATABASE_URL="postgresql://estategap:estategap@localhost:5432/estategap" \
  uv run alembic upgrade head

# 4. Run tests
uv run pytest tests/integration/test_schema/ -v
```

---

## Open Questions / Follow-On Work

| Item | Owner | Notes |
|------|-------|-------|
| Go struct models in `libs/pkg/` | Next feature | Will mirror Pydantic models once schema is validated in staging |
| Sub-partitioning by city (HASH) | Future migration | Triggered when any country partition exceeds 5M rows |
| Exchange rate loader | pipeline service | Separate task; schema only defines the table |
| `zone_statistics` refresh cron | K8s CronJob | Configured post-schema; calls `refresh_zone_statistics()` |
| Read replica routing | api-gateway | Separate concern; asyncpg pool config |
