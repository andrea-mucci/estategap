# Research: PostgreSQL Database Schema

**Feature**: 004-database-schema  
**Date**: 2026-04-16  
**Status**: Complete — all NEEDS CLARIFICATION items resolved

---

## 1. Alembic + asyncpg Migration Driver

**Decision**: Use `psycopg2-binary` as the Alembic migration sync driver; use `asyncpg` for all runtime queries.

**Rationale**: Alembic's `env.py` uses a synchronous SQLAlchemy `engine` for running migrations. The `asyncpg` driver is async-only and does not work directly with Alembic's standard `run_migrations_online()` pattern without wrapping in `asyncio.run()`. The recommended approach is to configure `alembic.ini` with a `postgresql+psycopg2://` URL for migration runs, and `postgresql+asyncpg://` for application runtime. Both point to the same host; only the driver differs.

**Alternatives considered**:
- `asyncpg` with `run_sync` wrapper: Technically possible but adds boilerplate and is not the Alembic-recommended pattern. Rejected.
- `alembic[async]` + `asyncpg`: Supported since Alembic 1.8 but requires async env.py which is more complex and offers no benefit for a one-time migration run. Rejected for simplicity.

---

## 2. SQLAlchemy 2.0 Role

**Decision**: SQLAlchemy 2.0 declarative models used only to drive `alembic revision --autogenerate`. They are not imported at runtime by any service.

**Rationale**: asyncpg's raw query performance is significantly faster than the SQLAlchemy ORM (no object hydration overhead, native binary protocol). The constitution (Principle V) explicitly prohibits ORM at runtime for Go services using pgx; applying the same discipline to Python services avoids inconsistency.

**Alternatives considered**:
- SQLAlchemy `async_sessionmaker` at runtime: Adds 30–50% overhead per query for ORM hydration. Rejected.
- No SQLAlchemy at all (raw SQL migrations): Loses autogenerate capability and makes schema-code drift harder to detect. Rejected.

---

## 3. PostGIS Type Handling

**Decision**: Use `GeoAlchemy2 0.14` `Geometry` column type in SQLAlchemy models.

**Rationale**: GeoAlchemy2 generates correct PostgreSQL DDL for `GEOMETRY(Point, 4326)` and `GEOMETRY(MultiPolygon, 4326)`. It also generates the correct `CREATE INDEX ... USING GIST` statements via Alembic autogenerate.

**Alternatives considered**:
- Raw `Text` columns with WKT: No type safety; spatial indexes not generated. Rejected.
- Custom `UserDefinedType`: More boilerplate than GeoAlchemy2 with no additional benefit. Rejected.

---

## 4. LIST Partitioning in Alembic

**Decision**: Partitioned table DDL written as raw SQL inside `op.execute()` in the Alembic migration file.

**Rationale**: SQLAlchemy 2.0 does not support the `PARTITION BY LIST` clause in the `Table` DDL definition. GeoAlchemy2 does not add this capability. Raw SQL inside `op.execute()` is the standard Alembic approach for DDL that SQLAlchemy cannot express.

**Alternatives considered**:
- Custom DDL compiler extension: Complex and fragile; raw SQL is simpler and more readable. Rejected.
- Single unpartitioned table with country column: Violates Constitution Principle III. Rejected.

---

## 5. UUID Generation Strategy

**Decision**: Server-side `DEFAULT gen_random_uuid()` via the `pgcrypto` extension for all UUID primary keys.

**Rationale**: Server-side generation ensures IDs are valid even if an application bug omits the ID on insert. `pgcrypto` is already required by the constitution and is enabled in migration 001.

**Alternatives considered**:
- Python `uuid.uuid4()` in application code: Client-side; not guaranteed to be set on all insert paths. Rejected.
- `uuid-ossp` extension `uuid_generate_v4()`: Identical functionality to `gen_random_uuid()` from pgcrypto; adding a second extension is unnecessary. Rejected.
- `ULID` monotonic IDs: Better index locality but not native to PostgreSQL; adds complexity. Deferred to future optimisation.

---

## 6. JSONB Column Strategy

**Decision**: JSONB used for the following columns: `countries.config`, `portals.config`, `alert_rules.filters`, `alert_rules.channels`, `ai_conversations.criteria_state`, `ai_messages.criteria_snapshot`, `ai_messages.visual_refs`, `ml_model_versions.metrics`, `listings.shap_features` (ML explainability blob).

