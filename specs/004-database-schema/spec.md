# Feature Specification: PostgreSQL Database Schema

**Feature Branch**: `004-database-schema`  
**Created**: 2026-04-16  
**Status**: Draft  
**Input**: User description: "Create the complete PostgreSQL database schema for the EstateGap platform."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Platform Services Can Store and Query Listings (Priority: P1)

A pipeline service writes a newly scraped and normalised property listing to the database. A query service reads listings filtered by country, deal tier, and geographic bounding box and returns results in under a second.

**Why this priority**: Listings are the core entity of the platform. No other feature — scoring, alerts, AI search — works without reliable listing storage and retrieval.

**Independent Test**: Can be tested by inserting a listing row into a country partition and running a spatial query with a country filter. Delivers core data persistence value independently.

**Acceptance Scenarios**:

1. **Given** a fresh PostgreSQL + PostGIS database with migrations applied, **When** a listing is inserted with country = 'ES', **Then** the row lands in the `listings_es` partition and can be retrieved by querying `listings` with `WHERE country = 'ES'`
2. **Given** a listing with a geometry point and a deal_tier of 1, **When** a query filters `WHERE status = 'active' AND deal_tier = 1`, **Then** the partial index is used and the query returns results in under 200 ms on a warm database
3. **Given** the same (source, source_id) pair inserted twice, **When** the second insert is attempted, **Then** a unique constraint violation is raised preventing duplicate portal listings

---

### User Story 2 - Price Changes Are Tracked Over Time (Priority: P2)

When the pipeline detects a price change on an existing listing, it appends a row to the price history table. Analysts and services can retrieve the full price timeline for any listing.

**Why this priority**: Price history is the primary signal for the deal-scoring algorithm and is required for trend charts in the frontend.

**Independent Test**: Insert a listing, insert two price_history rows with different timestamps, query ordered by `recorded_at DESC`. Delivers the audit trail independently.

**Acceptance Scenarios**:

1. **Given** an existing listing, **When** a new price is recorded in `price_history`, **Then** the row is appended without modifying the parent listing row
2. **Given** multiple price records for one listing, **When** querying `ORDER BY recorded_at DESC`, **Then** results are returned in correct chronological order using the composite index

---

### User Story 3 - Users Can Register and Manage Alert Rules (Priority: P3)

A user account is created. The user defines a saved search (alert rule) with country, zone, price ceiling, and property type filters stored as JSONB. The platform evaluates the rule against new listings.

**Why this priority**: User accounts and alerts are the monetisation layer. Required before the alert engine can function end-to-end.

**Independent Test**: Create a user row, insert an alert_rule with JSONB filters, query alert_rules by user_id. Delivers user + alert storage independently.

**Acceptance Scenarios**:

1. **Given** a new user row, **When** an alert rule is inserted referencing that user, **Then** the FK constraint is satisfied and the rule is queryable by `user_id`
2. **Given** an alert that fires, **When** a row is inserted into `alert_log`, **Then** the delivery channel, status, and timestamp are persisted correctly

---

### User Story 4 - AI Conversations Are Persisted Per Turn (Priority: P4)

An AI chat session stores the evolving search criteria in a JSONB snapshot per message turn. Services can resume a conversation from any prior state by reading the latest `criteria_state`.

**Why this priority**: Conversation state persistence is required for the AI search service to maintain context across WebSocket reconnects.

**Independent Test**: Create an `ai_conversations` row, insert two `ai_messages` with different `criteria_snapshot` values, confirm the latest snapshot is retrievable. Delivers AI session persistence independently.

**Acceptance Scenarios**:

1. **Given** an active conversation, **When** a new user message is appended, **Then** the `turn_count` increments and `criteria_snapshot` stores the latest parsed filters
2. **Given** a completed conversation, **When** the status is set to 'completed', **Then** no further messages can be appended via application logic

---

### User Story 5 - ML Model Versions Are Registered (Priority: P5)

After training, a new ML model version is registered with metrics and artifact paths. The scorer service queries the registry to load the correct per-country model.

**Why this priority**: Model versioning is required before the ML pipeline can safely deploy new models without downtime.

**Independent Test**: Insert an `ml_model_versions` row with country, version tag, ONNX artifact path, and metrics JSONB. Query by country and status = 'active'. Delivers model registry independently.

**Acceptance Scenarios**:

1. **Given** a trained model, **When** its version row is inserted, **Then** metrics (MAE, RMSE, SHAP feature importance) are stored as JSONB and queryable
2. **Given** two model versions for the same country, **When** one is promoted to active, **Then** only one row has `status = 'active'` for that country at any time (enforced by application or partial unique index)

---

### User Story 6 - Zone Statistics Materialized View Is Refreshed (Priority: P6)

The frontend requests zone-level statistics (median price/m², deal count, total volume). The materialized view `zone_statistics` is refreshed on a schedule and serves pre-aggregated data without a full table scan.

**Why this priority**: Zone statistics power the choropleth map and price heatmap. Without materialized views these queries would be prohibitively slow on millions of listings.

**Independent Test**: Insert listings for a zone, call the `refresh_zone_statistics()` function, query `zone_statistics`. Delivers pre-aggregated zone data independently.

**Acceptance Scenarios**:

1. **Given** listings with zone assignments, **When** `SELECT refresh_zone_statistics()` is called, **Then** `zone_statistics` reflects current aggregates within the same transaction
2. **Given** a zone with no active listings, **When** the view is refreshed, **Then** the zone row is absent from `zone_statistics`

---

### Edge Cases

