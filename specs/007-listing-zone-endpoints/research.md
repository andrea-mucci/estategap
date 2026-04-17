# Research: Listing & Zone Data Endpoints

**Phase**: 0 — Research  
**Date**: 2026-04-17  
**Feature**: specs/007-listing-zone-endpoints

---

## Current State Analysis

### What Already Exists

The API Gateway (`services/api-gateway`) has partial implementations that require enhancement:

| Endpoint | Status | Gaps |
|----------|--------|------|
| `GET /v1/listings` | Partial | Missing: zone_id filter, property_type, bedrooms/bathrooms, portal_id, days_on_market range, sort options, currency conversion, subscription gating, standard envelope |
| `GET /v1/listings/{id}` | Partial | Missing: price_history, SHAP (field exists in model), comparables, zone stats |
| `GET /v1/zones` | Partial | Missing: level/parent_id filters, summary stats in response |
| `GET /v1/zones/{id}` | Partial | Missing: full stats (listing count, median price, deal count, trend) |
| `GET /v1/zones/{id}/analytics` | Wrong shape | Current: period comparison (two windows). Required: 12 monthly data points via `date_trunc('month', ...)` |
| `GET /v1/zones/compare` | Missing | New endpoint |
| `GET /v1/countries` | Missing | New handler + repo |
| `GET /v1/portals` | Missing | New handler + repo |

### Existing Infrastructure

- **Replica pool** (`replicaPool`): Already used by `ListingsRepo` and `ZonesRepo` — all new read queries use it.
- **Redis client** (`redisClient`): Available in `run()`, not yet passed to listing/zone handlers. Must be threaded through for caching.
- **JWT claims in context**: `ctxkey.UserTier` already set by `Authenticator` middleware — free-tier gating reads from context without a DB round-trip.
- **Cursor helpers**: `encodeTimeCursor`/`decodeTimeCursor` and `encodeIDCursor`/`decodeIDCursor` exist. Need additional composite cursor for float+UUID (deal_score, price sorts).
- **Shared models**: `models.Listing`, `models.Zone`, `models.PriceHistory`, `models.Country`, `models.Portal` all defined in `libs/pkg/models/`.

---

## Decision: Cursor Strategy Per Sort Order

**Decision**: Use a composite base64 cursor encoding `{float64_value}|{uuid}` for numeric sort fields.

**Rationale**: The existing `encodeTimeCursor` encodes `{unix_nanos}|{uuid}`. The same pattern works for deal_score, price, price_m2, and days_on_market by encoding the float64 bits directly. Each sort key needs its own keyset pagination condition:

| sort_by | Cursor fields | SQL condition (DESC) |
|---------|---------------|---------------------|
| `recency` (default) | (first_seen_at, id) | `(first_seen_at, id) < ($cur_ts, $cur_id)` |
| `deal_score` | (deal_score, id) | `(deal_score, id) < ($cur_score, $cur_id)` |
| `price` | (asking_price_eur, id) | `(asking_price_eur, id) < ($cur_price, $cur_id)` |
| `price_m2` | (price_per_m2_eur, id) | `(price_per_m2_eur, id) < ($cur_price, $cur_id)` |
| `days_on_market` | (days_on_market, id) | `(days_on_market, id) < ($cur_dom, $cur_id)` |

NULL values in sort columns: listings with NULL deal_score are excluded when sorting by deal_score (`WHERE deal_score IS NOT NULL`). NULL days_on_market listings are sorted last when filtering without a days_on_market constraint.

**Alternatives considered**: Offset-based pagination — rejected because it produces skipped/duplicated results when new listings are inserted mid-session, and is O(n) for large offsets.

---

## Decision: Zone Filtering via PostGIS

**Decision**: Zone-based listing filter uses `ST_Within(l.location, z.geometry)` with a subquery or JOIN to the zones table.

**Rationale**: The listings table stores `location` as a PostGIS geometry (POINT). The zones table stores `geometry` as MULTIPOLYGON. A spatial predicate is the correct and index-accelerated approach when a GIST index exists on `listings.location`.

