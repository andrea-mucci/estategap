# Schema Contract: EstateGap Database

**Feature**: 004-database-schema  
**Date**: 2026-04-16

This document defines the table contracts, migration dependency graph, and index catalogue that all services must treat as authoritative.

---

## Migration Dependency Graph

```
001_extensions
    └─► 002_reference_tables   (countries, portals, exchange_rates)
            └─► 003_listings    (listings partitioned + price_history)
            └─► 004_zones       (zones with geometry)
            └─► 005_users       (users)
                    └─► 006_alerts     (alert_rules + alert_log)
                    └─► 007_ai         (ai_conversations + ai_messages)
            └─► 008_ml_models   (ml_model_versions)
            └─► 009_zone_stats  (zone_statistics materialized view + refresh fn)
                    ▲ depends on zones + listings existing
002_reference_tables
    └─► 010_seed_data   (INSERT countries + portals)
```

All migrations from 002 onward depend on 001 (extensions). Migrations 003–009 depend on 002 (countries table FK). Migrations 006 and 007 depend on 005 (users table FK).

---

## Table Contracts

### Contract: `countries`

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `code` | `CHAR(2)` | NO | — | ISO 3166-1 alpha-2; natural PK |
| `name` | `VARCHAR(100)` | NO | — | English display name |
| `currency` | `CHAR(3)` | NO | — | ISO 4217 default currency |
| `active` | `BOOLEAN` | NO | `TRUE` | Inactive = not scraped |
| `config` | `JSONB` | NO | `{}` | Proxy region, scrape schedule |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | |
| `updated_at` | `TIMESTAMPTZ` | NO | `NOW()` | |

**Constraints**: PK(`code`)

---

### Contract: `portals`

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `id` | `UUID` | NO | `gen_random_uuid()` | |
| `name` | `VARCHAR(60)` | NO | — | Human-readable portal name |
| `country_code` | `CHAR(2)` | NO | — | FK → `countries(code)` |
| `base_url` | `TEXT` | NO | — | Portal root URL |
| `spider_class` | `VARCHAR(80)` | NO | — | Python class name in spider-workers |
| `enabled` | `BOOLEAN` | NO | `TRUE` | Disabled = not scheduled |
| `config` | `JSONB` | NO | `{}` | Headers, throttle, auth tokens |
| `created_at` | `TIMESTAMPTZ` | NO | `NOW()` | |
| `updated_at` | `TIMESTAMPTZ` | NO | `NOW()` | |

**Constraints**: PK(`id`), UNIQUE(`name`, `country_code`), FK(`country_code`) → `countries`  
**Indexes**: `(country_code, enabled)`

---

### Contract: `exchange_rates`

| Column | Type | Nullable | Default | Notes |
|--------|------|----------|---------|-------|
| `currency` | `CHAR(3)` | NO | — | ISO 4217 |
| `date` | `DATE` | NO | — | Rate date |
| `rate_to_eur` | `NUMERIC(12,6)` | NO | — | 1 unit of currency = N EUR |
| `fetched_at` | `TIMESTAMPTZ` | NO | `NOW()` | |

**Constraints**: PK(`currency`, `date`)  
**Query pattern**: `WHERE currency = $1 ORDER BY date DESC LIMIT 1`

---

### Contract: `listings` (partitioned)

Partitioned by `LIST(country)`. Partitions: `listings_es`, `listings_fr`, `listings_it`, `listings_pt`, `listings_de`, `listings_gb`, `listings_nl`, `listings_us`, `listings_other` (DEFAULT).

**Identity columns**:
| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | `UUID` | NO | `gen_random_uuid()` |
| `canonical_id` | `UUID` | YES | Dedup group leader |
| `country` | `CHAR(2)` | NO | Partition key; `CHECK(length(country)=2)` |
| `source` | `VARCHAR(30)` | NO | Portal identifier |
| `source_id` | `VARCHAR(80)` | NO | Portal's listing ID |
| `source_url` | `TEXT` | NO | |
| `portal_id` | `UUID` | YES | FK → `portals(id)` |

**Location columns**:
| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `address` | `TEXT` | YES | |
| `neighborhood` | `VARCHAR(100)` | YES | |
| `district` | `VARCHAR(100)` | YES | |
| `city` | `VARCHAR(100)` | YES | |
| `region` | `VARCHAR(100)` | YES | |
| `postal_code` | `VARCHAR(15)` | YES | |
| `location` | `GEOMETRY(Point,4326)` | YES | Lon/Lat WGS84 |
| `zone_id` | `UUID` | YES | Soft FK → `zones(id)` |

