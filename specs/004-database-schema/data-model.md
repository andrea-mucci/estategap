# Data Model: PostgreSQL Database Schema

**Feature**: 004-database-schema  
**Date**: 2026-04-16

---

## Entity Relationship Overview

```
countries (1) ──< portals (*)
countries (1) ──< listings (*)       [partitioned by country]
countries (1) ──< zones (*)

listings (1) ──< price_history (*)
listings (*) >── zones (1)           [optional zone_id FK]

users (1) ──< alert_rules (*)
alert_rules (1) ──< alert_log (*)

users (1) ──< ai_conversations (*)
ai_conversations (1) ──< ai_messages (*)
ai_conversations (1) ──o alert_rules (1)   [optional created alert]

ml_model_versions: standalone registry

zones (1) ──o zones (*)              [self-referencing parent_id]
zone_statistics: materialized view over listings + zones
```

---

## Table Definitions

### `countries`

```sql
CREATE TABLE countries (
    code         CHAR(2)      PRIMARY KEY,           -- ISO 3166-1 alpha-2
    name         VARCHAR(100) NOT NULL,
    currency     CHAR(3)      NOT NULL,              -- ISO 4217
    active       BOOLEAN      NOT NULL DEFAULT TRUE,
    config       JSONB        NOT NULL DEFAULT '{}', -- scraping schedule, proxy region
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);
```

**Notes**: Natural PK (country code). Config JSONB holds portal-agnostic per-country settings (e.g. `{"proxy_region": "eu-west", "scrape_interval_hours": 24}`).

---

### `portals`

```sql
CREATE TABLE portals (
    id            UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    name          VARCHAR(60)  NOT NULL,
    country_code  CHAR(2)      NOT NULL REFERENCES countries(code),
    base_url      TEXT         NOT NULL,
    spider_class  VARCHAR(80)  NOT NULL,             -- Python class name in spider-workers
    enabled       BOOLEAN      NOT NULL DEFAULT TRUE,
    config        JSONB        NOT NULL DEFAULT '{}', -- throttle, headers, auth
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    UNIQUE(name, country_code)
);

CREATE INDEX ON portals (country_code, enabled);
```

---

### `exchange_rates`

```sql
CREATE TABLE exchange_rates (
    currency     CHAR(3)        NOT NULL,            -- ISO 4217
    date         DATE           NOT NULL,
    rate_to_eur  NUMERIC(12,6)  NOT NULL,
    fetched_at   TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    PRIMARY KEY (currency, date)
);
```

**Notes**: Append-only. Application selects `WHERE date = (SELECT MAX(date) FROM exchange_rates WHERE currency = $1)`.

---

### `listings` (partitioned)

