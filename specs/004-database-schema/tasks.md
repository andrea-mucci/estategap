# Tasks: PostgreSQL Database Schema

**Input**: Design documents from `specs/004-database-schema/`  
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: Integration tests are included — the acceptance criteria in spec.md explicitly require partition pruning verification, spatial index verification, constraint tests, and full migration round-trip validation.

**Organization**: Tasks are grouped by user story. All 10 migration files are created in Phase 2 (Foundational) because migrations form the schema itself — each depends on the previous via the Alembic revision chain. User story phases (3–8) cover SQLAlchemy declarative models, Pydantic models, and integration tests that validate each story's database contract.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no blocking dependency on an incomplete parallel sibling)
- **[Story]**: Which user story this task belongs to (US1–US6)
- All paths relative to repo root

---

## Phase 1: Setup (Project Initialization)

**Purpose**: Create the directory skeleton, wire dependencies, and prepare Alembic for first use.

- [X] T001 Create `services/pipeline/alembic/versions/` directory and `services/pipeline/src/pipeline/db/` package directories (with `__init__.py` files)
- [ ] T002 Add `alembic>=1.13`, `sqlalchemy>=2.0`, `geoalchemy2>=0.14`, `psycopg2-binary>=2.9`, `testcontainers[postgres]>=4.4` to `services/pipeline/pyproject.toml` under `[project.dependencies]` and `[dependency-groups]` (dev) respectively; run `uv sync`
- [X] T003 [P] Create `services/pipeline/alembic.ini` with `sqlalchemy.url = postgresql://%(DB_USER)s:%(DB_PASSWORD)s@%(DB_HOST)s/%(DB_NAME)s` and `script_location = alembic`
- [X] T004 [P] Add `[tool.ruff]` and `[tool.mypy]` sections to `services/pipeline/pyproject.toml` matching project-wide strict config from `CLAUDE.md`

**Checkpoint**: `uv sync` passes, `uv run alembic --help` works, linting config present.

---

## Phase 2: Foundational (Alembic Infrastructure + All Migrations)

**Purpose**: Build the entire schema foundation. All 10 migration files must exist and chain correctly before any user story test can run.

**⚠️ CRITICAL**: Migrations must be created in order (001 → 010). Each migration's `down_revision` points to the previous. No user story work can be tested until this phase is complete.

### Infrastructure

- [X] T005 Create `services/pipeline/src/pipeline/db/types.py` — define `GeometryPoint` and `GeometryMultiPolygon` as `GeoAlchemy2.Geometry` subtype aliases, and a `JSONB` alias via `sqlalchemy.dialects.postgresql.JSONB`
- [X] T006 Create `services/pipeline/alembic/env.py` — read `DATABASE_URL` from environment (override `alembic.ini` when set), configure `run_migrations_online()` with `psycopg2` sync engine, import `Base.metadata` from `services/pipeline/src/pipeline/db/models.py` for autogenerate support
- [X] T007 Create `services/pipeline/alembic/script.py.mako` — standard Alembic revision template with `# type: ignore` suppressor and UTF-8 encoding header
- [X] T008 Create `tests/integration/test_schema/conftest.py` — `pytest` fixture `db_engine` using `testcontainers.postgres.PostgresContainer("postgis/postgis:16-3.4")`; applies `alembic upgrade head` before yielding the `sqlalchemy` engine; tears down container after session

### SQLAlchemy Declarative Models

These models drive Alembic autogenerate for non-partitioned tables. The partitioned `listings` table is handled with raw SQL in migration 003.

