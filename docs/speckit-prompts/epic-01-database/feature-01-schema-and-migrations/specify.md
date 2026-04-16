# Feature: Core Database Schema & Migrations

## /specify prompt

```
Create the complete PostgreSQL database schema for the EstateGap platform.

## What
A set of Alembic migrations that create all tables needed for the platform:

1. Reference tables: countries (code, name, currency, active, config), portals (name, country FK, base_url, spider_class, enabled, config), exchange_rates (currency, rate_to_eur, date)
2. Listings table: partitioned by country (LIST partitioning) with partitions for ES, FR, IT, PT, DE, GB, NL, US, and DEFAULT. Contains 50+ columns covering identity, location (PostGIS Point), pricing (dual currency), physical attributes, condition, type, commercial/industrial/land-specific fields (nullable), ML scores, and metadata. Full schema defined in architecture document.
3. Price history: append-only table tracking all price changes per listing.
4. Zones: hierarchical geographic zones with PostGIS MultiPolygon geometry and self-referencing parent_id.
5. Users & subscriptions: user accounts with auth fields, subscription tier, Stripe IDs.
6. Alert rules & alert log: user-defined search rules with JSONB filters, notification tracking.
7. AI conversations & messages: conversation state with JSONB criteria snapshots per turn.
8. ML model versions: model registry with metrics JSONB, artifact paths.
9. Materialized views: zone_statistics aggregating median price/m², deal counts, volume per zone.

## Why
This is the foundational data layer. Every service reads from or writes to this schema. Partitioning by country is essential for query performance as the platform scales to millions of listings across 15+ countries.

## Acceptance Criteria
- All migrations run successfully via `alembic upgrade head` on a fresh PostgreSQL+PostGIS database
- Seed data: 5 countries (ES, IT, PT, FR, GB) and 10 priority portals inserted
- PostGIS spatial indexes on listings.location and zones.geometry work correctly
- Partition pruning verified via EXPLAIN on queries filtered by country
- Insert and query operations tested for every table
- Rollback migrations exist and work for all schema changes
```
