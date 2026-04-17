# Implementation Plan: Alert Engine

**Branch**: `016-alert-engine` | **Date**: 2026-04-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/016-alert-engine/spec.md`

## Summary

Implement the `alert-engine` Go service that consumes `scored.listings` and `listings.price-change.*` events from NATS JetStream, evaluates them against all active user alert rules using a country-indexed in-memory cache, deduplicates with Redis SETs, routes instant matches to `alerts.notifications.*`, and buffers digest matches in Redis sorted sets compiled by hourly/daily ticker goroutines.

## Technical Context

**Language/Version**: Go 1.23
**Primary Dependencies**: chi v5 (health HTTP), pgx/v5 (PostgreSQL), go-redis v9 (Redis), nats.go v1.37 (JetStream), google/uuid, shopspring/decimal, prometheus/client_golang, spf13/viper, golang.org/x/sync (errgroup)
**Storage**: PostgreSQL 16 + PostGIS 3.4 (read: alert_rules, zones, listings; write: alert_history); Redis 7 (dedup SETs, digest ZSETs)
**Testing**: Go table-driven unit tests + testcontainers-go integration tests (PostgreSQL + PostGIS + Redis)
**Target Platform**: Linux container (Kubernetes)
**Project Type**: Event-driven microservice (NATS consumer + background goroutines)
**Performance Goals**: < 500ms per scored listing including all rule evaluations; 10k active rules without degradation
**Constraints**: GOMAXPROCS-bounded goroutine pool; batch NATS consumption (100 msgs); O(1) country lookup via in-memory index
**Scale/Scope**: 10k active rules, ~1k-10k listings/day per country

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Polyglot Service Architecture | ✅ PASS | Go service for high-throughput alerting — explicitly called out in constitution |
| II. Event-Driven Communication | ✅ PASS | Consumes NATS JetStream; publishes to NATS. No direct HTTP between services |
| III. Country-First Data Sovereignty | ✅ PASS | Rules indexed by country; notifications routed to `alerts.notifications.{country}` |
| IV. ML-Powered Intelligence | ✅ PASS | Consumes ML deal_score/deal_tier; SHAP not needed here (scored upstream) |
| V. Code Quality Discipline | ✅ PASS | Go: pgx (no ORM), slog, explicit errors, golangci-lint, table-driven tests |
| VI. Security & Ethical Scraping | ✅ PASS | No user-facing auth in this service; no secrets in code |
| VII. Kubernetes-Native Deployment | ✅ PASS | Dockerfile + Helm chart required |

**Post-design re-check**: No violations introduced. No complexity tracking required.

## Project Structure

### Documentation (this feature)

```text
specs/016-alert-engine/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 — all decisions resolved
├── data-model.md        # Phase 1 — DB + Redis + Go types
├── quickstart.md        # Phase 1 — developer setup
├── contracts/
│   └── nats-events.md   # Phase 1 — consumed + published NATS schemas
└── tasks.md             # Phase 2 — /speckit.tasks output (not yet created)
```

### Source Code (repository root)

```text
services/alert-engine/
├── cmd/
│   └── main.go                    # wiring: config → DB → Redis → NATS → cache → consumers → digest → HTTP
├── internal/
│   ├── config/
│   │   └── config.go              # viper: DATABASE_URL, REDIS_URL, NATS_URL, intervals, pool sizes
│   ├── cache/
│   │   └── rules.go               # RuleCache: map[country][]CachedRule + ZoneCache; 60s refresh
│   ├── matcher/
│   │   ├── engine.go              # Orchestrate: country filter → zone → jsonb filter → tier; errgroup pool
│   │   ├── filter.go              # RuleFilter evaluation; short-circuit per field
│   │   └── zone.go                # BBOX pre-reject + PostGIS ST_Contains confirmation
│   ├── dedup/
│   │   └── dedup.go               # Redis SISMEMBER/SADD/SREM; fail-open on Redis error
│   ├── router/
│   │   └── router.go              # instant → publisher; digest → buffer.ZADD
│   ├── digest/
│   │   ├── buffer.go              # ZADD + EXPIRE per user+rule+frequency
│   │   └── compiler.go            # time.Ticker goroutines; SCAN + ZREVRANGEBYSCORE + DEL + publish
│   ├── repository/
│   │   ├── rules.go               # load active rules + zones from DB; used by cache refresh
│   │   └── history.go             # INSERT alert_history rows
│   ├── publisher/
│   │   └── publisher.go           # NATS publish to alerts.notifications.{country}
│   └── worker/
│       └── consumer.go            # JetStream pull consumers; batch fetch + errgroup dispatch
├── go.mod
├── go.sum
└── Dockerfile