**SQL pattern**:
```sql
-- When zone_id filter is present:
AND ST_Within(
    l.location,
    (SELECT geometry FROM zones WHERE id = $zone_id)
)
```

**Alternatives considered**: Pre-computed zone_id column on listings (`l.zone_id = $zone_id`) — faster but only works when the pipeline has already assigned zones to all listings. Since new listings may not yet have zone_id populated, ST_Within is the safer fallback. The filter should try zone_id match first (`l.zone_id = $zone_id OR ST_Within(...)`) but this adds complexity. **Resolution**: use `l.zone_id = $zone_id` as the primary filter (populated by pipeline), document that listings without a zone_id won't appear in zone-filtered searches until the pipeline assigns them.

---

## Decision: Currency Conversion in SQL

**Decision**: Join `exchange_rates` table in the SQL query and multiply prices inline.

**Rationale**: Single round-trip, no application-level conversion math. The exchange_rates table stores daily rates with a unique index on `(currency, date)`.

**SQL pattern**:
```sql
LEFT JOIN (
    SELECT rate_to_eur
    FROM exchange_rates
    WHERE currency = $target_currency
    ORDER BY date DESC
    LIMIT 1
) er ON TRUE
-- In SELECT: asking_price_eur * (1.0 / er.rate_to_eur) AS asking_price_converted
```

The `X-Exchange-Rate-Date` header is populated from the max date returned in the query. If no rate found, fall back to EUR (rate = 1.0, currency = EUR).

**Alternatives considered**: Application-level conversion after fetching — rejected because it requires fetching EUR prices and multiplying in Go, adding application complexity without benefit.

---

## Decision: Subscription Gating Implementation

**Decision**: Apply gating as SQL conditions directly in `SearchListings()`, reading tier from the context key `ctxkey.UserTier`.

**Rationale**: The JWT already carries the tier (set by `Authenticator` middleware). No DB round-trip needed for Free gating. Basic country restriction requires a DB lookup since the allowed-countries list is not in the JWT.

**Tier gating rules**:
| Tier | SQL addition |
|------|-------------|
| `free` | `AND first_seen_at < NOW() - INTERVAL '48 hours'` |
| `basic` | Fetch user record to get `allowed_countries`, add `AND country = ANY($allowed)` |
| `pro`, `global`, `api` | No restriction |

**Alternatives considered**: Middleware-level gating before the handler runs — rejected because gating logic depends on query parameters (e.g., which country is being searched) and is better expressed as SQL predicates.

---

## Decision: Redis Caching Layer

**Decision**: Add a `CacheClient` wrapper around `go-redis` with a generic `GetOrSet[T]` helper. Handlers/repos call this directly for cacheable resources.

**Cache key pattern**: `cache:{entity}:{id_or_hash}` where hash is `fmt.Sprintf("%x", fnv.Sum32())` over sorted query params.

**TTL matrix**:
| Entity | TTL | Key example |
|--------|-----|-------------|
| Zone statistics | 5 min | `cache:zone_stats:{zone_id}` |
| Zone analytics | 5 min | `cache:zone_analytics:{zone_id}` |
| Zone compare | 2 min | `cache:zone_compare:{hash_of_ids}` |
| Country summaries | 15 min | `cache:countries` |
| Portal list | 15 min | `cache:portals` |
| Top deals per country | 1 min | `cache:top_deals:{country}` |

Listing search results are **not** cached (high cardinality of filter combinations, stale results are unacceptable for paid tiers).

**Alternatives considered**: Read-through cache in the repository layer — too tightly coupled. Separate cache service — overkill for this scale. Handler-level check-then-fetch — chosen approach.

---

## Decision: Zone Analytics Shape (12 Monthly Points)

**Decision**: Rewrite `GetZoneAnalytics()` to use `date_trunc('month', recorded_at)` over `price_history`, generating exactly 12 data points with a `generate_series` to fill gaps.