```sql
CREATE TABLE listings (
    -- Identity
    id               UUID         NOT NULL DEFAULT gen_random_uuid(),
    canonical_id     UUID,                           -- dedup group leader
    country          CHAR(2)      NOT NULL,
    source           VARCHAR(30)  NOT NULL,          -- portal name (idealista, seloger…)
    source_id        VARCHAR(80)  NOT NULL,
    source_url       TEXT         NOT NULL,
    portal_id        UUID         REFERENCES portals(id),

    -- Location
    address          TEXT,
    neighborhood     VARCHAR(100),
    district         VARCHAR(100),
    city             VARCHAR(100),
    region           VARCHAR(100),
    postal_code      VARCHAR(15),
    location         GEOMETRY(Point, 4326),
    zone_id          UUID,                           -- FK to zones (no FK constraint on partitioned table)

    -- Pricing (dual currency)
    asking_price     NUMERIC(14,2),
    currency         CHAR(3)      NOT NULL DEFAULT 'EUR',
    asking_price_eur NUMERIC(14,2),
    price_per_m2_eur NUMERIC(10,2),

    -- Physical
    property_category VARCHAR(20),                  -- residential, commercial, industrial, land
    property_type     VARCHAR(30),                  -- apartment, villa, office, warehouse, plot…
    built_area        NUMERIC(10,2),
    area_unit         VARCHAR(5)   DEFAULT 'm2',     -- m2 or sqft
    built_area_m2     NUMERIC(10,2),
    usable_area_m2    NUMERIC(10,2),
    plot_area_m2      NUMERIC(12,2),
    bedrooms          SMALLINT,
    bathrooms         SMALLINT,
    toilets           SMALLINT,
    floor_number      SMALLINT,
    total_floors      SMALLINT,
    parking_spaces    SMALLINT,
    has_lift          BOOLEAN,
    has_pool          BOOLEAN,
    has_garden        BOOLEAN,
    terrace_area_m2   NUMERIC(8,2),
    garage_area_m2    NUMERIC(8,2),

    -- Condition
    year_built        SMALLINT,
    last_renovated    SMALLINT,
    condition         VARCHAR(20),                  -- new, good, needs_renovation, ruin
    energy_rating     CHAR(1),                      -- A–G
    energy_rating_kwh NUMERIC(8,2),
    co2_rating        CHAR(1),
    co2_kg_m2         NUMERIC(8,2),

    -- Commercial / Industrial (nullable)
    frontage_m        NUMERIC(6,2),
    ceiling_height_m  NUMERIC(4,2),
    loading_docks     SMALLINT,
    power_kw          NUMERIC(8,2),
    office_area_m2    NUMERIC(10,2),
    warehouse_area_m2 NUMERIC(10,2),

    -- Land (nullable)
    buildability_index   NUMERIC(4,2),
    urban_classification VARCHAR(30),
    land_use             VARCHAR(30),

    -- ML scores
    estimated_price   NUMERIC(14,2),
    deal_score        NUMERIC(5,2),
    deal_tier         SMALLINT,                     -- 1 (best) – 5 (worst)
    confidence_low    NUMERIC(14,2),
    confidence_high   NUMERIC(14,2),
    shap_features     JSONB,                        -- top SHAP values array
    model_version     VARCHAR(30),
    scored_at         TIMESTAMPTZ,

    -- Generated
    days_on_market    INTEGER GENERATED ALWAYS AS (
        EXTRACT(DAY FROM COALESCE(delisted_at, NOW()) - published_at)::INTEGER
    ) STORED,

    -- Metadata
    status            VARCHAR(20)  NOT NULL DEFAULT 'active', -- active, sold, withdrawn, expired
    description_orig  TEXT,
    description_lang  CHAR(2),
    images_count      SMALLINT     DEFAULT 0,
    first_seen_at     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    last_seen_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    published_at      TIMESTAMPTZ,
    delisted_at       TIMESTAMPTZ,
    raw_hash          CHAR(64),                     -- SHA-256 of raw JSON for dedup
    created_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at        TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

    PRIMARY KEY (id, country),
    UNIQUE (source, source_id, country)
) PARTITION BY LIST (country);

-- Partitions
CREATE TABLE listings_es    PARTITION OF listings FOR VALUES IN ('ES');
CREATE TABLE listings_fr    PARTITION OF listings FOR VALUES IN ('FR');
CREATE TABLE listings_it    PARTITION OF listings FOR VALUES IN ('IT');
CREATE TABLE listings_pt    PARTITION OF listings FOR VALUES IN ('PT');
CREATE TABLE listings_de    PARTITION OF listings FOR VALUES IN ('DE');
CREATE TABLE listings_gb    PARTITION OF listings FOR VALUES IN ('GB');
CREATE TABLE listings_nl    PARTITION OF listings FOR VALUES IN ('NL');
CREATE TABLE listings_us    PARTITION OF listings FOR VALUES IN ('US');
CREATE TABLE listings_other PARTITION OF listings DEFAULT;

-- Indexes (inherited by all partitions)
CREATE INDEX ON listings USING GIST (location);
CREATE INDEX ON listings (country, status);
CREATE INDEX ON listings (city, status) WHERE status = 'active';
CREATE INDEX ON listings (deal_tier)    WHERE status = 'active';
CREATE INDEX ON listings USING GIN (to_tsvector('simple', COALESCE(description_orig, '')));
CREATE INDEX ON listings (zone_id)      WHERE zone_id IS NOT NULL;
CREATE INDEX ON listings (scored_at)    WHERE scored_at IS NOT NULL;
```