services/pipeline/alembic/versions/
└── 014_alert_rules_add_frequency.py   # ADD COLUMN frequency + CHECK constraint + index

libs/pkg/models/
└── alert.go                           # Update CachedRule to match current DB schema (ZoneIDs, IsActive, Frequency)
```

**Structure Decision**: Single Go service following the established api-gateway/scrape-orchestrator pattern: `cmd/main.go` for wiring, `internal/` for domain packages. No HTTP router for external traffic (health/metrics only via chi). No ORM; raw pgx queries.

## Phase 0: Research

All decisions resolved. See [research.md](./research.md) for full rationale on:

1. In-memory rule cache with `sync.RWMutex` + country index (Decision 1)
2. Zone intersection: BBOX pre-filter + PostGIS ST_Contains confirmation (Decision 2)
3. JSONB filter as Go struct, parsed at cache-load time (Decision 3)
4. Redis SET dedup with 7-day TTL, fail-open (Decision 4)
5. Redis ZSET digest buffer with `ZREVRANGEBYSCORE LIMIT 0 20` (Decision 5)
6. NATS pull consumer, batch=100, `errgroup` goroutine pool (Decision 6)
7. `time.Ticker` digest scheduler in-process (Decision 7)
8. `frequency VARCHAR(10)` column on `alert_rules` via Alembic migration (Decision 8)
9. NATS notification event JSON schema (Decision 9)
10. `errgroup` bounded parallel rule evaluation (Decision 10)

## Phase 1: Design Artifacts

- [data-model.md](./data-model.md) — DB schema changes, Redis key layout, Go type definitions
- [contracts/nats-events.md](./contracts/nats-events.md) — NATS consumed + published event schemas
- [quickstart.md](./quickstart.md) — local dev setup, env vars, test commands

## Key Implementation Notes

### Rule Cache Refresh

```
startup:
  loadRules() → map[country][]CachedRule
  loadZones() → map[uuid]ZoneGeometry
  go refreshLoop(every 60s):
    mu.Lock(); cache = newCache; mu.Unlock()
```

### Matching Pipeline (per ScoredListingEvent)

```
1. rules = cache.Get(listing.CountryCode)        // O(1) map lookup
2. Pool.Submit(each rule):
   a. if rule.Category != "" && rule.Category != listing.PropertyType → skip
   b. if len(rule.ZoneIDs) > 0:
      - BBOX pre-check all zones (cheap)
      - ST_Contains DB query for candidates
      → skip if not in any zone
   c. filter.Evaluate(listing) → short-circuit on each field
   d. if rule.Filter.DealTierMax != nil && listing.DealTier > *DealTierMax → skip
3. Collect matches → route(instant|digest) → dedup → dispatch
```

### Dedup Check Ordering

Dedup MUST be checked AFTER rule evaluation passes, to avoid poisoning the dedup SET for rules that don't match. Check order per rule match:
1. `SISMEMBER alerts:sent:{user_id} {listing_id}` → if member → skip
2. Dispatch notification
3. `SADD alerts:sent:{user_id} {listing_id}` + `EXPIRE`

### Alert History Write

Write `alert_history` row (delivery_status = 'pending') synchronously after NATS publish succeeds. If NATS publish fails, do not write history. The dispatcher updates delivery_status to 'delivered' or 'failed'.

### Digest Compiler SCAN Pattern

```
SCAN 0 MATCH "alerts:digest:*:hourly" COUNT 100
→ for each key: parse user_id + rule_id
→ check rule still active in cache
→ ZREVRANGEBYSCORE LIMIT 0 20
→ fetch listing summaries from DB
→ publish NotificationEvent (is_digest=true)
→ DEL key
→ INSERT alert_history for each listing
```

## Complexity Tracking

No constitution violations.