- [X] T009 [P] Add `Country`, `Portal`, `ExchangeRate` SQLAlchemy 2.0 declarative models to `services/pipeline/src/pipeline/db/models.py` (use `mapped_column`, `Mapped[...]` annotations, `JSONB` from types.py)
- [X] T010 [P] Add `PriceHistory` SQLAlchemy model to `services/pipeline/src/pipeline/db/models.py` (`BIGSERIAL` PK via `BigInteger` + `Identity()`, `listing_id UUID`, `country CHAR(2)`, pricing columns, `recorded_at`)
- [X] T011 [P] Add `Zone` SQLAlchemy model to `services/pipeline/src/pipeline/db/models.py` (`GeometryMultiPolygon` from types.py, `parent_id` self-referencing FK, `level SMALLINT`, `slug UNIQUE`)
- [X] T012 [P] Add `User` SQLAlchemy model to `services/pipeline/src/pipeline/db/models.py` (email UNIQUE, password_hash, oauth fields, subscription_tier, stripe IDs, deleted_at for soft-delete)
- [X] T013 [P] Add `AlertRule`, `AlertLog` SQLAlchemy models to `services/pipeline/src/pipeline/db/models.py` (`filters JSONB`, `channels JSONB`, `ON DELETE CASCADE` FK)
- [X] T014 [P] Add `AiConversation`, `AiMessage` SQLAlchemy models to `services/pipeline/src/pipeline/db/models.py` (`criteria_state JSONB`, `criteria_snapshot JSONB`, `visual_refs JSONB`, `BIGSERIAL` PK for messages)
- [X] T015 [P] Add `MlModelVersion` SQLAlchemy model to `services/pipeline/src/pipeline/db/models.py` (`metrics JSONB`, `feature_names JSONB`, partial unique index on `country_code WHERE status='active'`)

### Migration Files (must be created in chain order)

- [X] T016 Write `services/pipeline/alembic/versions/001_extensions.py` — `op.execute("CREATE EXTENSION IF NOT EXISTS postgis")`, `pg_trgm`, `pgcrypto`; downgrade drops each extension; set `revision` and `down_revision = None`
- [X] T017 Write `services/pipeline/alembic/versions/002_reference_tables.py` — use Alembic autogenerate output from `Country`, `Portal`, `ExchangeRate` models; add `UNIQUE(name, country_code)` on portals; add `(country_code, enabled)` index on portals; `down_revision = "001_extensions_rev"`
- [X] T018 Write `services/pipeline/alembic/versions/003_listings.py` — use `op.execute()` for the full partitioned DDL: `CREATE TABLE listings (...) PARTITION BY LIST (country)`, 9 partition `CREATE TABLE ... PARTITION OF` statements, all indexes (GIST on location, partial on deal_tier, GIN tsvector on description_orig, composite on country+status); then standard autogenerate for `price_history` table with `(listing_id, recorded_at DESC)` composite index; `down_revision = "002_ref_rev"`
- [X] T019 Write `services/pipeline/alembic/versions/004_zones.py` — autogenerate from `Zone` model; add GIST index on `geometry`, GIST index on `bbox`; downgrade drops table; `down_revision = "003_listings_rev"`
- [X] T020 Write `services/pipeline/alembic/versions/005_users.py` — autogenerate from `User` model; add partial index on `email WHERE deleted_at IS NULL`; `down_revision = "004_zones_rev"`
- [X] T021 Write `services/pipeline/alembic/versions/006_alerts.py` — autogenerate from `AlertRule`, `AlertLog` models; add GIN index on `alert_rules.filters`; add partial index on `alert_log.status WHERE status='pending'`; `down_revision = "005_users_rev"`
- [X] T022 Write `services/pipeline/alembic/versions/007_ai.py` — autogenerate from `AiConversation`, `AiMessage` models; add `(user_id, status)` index on conversations; `down_revision = "006_alerts_rev"`
- [X] T023 Write `services/pipeline/alembic/versions/008_ml_models.py` — autogenerate from `MlModelVersion` model; add partial unique index on `(country_code) WHERE status='active'`; `down_revision = "007_ai_rev"`
- [X] T024 Write `services/pipeline/alembic/versions/009_zone_statistics.py` — `op.execute()` for `CREATE MATERIALIZED VIEW zone_statistics AS SELECT ... FROM zones z JOIN listings l ON l.zone_id = z.id ...`; create `UNIQUE INDEX ON zone_statistics (zone_id)`; create `CREATE OR REPLACE FUNCTION refresh_zone_statistics()` PL/pgSQL wrapper; downgrade drops function, index, and view; `down_revision = "008_ml_rev"`
- [X] T025 Write `services/pipeline/alembic/versions/010_seed_data.py` — `op.bulk_insert()` for 5 country rows (ES/EUR, IT/EUR, PT/EUR, FR/EUR, GB/GBP) and 10 portal rows (Idealista ES, Fotocasa ES, Immobiliare.it IT, Casa.it IT, Imovirtual PT, Idealista PT, SeLoger FR, LeBonCoin FR, Rightmove GB, Zoopla GB); downgrade deletes by PK; `down_revision = "009_zone_stats_rev"`

**Checkpoint**: `uv run alembic upgrade head` completes all 10 migrations without error. `uv run alembic downgrade base` reverses all cleanly.

