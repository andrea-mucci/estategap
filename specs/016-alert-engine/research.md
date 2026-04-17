# Research: Alert Engine (016)

**Date**: 2026-04-17
**Branch**: `016-alert-engine`

---

## Decision 1: In-Memory Rule Cache with Country Index

**Decision**: Load all active `alert_rules` rows into a `map[string][]*AlertRule` keyed by `country_code` on startup. Refresh the full map every 60 seconds via a background goroutine with a `sync.RWMutex`. Swap the map atomically by replacing the pointer under write lock.

**Rationale**: 10,000 rules fit comfortably in memory (~10–50MB for normalized rule structs). A country-keyed map gives O(1) lookup per listing, reducing the matching set from 10k to the rules for that country only. A full-replacement strategy is simpler than incremental diffing and avoids stale-entry bugs.

**Alternatives considered**:
- Database query per listing: Rejected — too slow (network + query per message), would not meet 500ms target at scale.
- Incremental cache updates via change-data-capture: Rejected — added complexity; 60s full refresh is sufficient given rule changes are infrequent.
- Rule cache in Redis: Rejected — adds network hop; in-process memory is faster for hot-path matching.

---

## Decision 2: Zone Intersection Strategy

**Decision**: Pre-load zone geometries at startup into a `map[uuid.UUID]ZoneGeometry`. For each rule with `zone_ids`, perform a two-phase check:
1. **Bounding box rejection**: Compare listing lat/lon against zone BBOX (cheap, no DB call). Skip if outside all BBOXes.
2. **Precise ST_Contains**: For listings that pass BBOX, run `SELECT ST_Contains(z.geom, ST_SetSRID(ST_MakePoint($lon, $lat), 4326)) FROM zones WHERE id = $zone_id` — batched for all candidate zones.

In practice, use the pre-loaded WKB geometry and `github.com/twpayne/go-geom` or a simple BBOX check followed by a single PostGIS query only for candidates, to avoid importing a full geometry library.

**Rationale**: Bounding box pre-filter eliminates most zones cheaply. PostGIS ST_Contains is the authoritative spatial check. Pre-loading zone geometries avoids repeated DB queries on the hot path.

**Alternatives considered**:
- Pure PostGIS per-event query (JOIN alert_rules with zones): Rejected — too slow for hot path, one DB round-trip per rule.
- Full in-process geometry library (e.g., `go-geos`): Rejected — CGO dependency, complicates build. BBOX pre-filter + single PostGIS confirmation is sufficient.
- No zone filtering (country-only): Rejected — rules with zone filters must be accurately enforced.

---

## Decision 3: JSONB Filter Evaluation in Go

**Decision**: Define a `RuleFilter` Go struct that mirrors the JSONB columns stored in `alert_rules.filter`. Unmarshal JSON once when loading into cache. Evaluate each field with direct Go comparisons; short-circuit on first non-match.

```go
type RuleFilter struct {
    PropertyType string   `json:"property_type,omitempty"`
    PriceMin     *float64 `json:"price_min,omitempty"`
    PriceMax     *float64 `json:"price_max,omitempty"`
    AreaMin      *float64 `json:"area_min,omitempty"`
    AreaMax      *float64 `json:"area_max,omitempty"`
    BedroomsMin  *int     `json:"bedrooms_min,omitempty"`
    BedroomsMax  *int     `json:"bedrooms_max,omitempty"`
    DealTierMax  *int     `json:"deal_tier_max,omitempty"` // 1=great, 2=good, 3=fair, 4=overpriced
    Features     []string `json:"features,omitempty"`
}
```

**Rationale**: Parsing at cache-load time (not per-event) means JSON deserialization cost is paid once per 60s refresh, not per evaluation. Direct field comparisons are O(1) and cache-friendly.

**Alternatives considered**:
- Evaluate JSONB filters in PostgreSQL (`WHERE filter @> $filter`): Rejected — requires DB call per rule on hot path.
- Dynamic expression engine (e.g., `expr` library): Rejected — unnecessary complexity; filter fields are well-defined and bounded.

---

## Decision 4: Deduplication with Redis SET

**Decision**: Use `SISMEMBER alerts:sent:{user_id} {listing_id}` to check. On miss: `SADD` + `EXPIRE 604800` (7 days). On price change events: remove the member with `SREM` before re-evaluating, so the next match passes the dedup check.

Key schema: `alerts:sent:{user_id}` → Redis SET of `listing_id` strings.

**Rationale**: Redis SET SISMEMBER is O(1). TTL on the key ensures automatic cleanup. Price drop bypass by deleting the member is simpler than maintaining a separate "bypass" flag.

**Alternatives considered**:
- PostgreSQL `alert_history` for dedup: Rejected — table scan per user per listing is too slow.
- Redis HASH per user: Equivalent; SET is simpler.
- No dedup (rely on caller): Rejected — duplicates directly degrade user experience.

**Note on fail-open**: If Redis is unavailable, the SISMEMBER call fails. The engine will fail open (allow the notification through) and log the error. This is preferable to silently dropping alerts.

---

## Decision 5: Digest Buffering with Redis Sorted Set