**Rationale**: The current implementation does a period-based comparison (current window vs prior window) which does not satisfy the 12-point time-series requirement.

**SQL pattern**:
```sql
WITH months AS (
    SELECT generate_series(
        date_trunc('month', NOW()) - INTERVAL '11 months',
        date_trunc('month', NOW()),
        INTERVAL '1 month'
    ) AS month
),
stats AS (
    SELECT
        date_trunc('month', ph.recorded_at) AS month,
        PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY ph.new_price_eur) AS median_price_eur,
        COUNT(DISTINCT ph.listing_id) AS listing_volume,
        COUNT(*) FILTER (WHERE l.deal_tier IN (1, 2)) AS deal_count
    FROM price_history ph
    JOIN listings l ON l.id = ph.listing_id AND l.country = ph.country
    WHERE l.zone_id = $1
      AND ph.recorded_at >= date_trunc('month', NOW()) - INTERVAL '11 months'
    GROUP BY 1
)
SELECT
    m.month,
    COALESCE(s.median_price_eur, 0) AS median_price_eur,
    COALESCE(s.listing_volume, 0) AS listing_volume,
    COALESCE(s.deal_count, 0) AS deal_count
FROM months m
LEFT JOIN stats s ON s.month = m.month
ORDER BY m.month ASC
```

**Alternatives considered**: Using the `listings` table with `first_seen_at` — rejected because `price_history` reflects actual market activity (including price changes) and is what the spec references.

---

## Decision: Zone Statistics Materialized View

**Decision**: Verify and create the `zone_statistics` materialized view if absent. The view is owned by the data pipeline feature but must exist before this feature goes live.

**Expected schema** (if not present, migration needed):
```sql
CREATE MATERIALIZED VIEW zone_statistics AS
SELECT
    z.id AS zone_id,
    z.country_code,
    COUNT(l.id) AS listing_count,
    PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY l.price_per_m2_eur) AS median_price_m2_eur,
    COUNT(l.id) FILTER (WHERE l.deal_tier IN (1, 2)) AS deal_count,
    AVG(l.price_per_m2_eur) - LAG(AVG(l.price_per_m2_eur)) OVER (
        PARTITION BY z.id ORDER BY date_trunc('month', NOW())
    ) AS price_trend_pct
FROM zones z
LEFT JOIN listings l ON l.zone_id = z.id AND l.status = 'active'
GROUP BY z.id, z.country_code;

CREATE UNIQUE INDEX ON zone_statistics (zone_id);
```

This view is refreshed by a background job (`REFRESH MATERIALIZED VIEW CONCURRENTLY zone_statistics`). The API reads it directly. **If the view does not exist, this feature requires a migration as a prerequisite.**

---

## Decision: Response Envelope Migration

**Decision**: Update all list responses to use the standard envelope `{data, pagination, meta}`. The existing `{items, total, cursor}` shape is changed.

**Rationale**: Consistent envelope across all endpoints enables generic client-side pagination handling.

**Breaking change**: The listings and zones `List` endpoints will change their response shape. Since this is a pre-GA API, no backwards compatibility shim is needed.

---

## Decision: Route Registration Order for /zones/compare

**Decision**: Register `GET /v1/zones/compare` before `GET /v1/zones/{id}` in the chi router to prevent `compare` from being captured as an `{id}` path parameter.

**Rationale**: chi routes are matched in registration order for exact vs parameter paths. Registering the static path first ensures correct dispatch.

---

## Prerequisite Check

| Prerequisite | Status | Action |
|-------------|--------|--------|
| `zone_statistics` materialized view | Unknown — check DB migrations | Create migration in `services/pipeline` or `alembic` if absent |
| `listings.location` GIST index | Unknown — check schema | Required for ST_Within performance |
| `exchange_rates` table populated | Assumed from data pipeline | No action for this feature |
| `price_history` table populated | Assumed from data pipeline | No action for this feature |
| `portals` health fields (`last_scrape_at`) | Not in current schema | Return `null` for health fields; schema extension is a separate feature |