---

## Phase 3: User Story 1 — Platform Services Can Store and Query Listings (Priority: P1) 🎯 MVP

**Goal**: Validate that listings land in the correct country partition, spatial indexes work, and the uniqueness constraint prevents duplicates.

**Independent Test**: Insert a listing with `country='ES'`, run `EXPLAIN (ANALYZE)` on a country-filtered query, confirm `listings_es` is the only partition scanned.

### Pydantic Models for US1

- [X] T026 [P] [US1] Create `libs/common/estategap_common/models/reference.py` — define `Country`, `Portal`, `ExchangeRate` Pydantic v2 `BaseModel` classes mirroring the DB schema; export from `estategap_common/models/__init__.py`
- [X] T027 [P] [US1] Extend `libs/common/estategap_common/models/listing.py` — replace stub `Listing` class with full 50+ field schema matching `data-model.md`: all identity, location, pricing, physical, condition, commercial, land, ML score, and metadata fields; add `ListingStatus` values for `sold`, `withdrawn`, `expired`

### Integration Tests for US1

- [X] T028 [US1] Write `tests/integration/test_schema/test_migrations.py` — `test_upgrade_head`: apply `alembic upgrade head` via `conftest.db_engine`, assert `alembic_version` table shows revision `010`; `test_downgrade_base`: apply `alembic downgrade base`, assert all tables are dropped
- [X] T029 [US1] Write `tests/integration/test_schema/test_partitioning.py` — insert one listing per country (ES, FR, IT, PT, DE, GB, NL, US, and an unknown country 'JP'); for each country run `EXPLAIN (FORMAT JSON) SELECT ... FROM listings WHERE country = $1`; parse JSON and assert only `listings_{country}` appears in the plan nodes and `listings_other` appears for 'JP'
- [X] T030 [US1] Write `tests/integration/test_schema/test_spatial.py` — insert a listing with `ST_SetSRID(ST_MakePoint(-3.7038, 40.4168), 4326)` (Madrid); run `EXPLAIN (FORMAT JSON) SELECT ... FROM listings WHERE ST_DWithin(location, ST_MakePoint(-3.7038, 40.4168)::geography, 5000)`; assert plan contains `Index Scan` on the GIST index
- [X] T031 [US1] Write `tests/integration/test_schema/test_constraints.py` — `test_unique_source_source_id`: insert a listing, attempt second insert with same `(source, source_id, country)`, assert `asyncpg.exceptions.UniqueViolationError` is raised; `test_generated_days_on_market`: insert a listing with `published_at = NOW() - interval '10 days'`, assert `days_on_market >= 10`

**Checkpoint**: All 4 test files pass. Partition pruning confirmed. GIST spatial index confirmed. Uniqueness constraint confirmed.

---

## Phase 4: User Story 2 — Price Changes Are Tracked Over Time (Priority: P2)

**Goal**: Validate that price history appends correctly and the composite index supports efficient timeline retrieval.

**Independent Test**: Insert a listing and three `price_history` rows at different timestamps; query `ORDER BY recorded_at DESC LIMIT 1` and verify the latest price is returned using the index.

### Pydantic Models for US2

- [X] T032 [P] [US2] Add `PriceChange` Pydantic v2 class to `libs/common/estategap_common/models/listing.py` — fields: `id`, `listing_id`, `country`, `old_price`, `new_price`, `currency`, `old_price_eur`, `new_price_eur`, `change_type`, `old_status`, `new_status`, `recorded_at`, `source`

### Integration Tests for US2

- [X] T033 [US2] Write `tests/integration/test_schema/test_price_history.py` — `test_append_price_changes`: insert a listing and 3 price_history rows; query `ORDER BY recorded_at DESC`; assert results are in reverse-chronological order and count is 3; `test_price_history_index_usage`: run `EXPLAIN (FORMAT JSON)` on the timeline query; assert `Index Scan` on `price_history_listing_id_recorded_at_idx`; `test_no_fk_violation`: insert price_history with a random UUID `listing_id` (no FK constraint on partitioned parent), assert insert succeeds

**Checkpoint**: Price history append-only behavior and index usage confirmed independently.

---

## Phase 5: User Story 3 — Users Can Register and Manage Alert Rules (Priority: P3)

**Goal**: Validate user row creation, FK relationship to alert_rules, GIN-indexed filter queries, and alert_log delivery tracking.

