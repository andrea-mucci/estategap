# Data Model: Alert Engine (016)

**Date**: 2026-04-17
**Branch**: `016-alert-engine`

---

## Existing Tables (read-only from alert engine)

### `alert_rules` (existing + migration required)

The alert engine reads this table. One migration is required to add the `frequency` column.

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | `gen_random_uuid()` |
| `user_id` | UUID FK → users(id) CASCADE | |
| `name` | VARCHAR(255) | |
| `zone_ids` | UUID[] | zones the rule applies to; empty = country-wide |
| `category` | VARCHAR(50) | residential / commercial / industrial / land |
| `filter` | JSONB | `RuleFilter` struct (see below) |
| `channels` | JSONB | `[{type, webhook_url?}]` |
| `frequency` | VARCHAR(10) NOT NULL DEFAULT 'instant' | **NEW** — instant / hourly / daily |
| `is_active` | BOOLEAN | soft-delete flag |
| `created_at` | TIMESTAMPTZ | |
| `updated_at` | TIMESTAMPTZ | |

**Migration**: `014_alert_rules_add_frequency.py` (Alembic, pipeline service)
```sql
ALTER TABLE alert_rules ADD COLUMN frequency VARCHAR(10) NOT NULL DEFAULT 'instant';
ALTER TABLE alert_rules ADD CONSTRAINT alert_rules_frequency_check
    CHECK (frequency IN ('instant', 'hourly', 'daily'));
CREATE INDEX idx_alert_rules_frequency ON alert_rules (frequency) WHERE is_active = TRUE;
```

#### `filter` JSONB Structure (`RuleFilter`)

```json
{
  "property_type": "residential",
  "price_min": 100000,
  "price_max": 500000,
  "area_min": 50,
  "area_max": 200,
  "bedrooms_min": 2,
  "bedrooms_max": 4,
  "deal_tier_max": 2,
  "features": ["parking", "garden"]
}
```

All fields are optional. Omitted fields are not evaluated (match any value).

`deal_tier_max`: integer 1–4. A listing matches if `listing.deal_tier <= deal_tier_max` (lower = better deal).

#### `channels` JSONB Structure

```json
[
  {"type": "email"},
  {"type": "push"},
  {"type": "webhook", "webhook_url": "https://..."}
]
```

Supported types: `email`, `push`, `webhook`.

---

### `alert_history` (existing — alert engine writes)

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | `gen_random_uuid()` |
| `rule_id` | UUID FK → alert_rules(id) CASCADE | |
| `listing_id` | UUID | |
| `channel` | VARCHAR(50) | email / push / webhook |
| `delivery_status` | VARCHAR(20) | pending (written by engine) |
| `error_detail` | TEXT | null on write |
| `delivered_at` | TIMESTAMPTZ | null on write (updated by dispatcher) |
| `triggered_at` | TIMESTAMPTZ | NOW() |

---

### `zones` (existing — alert engine reads for geometry)

| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `country_code` | VARCHAR(2) | |
| `name` | VARCHAR(255) | |
| `geom` | geometry(MultiPolygon, 4326) | PostGIS geometry |
| `bbox_min_lat` | DOUBLE PRECISION | pre-computed bounding box |
| `bbox_max_lat` | DOUBLE PRECISION | |
| `bbox_min_lon` | DOUBLE PRECISION | |
| `bbox_max_lon` | DOUBLE PRECISION | |

Alert engine loads `id`, `geom` (as WKB hex), and bbox columns at startup.

---

### `listings` (existing — alert engine reads for enrichment)

Alert engine reads minimal fields from `listings` to populate `listing_summary` in notifications. No writes to listings.

Relevant columns:
- `id`, `title`, `price_eur`, `area_m2`, `bedrooms`, `city`, `country_code`
- `deal_score`, `deal_tier`, `lat`, `lon`
- `status` (only `active` listings should trigger alerts)

---

## Redis Data Structures

### Deduplication SET

```
Key:   alerts:sent:{user_id}
Type:  SET
Value: listing_id (UUID string)
TTL:   604800 (7 days)
```

Operations:
- `SISMEMBER alerts:sent:{user_id} {listing_id}` — check before dispatching
- `SADD alerts:sent:{user_id} {listing_id}` — record after dispatching
- `EXPIRE alerts:sent:{user_id} 604800` — reset TTL on each SADD
- `SREM alerts:sent:{user_id} {listing_id}` — remove on price drop event (allow re-alert)