**Notes on partitioned FK**: PostgreSQL does not support foreign key constraints referencing partitioned tables. `zone_id` is stored without a FK constraint; referential integrity enforced at application level. `portal_id` references the non-partitioned `portals` table and is valid as an FK.

---

### `price_history`

```sql
CREATE TABLE price_history (
    id           BIGSERIAL    PRIMARY KEY,
    listing_id   UUID         NOT NULL,
    country      CHAR(2)      NOT NULL,             -- for routing; no FK on partitioned parent
    old_price    NUMERIC(14,2),
    new_price    NUMERIC(14,2) NOT NULL,
    currency     CHAR(3)      NOT NULL,
    old_price_eur NUMERIC(14,2),
    new_price_eur NUMERIC(14,2),
    change_type  VARCHAR(20)  NOT NULL DEFAULT 'price_change', -- price_change, status_change, relisted
    old_status   VARCHAR(20),
    new_status   VARCHAR(20),
    recorded_at  TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    source       VARCHAR(30)                        -- which spider detected this change
);

CREATE INDEX ON price_history (listing_id, recorded_at DESC);
CREATE INDEX ON price_history (country, recorded_at DESC);
```

---

### `zones`

```sql
CREATE TABLE zones (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    name         VARCHAR(150) NOT NULL,
    name_local   VARCHAR(150),                      -- local language name
    country_code CHAR(2)      NOT NULL REFERENCES countries(code),
    level        SMALLINT     NOT NULL,             -- 0=country, 1=region, 2=province/dept, 3=city, 4=neighbourhood
    parent_id    UUID         REFERENCES zones(id),
    geometry     GEOMETRY(MultiPolygon, 4326),
    bbox         GEOMETRY(Polygon, 4326),           -- bounding box for fast pre-filter
    population   INTEGER,
    area_km2     NUMERIC(10,2),
    slug         VARCHAR(200) UNIQUE,               -- URL-safe identifier
    osm_id       BIGINT,                            -- OpenStreetMap reference
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX ON zones USING GIST (geometry);
CREATE INDEX ON zones USING GIST (bbox);
CREATE INDEX ON zones (country_code, level);
CREATE INDEX ON zones (parent_id) WHERE parent_id IS NOT NULL;
CREATE INDEX ON zones (slug);
```

---

### `users`

```sql
CREATE TABLE users (
    id                  UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    email               VARCHAR(255) NOT NULL UNIQUE,
    password_hash       VARCHAR(255),               -- NULL if OAuth-only
    oauth_provider      VARCHAR(20),                -- google, github, NULL
    oauth_subject       VARCHAR(100),               -- provider's user ID
    display_name        VARCHAR(100),
    avatar_url          TEXT,
    subscription_tier   VARCHAR(20)  NOT NULL DEFAULT 'free', -- free, starter, pro, enterprise
    stripe_customer_id  VARCHAR(30)  UNIQUE,
    stripe_sub_id       VARCHAR(30)  UNIQUE,
    subscription_ends_at TIMESTAMPTZ,
    alert_limit         SMALLINT     NOT NULL DEFAULT 3,
    email_verified      BOOLEAN      NOT NULL DEFAULT FALSE,
    email_verified_at   TIMESTAMPTZ,
    last_login_at       TIMESTAMPTZ,
    deleted_at          TIMESTAMPTZ,                -- soft delete (GDPR)
    created_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX ON users (email) WHERE deleted_at IS NULL;
CREATE INDEX ON users (stripe_customer_id) WHERE stripe_customer_id IS NOT NULL;
CREATE INDEX ON users (oauth_provider, oauth_subject) WHERE oauth_provider IS NOT NULL;
```