**Independent Test**: Create a user, insert an alert_rule referencing that user with a JSONB filters object, run a `@>` containment query on filters, assert the index is used.

### Pydantic Models for US3

- [X] T034 [P] [US3] Create `libs/common/estategap_common/models/user.py` — define `SubscriptionTier` enum (`free`, `starter`, `pro`, `enterprise`) and `User` Pydantic v2 model with all fields from `data-model.md`; export from `models/__init__.py`
- [X] T035 [P] [US3] Extend `libs/common/estategap_common/models/alert.py` — add `AlertLog` Pydantic v2 class (rule_id, listing_id, country, channel, status, error_message, sent_at); extend `AlertRule` with `channels`, `last_triggered_at`, `trigger_count`

### Integration Tests for US3

- [X] T036 [US3] Write `tests/integration/test_schema/test_users_alerts.py` — `test_user_insert_and_retrieve`: insert a user row, retrieve by email, assert all fields round-trip correctly; `test_soft_delete_index`: insert a deleted user (`deleted_at = NOW()`), run query `WHERE email = $1 AND deleted_at IS NULL`, assert deleted user is excluded; `test_alert_rule_fk`: insert user + alert_rule, assert FK constraint satisfied; `test_gin_filter_query`: run `SELECT * FROM alert_rules WHERE filters @> '{"country": "ES"}'::jsonb`, assert `EXPLAIN` shows GIN index scan; `test_alert_log_delivery`: insert alert_log row with `status='sent'`, query by rule_id ordered by sent_at DESC

**Checkpoint**: User + alert storage works. GIN filter queries use the index. FK integrity enforced.

---

## Phase 6: User Story 4 — AI Conversations Are Persisted Per Turn (Priority: P4)

**Goal**: Validate conversation creation, message appending with criteria snapshots, and turn_count tracking.

**Independent Test**: Create an `ai_conversations` row, append two `ai_messages` with different `criteria_snapshot` JSONB values, query the latest snapshot via `ORDER BY id DESC LIMIT 1`.

### Pydantic Models for US4

- [X] T037 [P] [US4] Extend `libs/common/estategap_common/models/conversation.py` — update `ConversationState` to include `language`, `criteria_state JSONB`, `alert_rule_id`, `turn_count`, `status`, `model_used`; update `ChatMessage` to include `criteria_snapshot`, `visual_refs`, `tokens_used`

### Integration Tests for US4

- [X] T038 [US4] Write `tests/integration/test_schema/test_ai_conversations.py` — `test_conversation_create`: insert a conversation row, assert all fields retrieved; `test_message_append`: append 2 messages to a conversation, assert `COUNT(*) = 2`; `test_criteria_snapshot_roundtrip`: insert a message with `criteria_snapshot = {"country": "ES", "max_price_eur": 200000}`, retrieve and assert the JSONB is identical; `test_turn_count_index`: run `EXPLAIN` on `WHERE user_id = $1 AND status = 'active'`, assert index scan on `ai_conversations_user_id_status_idx`

**Checkpoint**: AI session persistence confirmed. Criteria snapshots round-trip. Index on (user_id, status) used.

---

## Phase 7: User Story 5 — ML Model Versions Are Registered (Priority: P5)

**Goal**: Validate model version insert, the partial unique index enforcing one active model per country, and metrics JSONB round-trip.

**Independent Test**: Insert two `ml_model_versions` rows for country 'ES', promote one to `status='active'`, attempt to insert a second active row for ES, assert the partial unique index rejects it.

### Pydantic Models for US5

- [X] T039 [P] [US5] Create `libs/common/estategap_common/models/ml.py` — define `MlModelVersion` Pydantic v2 model with all fields from `data-model.md`; define `ModelStatus` enum (`staging`, `active`, `retired`); export from `models/__init__.py`

### Integration Tests for US5

- [X] T040 [US5] Write `tests/integration/test_schema/test_ml_models.py` — `test_model_version_insert`: insert a model version with metrics JSONB `{"mae": 15000, "rmse": 22000, "r2": 0.87}`, retrieve and assert fields; `test_active_model_partial_unique`: insert active model for 'ES', attempt second active insert for 'ES', assert `UniqueViolationError`; `test_metrics_jsonb_access`: run `SELECT metrics->>'mae' FROM ml_model_versions WHERE country_code = 'ES'`, assert value is `'15000'`