**Pricing columns**:
| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `asking_price` | `NUMERIC(14,2)` | YES | Source currency |
| `currency` | `CHAR(3)` | NO | Default `EUR` |
| `asking_price_eur` | `NUMERIC(14,2)` | YES | EUR normalised |
| `price_per_m2_eur` | `NUMERIC(10,2)` | YES | EUR / m² |

**Physical columns** (partial, see data-model.md for full list):
`built_area_m2`, `usable_area_m2`, `plot_area_m2`, `bedrooms`, `bathrooms`, `floor_number`, `has_lift`, `has_pool`, `has_garden`, `year_built`, `condition`, `energy_rating`

**ML score columns**:
`estimated_price`, `deal_score`, `deal_tier`, `confidence_low`, `confidence_high`, `shap_features JSONB`, `model_version`, `scored_at`

**Generated column**:
`days_on_market INTEGER GENERATED ALWAYS AS (...) STORED` — computed from `published_at` and `delisted_at`

**Metadata columns**:
`status VARCHAR(20)` (default `active`), `first_seen_at`, `last_seen_at`, `published_at`, `delisted_at`, `raw_hash CHAR(64)`, `created_at`, `updated_at`

**Constraints**: PK(`id`, `country`), UNIQUE(`source`, `source_id`, `country`)  
**Critical indexes**: GIST(`location`), partial on `deal_tier WHERE status='active'`, GIN tsvector on `description_orig`

---

### Contract: `price_history`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | `BIGSERIAL` | NO | Performance PK |
| `listing_id` | `UUID` | NO | Soft FK (no constraint on partitioned parent) |
| `country` | `CHAR(2)` | NO | For routing/filtering |
| `old_price` | `NUMERIC(14,2)` | YES | NULL on first record |
| `new_price` | `NUMERIC(14,2)` | NO | |
| `currency` | `CHAR(3)` | NO | |
| `old_price_eur` | `NUMERIC(14,2)` | YES | |
| `new_price_eur` | `NUMERIC(14,2)` | YES | |
| `change_type` | `VARCHAR(20)` | NO | `price_change`, `status_change`, `relisted` |
| `old_status` | `VARCHAR(20)` | YES | |
| `new_status` | `VARCHAR(20)` | YES | |
| `recorded_at` | `TIMESTAMPTZ` | NO | `NOW()` |
| `source` | `VARCHAR(30)` | YES | Detecting spider |

**Constraints**: PK(`id`)  
**Indexes**: `(listing_id, recorded_at DESC)`, `(country, recorded_at DESC)`  
**Insert policy**: Append-only. No UPDATE or DELETE. Application enforces this.

---

### Contract: `zones`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | `UUID` | NO | `gen_random_uuid()` |
| `name` | `VARCHAR(150)` | NO | English name |
| `name_local` | `VARCHAR(150)` | YES | Local language |
| `country_code` | `CHAR(2)` | NO | FK → `countries` |
| `level` | `SMALLINT` | NO | 0=country, 1=region, 2=province, 3=city, 4=neighbourhood |
| `parent_id` | `UUID` | YES | FK → `zones(id)` |
| `geometry` | `GEOMETRY(MultiPolygon,4326)` | YES | |
| `bbox` | `GEOMETRY(Polygon,4326)` | YES | Pre-computed bounding box |
| `slug` | `VARCHAR(200)` | YES | UNIQUE; URL identifier |
| `osm_id` | `BIGINT` | YES | OpenStreetMap ID |

**Constraints**: PK(`id`), UNIQUE(`slug`), FK(`country_code`), FK(`parent_id`)  
**Indexes**: GIST(`geometry`), GIST(`bbox`), `(country_code, level)`, `(parent_id)`

---

### Contract: `users`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | `UUID` | NO | `gen_random_uuid()` |
| `email` | `VARCHAR(255)` | NO | UNIQUE |
| `password_hash` | `VARCHAR(255)` | YES | NULL for OAuth-only users |
| `oauth_provider` | `VARCHAR(20)` | YES | `google`, `github` |
| `oauth_subject` | `VARCHAR(100)` | YES | Provider user ID |
| `display_name` | `VARCHAR(100)` | YES | |
| `subscription_tier` | `VARCHAR(20)` | NO | `free`, `starter`, `pro`, `enterprise` |
| `stripe_customer_id` | `VARCHAR(30)` | YES | UNIQUE |
| `stripe_sub_id` | `VARCHAR(30)` | YES | UNIQUE |
| `subscription_ends_at` | `TIMESTAMPTZ` | YES | |
| `alert_limit` | `SMALLINT` | NO | Default 3 (free tier) |
| `email_verified` | `BOOLEAN` | NO | Default FALSE |
| `deleted_at` | `TIMESTAMPTZ` | YES | Soft delete (GDPR) |