**Decision**: Buffer digest matches with `ZADD alerts:digest:{user_id}:{frequency} {deal_score} {listing_id}`. Set TTL = frequency interval (3600s for hourly, 86400s for daily). Compilation reads with `ZREVRANGEBYSCORE ... LIMIT 0 20` (highest score first), then `DEL` the key after publishing.

**Rationale**: Sorted set with score = deal_score gives rank ordering for free. ZREVRANGEBYSCORE with LIMIT handles the "top 20" requirement atomically. DEL after send ensures no stale entries accumulate.

**Alternatives considered**:
- Redis LIST per user: No built-in ranking; would require sort at compilation time.
- In-memory buffer with periodic flush: Lost on restart; Redis provides durability across crashes.

---

## Decision 6: NATS JetStream Consumption Pattern

**Decision**: Use a durable pull consumer with `MaxAckPending = 100` for batch processing. Each worker goroutine calls `FetchMsg` and processes a batch of up to 100 messages. Acknowledge only after full processing. Use a bounded goroutine pool (size = `runtime.GOMAXPROCS(0)`) for parallel rule evaluation per message.

Subjects consumed:
- `scored.listings` (durable consumer: `alert-engine-scored`)
- `listings.price-change.>` (durable consumer: `alert-engine-price`)

**Rationale**: Pull consumers give backpressure control. Batch size 100 amortizes round-trip overhead. Goroutine pool prevents unbounded spawning under burst load.

**Alternatives considered**:
- Push consumers: Less backpressure control; pull is preferred for CPU-bound processing.
- Single goroutine per message: Too slow at scale.
- Unbounded goroutines: Risk of memory exhaustion under spike.

---

## Decision 7: Digest Scheduler

**Decision**: Two `time.Ticker` goroutines in the background: one ticking every 60 minutes (hourly digest), one every 24 hours (daily digest). On each tick, query Redis for all `alerts:digest:*:hourly` / `alerts:digest:*:daily` keys using `SCAN` with pattern matching, then compile and publish each.

**Rationale**: `time.Ticker` is idiomatic Go for periodic tasks. SCAN with pattern avoids maintaining a separate user-list index.

**Alternatives considered**:
- External cron job (K8s CronJob): Adds operational overhead; digest compilation is lightweight enough to run in-process.
- Separate digest service: Overkill for this scope; same binary is simpler.
- Maintain explicit user-set in Redis: Extra write per match; SCAN is acceptable given moderate key counts.

---

## Decision 8: Schema Addition — `frequency` Column

**Decision**: Add `frequency VARCHAR(10) NOT NULL DEFAULT 'instant'` to `alert_rules`. Values: `instant`, `hourly`, `daily`. Requires a new Alembic migration (migration 014 in the pipeline service).

**Rationale**: Frequency is a rule-level property, not a channel-level property. Embedding it in the `channels` JSONB would make it harder to index and query. A dedicated column allows simple SQL filtering in the rule cache load query.

**Alternatives considered**:
- Frequency in channels JSONB: Rejected — harder to query, no DB-level constraint.
- Separate `rule_frequency` table: Over-normalized for a simple enum field.

---

## Decision 9: NATS Notification Event Schema

**Decision**: Publish to `alerts.notifications.{country_code}` as JSON:

```json
{
  "event_id": "uuid",
  "user_id": "uuid",
  "rule_id": "uuid",
  "rule_name": "string",
  "listing_id": "uuid",
  "country_code": "string",
  "channel": "email|push|webhook",
  "webhook_url": "string|null",
  "frequency": "instant|hourly|daily",
  "is_digest": false,
  "deal_score": 0.87,
  "deal_tier": 1,
  "listing_summary": {
    "title": "string",
    "price_eur": 320000,
    "area_m2": 95,
    "bedrooms": 3,
    "city": "string",
    "image_url": "string|null"
  },
  "triggered_at": "RFC3339"
}
```

For digest events, `is_digest: true` and `listing_summary` is replaced by `listings: [...]`.

**Rationale**: Subject per country allows downstream dispatcher to shard by country. JSON is the existing protocol used across NATS streams in this project (no proto for alerts yet per codebase audit). `listing_summary` avoids the dispatcher needing a DB lookup.

**Alternatives considered**:
- Single `alerts.notifications` subject: Less routing flexibility downstream.
- Protobuf: No existing alert proto; JSON is consistent with other streams. Can migrate later.

---

## Decision 10: Parallel Rule Evaluation

**Decision**: For each incoming listing, fan out rule evaluation across a `errgroup`-based worker pool bounded at `GOMAXPROCS`. Each worker evaluates one rule and sends a match result to a result channel. Collect results; dispatch notifications serially after fan-in.

**Rationale**: `golang.org/x/sync/errgroup` provides clean cancellation on first error. Bounded pool prevents goroutine explosion. Serial dispatch after fan-in simplifies Redis dedup (no concurrent SADD for same user).

**Alternatives considered**:
- Sequential evaluation: Correct but slower — 10k rules × ~10μs each = ~100ms sequential. Parallel brings it under 10ms for typical country slices.
- Unbounded `go func()` per rule: Risk of goroutine explosion; pool is safer.