**Checkpoint**: ML model registry constraints confirmed. One active model per country enforced at DB level.

---

## Phase 8: User Story 6 — Zone Statistics Materialized View Is Refreshed (Priority: P6)

**Goal**: Validate zone hierarchy creation, geometry storage, listings-to-zone assignment, and zone_statistics refresh producing correct aggregates.

**Independent Test**: Create a zone, insert 5 listings with `zone_id` set, call `SELECT refresh_zone_statistics()`, query `zone_statistics` and assert `listing_count = 5`.

### Pydantic Models for US6

- [X] T041 [P] [US6] Extend `libs/common/estategap_common/models/zone.py` — add `level` field with `ZoneLevel` enum (0=country, 1=region, 2=province, 3=city, 4=neighbourhood), `name_local`, `bbox_wkt`, `slug`, `osm_id`, `area_km2`

### Integration Tests for US6

- [X] T042 [US6] Write `tests/integration/test_schema/test_zones_statistics.py` — `test_zone_insert_with_geometry`: insert a zone with `geometry = ST_GeomFromText('MULTIPOLYGON(...)', 4326)`, retrieve and assert `ST_AsText(geometry)` round-trips; `test_zone_hierarchy`: insert a parent zone and child zone with `parent_id`, assert parent-child query works; `test_gist_index_on_geometry`: run `EXPLAIN` on `ST_Contains(geometry, ST_MakePoint(-3.7, 40.4)::geometry)`, assert GIST index used; `test_zone_statistics_refresh`: insert 3 active listings with zone_id, call `SELECT refresh_zone_statistics()`, query view and assert `listing_count = 3` and `median_price_m2_eur` is non-null; `test_empty_zone_excluded`: verify a zone with no listings is absent from `zone_statistics` after refresh

**Checkpoint**: Zone hierarchy, PostGIS geometry, and materialized view refresh all confirmed.

---

## Phase 9: Seed Data Validation

**Goal**: Confirm that migration 010 seeds exactly the right reference data rows.

**Independent Test**: Apply `alembic upgrade head` on a fresh DB, count countries and portals.

- [X] T043 Write `tests/integration/test_schema/test_seed_data.py` — `test_countries_seeded`: assert `SELECT COUNT(*) FROM countries WHERE code IN ('ES','IT','PT','FR','GB') = 5`; `test_portals_seeded`: assert `SELECT COUNT(*) FROM portals = 10`; `test_portal_spider_classes`: assert all 10 portals have non-empty `spider_class`; `test_seed_downgrade`: apply `alembic downgrade -1` (reverts migration 010 only), assert `COUNT(countries) = 0` and `COUNT(portals) = 0`, then re-apply `alembic upgrade head`

**Checkpoint**: Seed data present and reversible without affecting schema structure.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: End-to-end validation, documentation, and integration with the broader monorepo.

- [X] T044 [P] Update `libs/common/estategap_common/models/__init__.py` — export all new and updated model classes (`Country`, `Portal`, `ExchangeRate`, `PriceChange`, `User`, `SubscriptionTier`, `AlertLog`, `MlModelVersion`, `ModelStatus`, `ZoneLevel`) so all services can import from `estategap_common.models`
- [ ] T045 [P] Run `uv run mypy libs/common/estategap_common/models/` and fix all strict-mode type errors in the updated Pydantic models
- [ ] T046 [P] Run `uv run ruff check services/pipeline/ libs/common/` and resolve all linting errors in migration files and model files
- [ ] T047 Run full integration test suite `uv run pytest tests/integration/test_schema/ -v --tb=short` and confirm all tests pass
- [X] T048 [P] Add `services/pipeline/` path to the Makefile `lint` and `test` targets so CI picks up the new module
- [ ] T049 Validate the quickstart guide (`specs/004-database-schema/quickstart.md`) end-to-end: spin up the Docker container, run `alembic upgrade head`, execute every verification command in the guide, confirm all outputs match expectations

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 completion — **blocks all user story testing**
- **US1 (Phase 3)**: Depends on Phase 2 (all 10 migration files must exist for full round-trip test)
- **US2 (Phase 4)**: Depends on Phase 2 (price_history created in migration 003)
- **US3 (Phase 5)**: Depends on Phase 2
- **US4 (Phase 6)**: Depends on Phase 2
- **US5 (Phase 7)**: Depends on Phase 2
- **US6 (Phase 8)**: Depends on Phase 2
- **Seed (Phase 9)**: Depends on Phase 2 (migration 010 must exist)
- **Polish (Phase 10)**: Depends on all story phases complete