**Constraints**: PK(`id`), UNIQUE(`email`), UNIQUE(`stripe_customer_id`), UNIQUE(`stripe_sub_id`)

---

### Contract: `alert_rules`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | `UUID` | NO | `gen_random_uuid()` |
| `user_id` | `UUID` | NO | FK → `users(id)` ON DELETE CASCADE |
| `name` | `VARCHAR(100)` | NO | User-visible label |
| `filters` | `JSONB` | NO | Search criteria (GIN indexed) |
| `channels` | `JSONB` | NO | Notification targets |
| `active` | `BOOLEAN` | NO | Default TRUE |
| `last_triggered_at` | `TIMESTAMPTZ` | YES | |
| `trigger_count` | `INTEGER` | NO | Default 0 |

**Filters JSONB schema** (documented, not enforced in DB):
```json
{
  "country": "ES",
  "zone_ids": ["uuid1", "uuid2"],
  "property_category": "residential",
  "max_price_eur": 300000,
  "min_area_m2": 60,
  "min_deal_score": 70,
  "deal_tier_max": 2,
  "bedrooms_min": 2
}
```

**Constraints**: PK(`id`), FK(`user_id`) ON DELETE CASCADE  
**Indexes**: GIN(`filters`), `(user_id, active)`

---

### Contract: `ml_model_versions`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | `UUID` | NO | |
| `country_code` | `CHAR(2)` | NO | FK → `countries` |
| `algorithm` | `VARCHAR(30)` | NO | Default `lightgbm` |
| `version_tag` | `VARCHAR(40)` | NO | UNIQUE; e.g. `es-lightgbm-20260416-v3` |
| `artifact_path` | `TEXT` | NO | MinIO path: `models/{tag}.onnx` |
| `dataset_ref` | `TEXT` | YES | MinIO path to training data |
| `feature_names` | `JSONB` | NO | Ordered list of feature names |
| `metrics` | `JSONB` | NO | `{mae, rmse, r2, shap_top_features}` |
| `status` | `VARCHAR(20)` | NO | `staging`, `active`, `retired` |
| `trained_at` | `TIMESTAMPTZ` | NO | |

**Constraints**: PK(`id`), UNIQUE(`version_tag`), PARTIAL UNIQUE(`country_code`) WHERE `status='active'`  
**Indexes**: `(country_code, status)`

---

## Index Catalogue

| Table | Index Type | Columns | Condition | Purpose |
|-------|-----------|---------|-----------|---------|
| `listings` | GIST | `location` | — | Spatial proximity queries |
| `listings` | BTREE | `(country, status)` | — | Country + status filter |
| `listings` | BTREE | `(city, status)` | `WHERE status='active'` | City search |
| `listings` | BTREE | `deal_tier` | `WHERE status='active'` | Deal tier filter |
| `listings` | GIN | `to_tsvector(description_orig)` | — | Full-text search |
| `listings` | BTREE | `zone_id` | `WHERE zone_id IS NOT NULL` | Zone lookup |
| `price_history` | BTREE | `(listing_id, recorded_at DESC)` | — | Timeline retrieval |
| `price_history` | BTREE | `(country, recorded_at DESC)` | — | Country-level history |
| `zones` | GIST | `geometry` | — | Spatial containment |
| `zones` | GIST | `bbox` | — | Bounding box pre-filter |
| `zones` | BTREE | `(country_code, level)` | — | Hierarchy navigation |
| `alert_rules` | GIN | `filters` | — | `@>` containment matching |
| `alert_rules` | BTREE | `(user_id, active)` | — | User's active rules |
| `alert_log` | BTREE | `(rule_id, sent_at DESC)` | — | Rule delivery history |
| `ai_conversations` | BTREE | `(user_id, status)` | — | Active sessions |
| `ai_messages` | BTREE | `(conversation_id, id)` | — | Message pagination |
| `ml_model_versions` | BTREE | `(country_code, status)` | — | Active model lookup |
| `ml_model_versions` | UNIQUE | `country_code` | `WHERE status='active'` | One active per country |
| `zone_statistics` | UNIQUE | `zone_id` | — | Required for CONCURRENTLY |
| `zone_statistics` | BTREE | `country_code` | — | Country filter on view |