---

### `alert_rules`

```sql
CREATE TABLE alert_rules (
    id               UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id          UUID         NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name             VARCHAR(100) NOT NULL,
    filters          JSONB        NOT NULL DEFAULT '{}',
    -- filters shape: {country, zone_ids[], property_category, max_price_eur,
    --                 min_area_m2, min_deal_score, deal_tier_max, bedrooms_min}
    channels         JSONB        NOT NULL DEFAULT '{"email": true}',
    -- channels shape: {email, push, sms, telegram}
    active           BOOLEAN      NOT NULL DEFAULT TRUE,
    last_triggered_at TIMESTAMPTZ,
    trigger_count    INTEGER      NOT NULL DEFAULT 0,
    created_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX ON alert_rules USING GIN (filters);
CREATE INDEX ON alert_rules (user_id, active);
CREATE INDEX ON alert_rules (active, last_triggered_at) WHERE active = TRUE;
```

---

### `alert_log`

```sql
CREATE TABLE alert_log (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id      UUID         NOT NULL REFERENCES alert_rules(id) ON DELETE CASCADE,
    listing_id   UUID         NOT NULL,
    country      CHAR(2)      NOT NULL,
    channel      VARCHAR(20)  NOT NULL,             -- email, push, sms, telegram
    status       VARCHAR(20)  NOT NULL DEFAULT 'pending', -- pending, sent, failed, suppressed
    error_message TEXT,
    sent_at      TIMESTAMPTZ,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX ON alert_log (rule_id, sent_at DESC);
CREATE INDEX ON alert_log (listing_id);
CREATE INDEX ON alert_log (status, created_at) WHERE status = 'pending';
```

---

### `ai_conversations`

```sql
CREATE TABLE ai_conversations (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id        UUID        REFERENCES users(id) ON DELETE SET NULL,
    language       CHAR(2)     NOT NULL DEFAULT 'en',
    criteria_state JSONB       NOT NULL DEFAULT '{}',  -- latest merged criteria snapshot
    alert_rule_id  UUID        REFERENCES alert_rules(id) ON DELETE SET NULL,
    turn_count     SMALLINT    NOT NULL DEFAULT 0,
    status         VARCHAR(20) NOT NULL DEFAULT 'active', -- active, completed, abandoned
    model_used     VARCHAR(60),                       -- e.g. claude-opus-4-6
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ON ai_conversations (user_id, status);
CREATE INDEX ON ai_conversations (status, updated_at) WHERE status = 'active';
```

---

### `ai_messages`

```sql
CREATE TABLE ai_messages (
    id               BIGSERIAL   PRIMARY KEY,
    conversation_id  UUID        NOT NULL REFERENCES ai_conversations(id) ON DELETE CASCADE,
    role             VARCHAR(10) NOT NULL CHECK (role IN ('user', 'assistant', 'system')),
    content          TEXT        NOT NULL,
    criteria_snapshot JSONB      NOT NULL DEFAULT '{}', -- criteria state after this turn
    visual_refs      JSONB       NOT NULL DEFAULT '[]', -- listing IDs shown to user
    tokens_used      INTEGER,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ON ai_messages (conversation_id, id);
```

---

### `ml_model_versions`

