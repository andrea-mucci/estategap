# Feature: Core Database Schema & Migrations

## /plan prompt

```
Implement the database schema with these technical decisions:

## Stack
- Alembic for migrations, managed from services/pipeline/ (Python)
- asyncpg as the async PostgreSQL driver
- SQLAlchemy 2.0 for model definitions (used for migration generation, not as runtime ORM)
- PostGIS 3.4 via CREATE EXTENSION postgis

## Partitioning Strategy
- listings table: PARTITION BY LIST (country) with explicit partitions per country code
- Each partition can optionally be sub-partitioned by city using PARTITION BY HASH if a single country exceeds 5M rows
- price_history: regular table with index on (listing_id, recorded_at DESC)

## Key Design Decisions
- UUIDs (gen_random_uuid()) for all primary keys except price_history (BIGSERIAL for performance)
- JSONB columns for: portal config, alert filters, ML metrics, criteria snapshots, SHAP features
- Generated column: days_on_market computed from published_at and delisted_at
- Composite unique: (source, source_id) on listings to prevent duplicates per portal
- PostGIS GIST indexes on all geometry columns
- Partial indexes: deal_tier index only WHERE status = 'active'
- Text search: GIN index on description for future full-text search

## Migrations Order
1. Enable extensions (postgis, pg_trgm, pgcrypto)
2. countries + portals + exchange_rates (reference data)
3. listings (partitioned) + price_history
4. zones (with geometry)
5. users + subscriptions
6. alert_rules + alert_log
7. ai_conversations + ai_messages
8. model_versions
9. materialized view zone_statistics + refresh function
10. Seed data migration

## Shared Models
- Python Pydantic models in libs/common/models/ mirror the DB schema
- Go structs in pkg/models/ for API serialization
```