- What happens when a listing's country is not one of the eight explicit partitions (ES, FR, IT, PT, DE, GB, NL, US)? → Row falls into `listings_other` (DEFAULT partition)
- How does the schema handle areas in square feet (US listings)? → `built_area` + `area_unit` stored as-is; `built_area_m2` holds the normalised value
- What happens if PostGIS extension is not installed before the migration runs? → Migration fails with a clear extension error; migration 001 must run first
- How are stale exchange rates handled? → `exchange_rates` has a `date` column; application selects the most recent rate per currency; no uniqueness constraint blocks historical inserts
- What happens if `zone_statistics` is queried during a concurrent refresh? → `REFRESH MATERIALIZED VIEW CONCURRENTLY` is used to allow reads during refresh

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST create all tables via versioned, reversible Alembic migrations that apply cleanly on a fresh PostgreSQL 16 + PostGIS 3.4 database
- **FR-002**: The `listings` table MUST be partitioned by LIST on the `country` column with named partitions for ES, FR, IT, PT, DE, GB, NL, US, and a DEFAULT partition for all other countries
- **FR-003**: All geometry columns MUST use SRID 4326 and be indexed with GIST indexes for spatial query performance
- **FR-004**: `price_history` MUST be an append-only table with a composite index on `(listing_id, recorded_at DESC)` to support efficient timeline retrieval
- **FR-005**: The `zones` table MUST support hierarchical self-referencing via `parent_id` to represent country → region → city → neighbourhood levels
- **FR-006**: User accounts MUST store subscription tier and Stripe customer/subscription IDs to support billing integration
- **FR-007**: Alert rules MUST store filter criteria as JSONB to allow flexible, schema-free search parameters without future migrations
- **FR-008**: AI conversation messages MUST capture a `criteria_snapshot` JSONB per turn to allow conversation replay and context recovery
- **FR-009**: ML model versions MUST record country, algorithm, artifact path, training dataset reference, and a metrics JSONB blob
- **FR-010**: A `zone_statistics` materialized view MUST aggregate median price/m², listing count, and total volume per zone, refreshable via a stored function
- **FR-011**: A seed data migration MUST insert the 5 priority countries (ES, IT, PT, FR, GB) and 10 priority portals on first apply
- **FR-012**: All down-migrations MUST reverse their corresponding up-migration without data loss for empty tables
- **FR-013**: The `(source, source_id)` composite unique constraint on `listings` MUST prevent duplicate portal listings across all partitions
- **FR-014**: A partial index on `deal_tier WHERE status = 'active'` MUST exist to support fast active-listing deal-tier queries

### Key Entities

- **Country**: Reference entity with ISO 3166-1 code, display name, default currency, active flag, and JSONB config (scraping schedule, proxy region, etc.)
- **Portal**: Scraping source associated with a country; holds spider class name, base URL, enabled flag, and JSONB config
- **ExchangeRate**: Daily EUR conversion rate per currency code; append-only with date dimension
- **Listing**: Core property entity partitioned by country; 50+ attributes covering location, pricing (dual currency), physical attributes, condition, type-specific fields, ML scores, and lifecycle metadata
- **PriceHistory**: Immutable price event record linked to a listing; captures old and new price, currency, and change timestamp
- **Zone**: Geographic administrative area with MultiPolygon geometry; self-referencing hierarchy (country → region → city → neighbourhood)
- **User**: Platform account with hashed password, OAuth provider link, subscription tier, and Stripe billing identifiers
- **AlertRule**: User-defined saved search with JSONB filter criteria and notification channel preferences; linked to a zone and user
- **AlertLog**: Delivery record for each alert notification sent; tracks channel, status, and timestamps
- **AiConversation**: Chat session entity tracking turn count, status, and the latest consolidated criteria state
- **AiMessage**: Individual message within a conversation; stores role, content, criteria snapshot, and token count
- **MlModelVersion**: Versioned model registration entry per country; stores artifact paths, training metadata, and evaluation metrics
- **ZoneStatistics**: Materialized view row per zone with aggregated price and volume metrics

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 10 migrations apply in sequence on a fresh database in under 60 seconds
- **SC-002**: All 10 down-migrations reverse cleanly, leaving the database in its pre-migration state
- **SC-003**: A `EXPLAIN (ANALYZE, BUFFERS)` query for listings filtered by a single country shows partition pruning — only one partition is scanned
- **SC-004**: Spatial queries using a bounding box on `listings.location` use the GIST index (no sequential scan on the geometry column)
- **SC-005**: Insert and SELECT round-trips succeed for every table in the schema including seed data rows
- **SC-006**: The `zone_statistics` view returns correct aggregates immediately after `refresh_zone_statistics()` is called with test data
- **SC-007**: The `(source, source_id)` uniqueness constraint rejects a duplicate insert with a constraint violation error

## Assumptions

- PostgreSQL 16 and PostGIS 3.4 are available in the target database; the migration tool does not provision the database engine itself
- The Alembic migration runner executes as a database role with CREATE, ALTER, DROP, and EXTENSION privileges
- `gen_random_uuid()` is available via the `pgcrypto` extension enabled in migration 001
- Exchange rates are populated by a separate batch job; the schema only provides the table structure
- Sub-partitioning by city (HASH) is out of scope for this feature and will be added as a future migration when a country partition exceeds 5 million rows
- The materialized view refresh cadence is configured at the application/scheduler level; this feature only defines the view and the refresh function
- Alembic is managed from within `services/pipeline/` alongside the data pipeline service that owns schema migrations
- Go struct models in `libs/pkg/` will be added in a follow-on task once the Python Pydantic models are validated against the live schema