**GIN index on `alert_rules.filters`**: The alert engine evaluates rules using `@>` containment queries (e.g., `filters @> '{"country":"ES"}'`). A GIN index on this column makes such queries efficient.

**No GIN on other JSONB columns**: Other JSONB columns are read by primary key and do not need GIN indexes.

**Rationale**: JSONB avoids premature schema normalisation for data that evolves frequently (ML metrics, AI criteria snapshots). The columnar structure for the fixed domain fields (prices, areas, scores) is kept as typed columns for query efficiency and constraint enforcement.

**Alternatives considered**:
- Full normalisation of ML metrics into columns: Each model type has different metric names; JSONB is the correct approach. Rejected.
- JSONB for all listing attributes: Loses type safety, constraint enforcement, and index efficiency for the core query path. Rejected.

---

## 7. Generated Column for days_on_market

**Decision**: `days_on_market SMALLINT GENERATED ALWAYS AS (EXTRACT(DAY FROM COALESCE(delisted_at, NOW()) - published_at)::INTEGER) STORED`

**Rationale**: Eliminates a common application-layer calculation. The `STORED` variant persists the value on every write and is indexable. `COALESCE(delisted_at, NOW())` handles both active (still counting) and inactive (fixed count) listings.

**Alternatives considered**:
- Application-layer computation: Must be duplicated in every service that reads listings. Rejected.
- `VIRTUAL` generated column: Not supported in PostgreSQL (only STORED is supported). N/A.

**Constraint**: `published_at` must be non-null for this column to produce meaningful values. Application code must populate it on insert.

---

## 8. Materialized View Refresh Strategy

**Decision**: `REFRESH MATERIALIZED VIEW CONCURRENTLY zone_statistics` called via a `refresh_zone_statistics()` PL/pgSQL wrapper function.

**Rationale**: `CONCURRENTLY` allows read queries on the view during the refresh (no exclusive lock). The PL/pgSQL wrapper is callable from a Kubernetes CronJob, from the pipeline service after a bulk ingest, or from a manual admin call — without any application-layer Alembic dependency.

**Requirement for CONCURRENTLY**: The materialized view must have a unique index. A `UNIQUE INDEX ON zone_statistics (zone_id)` is created in migration 009.

**Alternatives considered**:
- `REFRESH MATERIALIZED VIEW` (blocking): Locks the view; unacceptable for a production read path. Rejected.
- Application-layer aggregation: Requires a full table scan on every frontend request. Rejected.
- Incremental materialisation via triggers: Complex to implement correctly with partitioned tables. Deferred.

---

## 9. Testcontainers Setup

**Decision**: `postgis/postgis:16-3.4` Docker image via `testcontainers-python`.

**Rationale**: Official image from the PostGIS project; includes both PostgreSQL 16 and PostGIS 3.4. Alembic migrations are run against the testcontainer before each integration test session.

**Test scope**:
1. `test_migrations.py`: `alembic upgrade head` → insert one row per table → `alembic downgrade base`
2. `test_partitioning.py`: `EXPLAIN (FORMAT JSON)` on country-filtered queries; assert `Scan on listings_{country}` node present and `listings_other` absent
3. `test_spatial.py`: Insert a point geometry; assert `EXPLAIN` shows Index Scan on GIST index
4. `test_constraints.py`: Duplicate `(source, source_id)` insert raises `UniqueViolation`
5. `test_seed_data.py`: After `upgrade head`, assert `SELECT COUNT(*) FROM countries = 5` and `SELECT COUNT(*) FROM portals = 10`

---

## 10. Seed Data Scope

**Decision**: Migration 010 inserts:
- **5 countries**: ES (EUR), IT (EUR), PT (EUR), FR (EUR), GB (GBP)
- **10 portals**: Idealista (ES), Fotocasa (ES), Immobiliare.it (IT), Casa.it (IT), Imovirtual (PT), Idealista (PT), SeLoger (FR), LeBonCoin (FR), Rightmove (GB), Zoopla (GB)

**Rationale**: Covers the two most active portals per launch country. Sufficient for integration test validation and initial scraping runs. Additional portals and countries added via future seed migrations.

**Down-migration**: Deletes the 10 portal rows and 5 country rows by primary key (safe; no listing data in a fresh schema).