### Digest Buffer ZSET

```
Key:    alerts:digest:{user_id}:{rule_id}:{frequency}
Type:   SORTED SET
Score:  deal_score (float64, higher = better)
Member: listing_id (UUID string)
TTL:    3600 (hourly) | 86400 (daily)
```

Operations:
- `ZADD alerts:digest:{user_id}:{rule_id}:{frequency} {deal_score} {listing_id}` — buffer match
- `EXPIRE alerts:digest:{user_id}:{rule_id}:{frequency} {ttl}` — set expiry
- `ZREVRANGEBYSCORE ... LIMIT 0 20` — compile top 20 by score
- `DEL alerts:digest:{user_id}:{rule_id}:{frequency}` — clear after sending

Note: `rule_id` is included in the key so multiple digest rules per user buffer independently.

---

## Go Type Definitions

### In-memory rule cache entry

```go
// CachedRule is the in-memory representation of an alert_rules row.
// Parsed once at cache load time; evaluated per-listing on hot path.
type CachedRule struct {
    ID          uuid.UUID
    UserID      uuid.UUID
    Name        string
    CountryCode string
    ZoneIDs     []uuid.UUID
    Category    string // empty = any
    Filter      RuleFilter
    Channels    []NotificationChannel
    Frequency   string // instant | hourly | daily
}

type RuleFilter struct {
    PropertyType string   `json:"property_type,omitempty"`
    PriceMin     *float64 `json:"price_min,omitempty"`
    PriceMax     *float64 `json:"price_max,omitempty"`
    AreaMin      *float64 `json:"area_min,omitempty"`
    AreaMax      *float64 `json:"area_max,omitempty"`
    BedroomsMin  *int     `json:"bedrooms_min,omitempty"`
    BedroomsMax  *int     `json:"bedrooms_max,omitempty"`
    DealTierMax  *int     `json:"deal_tier_max,omitempty"`
    Features     []string `json:"features,omitempty"`
}

type NotificationChannel struct {
    Type       string  `json:"type"`
    WebhookURL *string `json:"webhook_url,omitempty"`
}
```

### NATS event payloads (consumed)

```go
// ScoredListingEvent consumed from subject: scored.listings
type ScoredListingEvent struct {
    ListingID       uuid.UUID `json:"listing_id"`
    CountryCode     string    `json:"country_code"`
    Lat             float64   `json:"lat"`
    Lon             float64   `json:"lon"`
    PropertyType    string    `json:"property_type"`
    PriceEUR        float64   `json:"price_eur"`
    AreaM2          float64   `json:"area_m2"`
    Bedrooms        *int      `json:"bedrooms,omitempty"`
    Features        []string  `json:"features,omitempty"`
    DealScore       float64   `json:"deal_score"`
    DealTier        int       `json:"deal_tier"`
    EstimatedPrice  float64   `json:"estimated_price_eur"`
    ModelVersion    string    `json:"model_version"`
    ScoredAt        time.Time `json:"scored_at"`
}

// PriceChangeEvent consumed from subject: listings.price-change.{country}
type PriceChangeEvent struct {
    ListingID   uuid.UUID `json:"listing_id"`
    CountryCode string    `json:"country_code"`
    OldPriceEUR float64   `json:"old_price_eur"`
    NewPriceEUR float64   `json:"new_price_eur"`
    ChangedAt   time.Time `json:"changed_at"`
}
```

### NATS event payloads (published)

See `contracts/nats-notifications.md` for the full `NotificationEvent` schema.

---

## Zone Geometry Cache

```go
type ZoneGeometry struct {
    ID     uuid.UUID
    BBoxMinLat, BBoxMaxLat float64
    BBoxMinLon, BBoxMaxLon float64
    // WKB geometry stored for PostGIS confirmation query
}

// ZoneCache maps zone_id → ZoneGeometry
type ZoneCache map[uuid.UUID]ZoneGeometry
```

---

## State Transition: Alert Dedup Lifecycle

```
Listing published
       │
       ▼
  SISMEMBER? ──YES──► Skip (already sent in 7d window)
       │
       NO
       ▼
  Evaluate rule
       │
    MATCH?
       │
      YES
       ▼
  SADD + EXPIRE 7d ──► Dispatch notification
       │
  Price drop event ──► SREM (clear dedup) ──► Re-evaluate on next score
```