### User Story Dependencies

- **US1 (P1)**: No dependency on other user stories — can start immediately after Phase 2
- **US2 (P2)**: No dependency on US1 — price_history table exists from migration 003
- **US3 (P3)**: No dependency on US1 or US2
- **US4 (P4)**: Soft dependency on US3 (conversations reference users via FK) — can write Pydantic models independently but integration test needs users table
- **US5 (P5)**: No dependency on other stories — completely standalone
- **US6 (P6)**: Soft dependency on US1 (zone_statistics joins listings) — needs listings table to exist, which is from Phase 2

### Within Each Migration File

Migration files are strictly sequential (each has a `down_revision` pointing to the previous):
```
T016(001) → T017(002) → T018(003) → T019(004) → T020(005) →
T021(006) → T022(007) → T023(008) → T024(009) → T025(010)
```

### Parallel Opportunities

Within Phase 2:
- T005, T006, T007, T008 can all run in parallel
- T009–T015 (SQLAlchemy models) can all run in parallel with each other
- Migration files T016–T025 must run sequentially (chain order)

Within each User Story phase:
- Pydantic model tasks [P] can run in parallel with writing integration tests
- Tests should be written before or alongside implementation confirmation

---

## Parallel Example: Phase 2 SQLAlchemy Models

```bash
# All 7 SQLAlchemy model tasks can be dispatched simultaneously:
Task T009: "Add Country, Portal, ExchangeRate models to services/pipeline/src/pipeline/db/models.py"
Task T010: "Add PriceHistory model to services/pipeline/src/pipeline/db/models.py"
Task T011: "Add Zone model to services/pipeline/src/pipeline/db/models.py"
Task T012: "Add User model to services/pipeline/src/pipeline/db/models.py"
Task T013: "Add AlertRule, AlertLog models to services/pipeline/src/pipeline/db/models.py"
Task T014: "Add AiConversation, AiMessage models to services/pipeline/src/pipeline/db/models.py"
Task T015: "Add MlModelVersion model to services/pipeline/src/pipeline/db/models.py"
```

## Parallel Example: User Story 3

```bash
# Both Pydantic model tasks can be dispatched simultaneously:
Task T034: "Create libs/common/estategap_common/models/user.py"
Task T035: "Extend libs/common/estategap_common/models/alert.py"

# Once T034 and T035 complete:
Task T036: "Write tests/integration/test_schema/test_users_alerts.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (migrations 001–003 minimum; T016–T018 are MVP-critical)
3. Complete Phase 3: US1 (partitioning, spatial, constraint validation)
4. **STOP and VALIDATE**: Run `pytest tests/integration/test_schema/test_partitioning.py test_spatial.py test_constraints.py`
5. The core listings schema is production-ready at this point

### Incremental Delivery

1. Setup + Foundational → Full schema deployed, seed data seeded
2. US1 → Listings partitioning and spatial indexing confirmed → **MVP shipped**
3. US2 → Price history audit trail confirmed
4. US3 → Users + alerts stored and queryable
5. US4 → AI conversation state persisted
6. US5 → ML model registry enforces one-active-per-country
7. US6 → Zone statistics materialized view refreshable
8. Polish → Full test suite green, CI integrated

### Full Schema in One Pass (Solo Developer)

1. Phases 1–2 completely first (foundation everything)
2. Work through US1 → US6 sequentially
3. Phase 9 (seed tests) after all migrations exist
4. Phase 10 (polish) last

---

## Notes

- [P] tasks = different files, safe to run concurrently
- Each migration file must set `down_revision` to the correct parent revision ID (returned by `alembic revision` command)
- The listings table uses `op.execute()` raw SQL — do NOT attempt autogenerate for it; write DDL by hand from `data-model.md`
- `days_on_market` is a `GENERATED ALWAYS AS ... STORED` column — do not include in INSERT statements
- `zone_id` in listings has no FK constraint (partitioned table limitation) — referential integrity is application-enforced
- The partial unique index on `ml_model_versions(country_code) WHERE status='active'` uses `sqlalchemy.Index(..., postgresql_where=...)` syntax
- `REFRESH MATERIALIZED VIEW CONCURRENTLY` requires the unique index on `zone_statistics(zone_id)` to exist first — migration 009 must create the index before the function