```sql
CREATE TABLE ml_model_versions (
    id             UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    country_code   CHAR(2)     NOT NULL REFERENCES countries(code),
    algorithm      VARCHAR(30) NOT NULL DEFAULT 'lightgbm',
    version_tag    VARCHAR(40) NOT NULL UNIQUE,      -- e.g. es-lightgbm-20260416-v3
    artifact_path  TEXT        NOT NULL,             -- MinIO path: models/{version_tag}.onnx
    dataset_ref    TEXT,                             -- MinIO path to training dataset
    feature_names  JSONB       NOT NULL DEFAULT '[]',
    metrics        JSONB       NOT NULL DEFAULT '{}',
    -- metrics shape: {mae, rmse, r2, mape, shap_top_features[{name, mean_abs_shap}]}
    status         VARCHAR(20) NOT NULL DEFAULT 'staging', -- staging, active, retired
    trained_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    promoted_at    TIMESTAMPTZ,
    retired_at     TIMESTAMPTZ,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ON ml_model_versions (country_code, status);
CREATE UNIQUE INDEX ON ml_model_versions (country_code) WHERE status = 'active';
-- ^^ enforces only one active model per country at the DB level
```

---

### `zone_statistics` (materialized view)

```sql
CREATE MATERIALIZED VIEW zone_statistics AS
SELECT
    z.id                                          AS zone_id,
    z.country_code,
    z.name                                        AS zone_name,
    COUNT(*)                                      AS listing_count,
    COUNT(*) FILTER (WHERE l.status = 'active')   AS active_listings,
    PERCENTILE_CONT(0.5) WITHIN GROUP (
        ORDER BY l.price_per_m2_eur
    )                                             AS median_price_m2_eur,
    SUM(l.asking_price_eur)                       AS total_volume_eur,
    AVG(l.deal_score)                             AS avg_deal_score,
    MIN(l.asking_price_eur)                       AS min_price_eur,
    MAX(l.asking_price_eur)                       AS max_price_eur,
    NOW()                                         AS refreshed_at
FROM zones z
JOIN listings l ON l.zone_id = z.id
WHERE l.status = 'active'
  AND l.price_per_m2_eur IS NOT NULL
GROUP BY z.id, z.country_code, z.name
WITH DATA;

CREATE UNIQUE INDEX ON zone_statistics (zone_id);
CREATE INDEX ON zone_statistics (country_code);

-- Refresh function
CREATE OR REPLACE FUNCTION refresh_zone_statistics()
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY zone_statistics;
END;
$$;
```

---

## State Transitions

### Listing Status

```
scraped → active → sold
                 → withdrawn
                 → expired
sold     → active  (relisted)
withdrawn → active (relisted)
```

State changes are always recorded in `price_history` with `change_type = 'status_change'`.

### AI Conversation Status

```
active → completed  (user saves an alert rule)
active → abandoned  (timeout or explicit close)
```

### ML Model Status

```
staging → active    (promoted by ML pipeline)
active  → retired   (superseded by new active model)
```

---

## Pydantic Model Mapping

| DB Table | Pydantic Model | Module |
|----------|---------------|--------|
| `countries` | `Country` | `libs/common/estategap_common/models/reference.py` (NEW) |
| `portals` | `Portal` | `libs/common/estategap_common/models/reference.py` (NEW) |
| `exchange_rates` | `ExchangeRate` | `libs/common/estategap_common/models/reference.py` (NEW) |
| `listings` | `Listing` | `libs/common/estategap_common/models/listing.py` (EXTEND) |
| `price_history` | `PriceChange` | `libs/common/estategap_common/models/listing.py` (NEW class) |
| `zones` | `Zone` | `libs/common/estategap_common/models/zone.py` (EXTEND) |
| `users` | `User`, `SubscriptionTier` | `libs/common/estategap_common/models/user.py` (NEW) |
| `alert_rules` | `AlertRule` | `libs/common/estategap_common/models/alert.py` (EXTEND) |
| `alert_log` | `AlertLog` | `libs/common/estategap_common/models/alert.py` (NEW class) |
| `ai_conversations` | `ConversationState` | `libs/common/estategap_common/models/conversation.py` (EXTEND) |
| `ai_messages` | `ChatMessage` | `libs/common/estategap_common/models/conversation.py` (EXTEND) |
| `ml_model_versions` | `MlModelVersion` | `libs/common/estategap_common/models/ml.py` (NEW) |
