# Tasks: Alert Engine

**Input**: Design documents from `specs/016-alert-engine/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/nats-events.md ✅, quickstart.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story. No TDD requested — no test tasks unless noted in Polish phase.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel with other [P] tasks in the same phase (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- All paths are relative to the repository root

---

## Phase 1: Setup

**Purpose**: Bootstrap the `alert-engine` Go module with correct dependencies and build infrastructure.

- [ ] T001 Update `services/alert-engine/go.mod` to add all required dependencies: `github.com/go-chi/chi/v5`, `github.com/jackc/pgx/v5`, `github.com/redis/go-redis/v9`, `github.com/nats-io/nats.go`, `github.com/google/uuid`, `github.com/shopspring/decimal`, `github.com/prometheus/client_golang`, `github.com/spf13/viper`, `golang.org/x/sync`, `github.com/estategap/libs`; run `go mod tidy` to populate `go.sum`
- [X] T002 [P] Create all service subdirectories under `services/alert-engine/`: `cmd/`, `internal/config/`, `internal/cache/`, `internal/matcher/`, `internal/dedup/`, `internal/router/`, `internal/digest/`, `internal/repository/`, `internal/publisher/`, `internal/worker/`, `internal/metrics/`
- [X] T003 [P] Create `services/alert-engine/Dockerfile` using multi-stage build (Go 1.23 builder → distroless/static-debian12 runner), exposing port 8080, with `COPY --chown=nonroot` and `USER nonroot`

**Checkpoint**: Module compiles with `go build ./...` (empty stubs).

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before any user story can be implemented — DB access, rule cache, NATS consumers, publisher, and config.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T004 [P] Create Alembic migration `services/pipeline/alembic/versions/014_alert_rules_add_frequency.py`: add `frequency VARCHAR(10) NOT NULL DEFAULT 'instant'` to `alert_rules`, add CHECK constraint `(frequency IN ('instant', 'hourly', 'daily'))`, add partial index `idx_alert_rules_frequency` WHERE `is_active = TRUE`
- [X] T005 [P] Update `libs/pkg/models/alert.go`: replace the legacy `AlertRule` struct fields (`Filters`, `Active`, `LastTriggeredAt`, `TriggerCount`) with the current DB schema fields (`ZoneIDs []pgtype.UUID`, `Category string`, `Filter json.RawMessage`, `IsActive bool`, `Frequency string`) to match migration 013 + 014
- [X] T006 [P] Implement `services/alert-engine/internal/config/config.go`: define `Config` struct with fields `DatabaseURL`, `DatabaseReplicaURL`, `RedisURL`, `NatsURL`, `RuleCacheRefreshInterval` (default 60s), `WorkerPoolSize` (default 0 = GOMAXPROCS), `BatchSize` (default 100), `HealthPort` (default 8080), `LogLevel` (default "info"); implement `Load() (*Config, error)` using `spf13/viper` with env-var binding
- [X] T007 Implement `services/alert-engine/internal/repository/rules.go`: define `Repo` struct with `primary` and `replica` `*pgxpool.Pool`; implement `LoadActiveRules(ctx) ([]CachedRule, error)` querying `alert_rules` JOIN `zones` (via `zone_ids` array unnest) for all rows WHERE `is_active = TRUE`; implement `LoadZoneGeometries(ctx, []uuid.UUID) (map[uuid.UUID]ZoneGeometry, error)` selecting `id`, `bbox_min_lat`, `bbox_max_lat`, `bbox_min_lon`, `bbox_max_lon` from `zones`; define local types `CachedRule` (id, user_id, name, country_code, zone_ids, category, filter `RuleFilter`, channels `[]NotificationChannel`, frequency) and `ZoneGeometry` (id, bbox fields) as specified in `data-model.md`
- [X] T008 Implement `services/alert-engine/internal/cache/rules.go`: define `RuleCache` struct holding `mu sync.RWMutex`, `byCountry map[string][]*CachedRule`, `zones map[uuid.UUID]ZoneGeometry`; implement `Load(ctx, repo)` to do initial fetch; implement `StartRefresh(ctx, repo, interval time.Duration)` goroutine that ticks every `interval` and calls `Load`; implement `Get(countryCode string) []*CachedRule` under read lock; implement `GetZone(id uuid.UUID) (ZoneGeometry, bool)` under read lock
- [X] T009 [P] Implement `services/alert-engine/internal/publisher/publisher.go`: define `Publisher` struct wrapping `nats.JetStreamContext`; implement `PublishNotification(ctx, countryCode string, event NotificationEvent) error` marshalling to JSON and publishing to subject `alerts.notifications.{countryCode}`; define `NotificationEvent`, `ListingSummary`, and `DigestListing` structs matching the schema in `contracts/nats-events.md`
- [X] T010 Implement `services/alert-engine/internal/worker/consumer.go`: define `Consumer` struct; implement `StartScoredListings(ctx, js nats.JetStreamContext, batchSize int, handler func(ScoredListingEvent) error)` as a durable pull consumer on stream `scored-listings`, consumer name `alert-engine-scored`, MaxAckPending=batchSize; implement `StartPriceChanges(ctx, js nats.JetStreamContext, handler func(PriceChangeEvent) error)` as a durable pull consumer on stream `price-changes`, consumer name `alert-engine-price`; define `ScoredListingEvent` and `PriceChangeEvent` structs matching `contracts/nats-events.md`; handlers receive decoded events and return error (nak on error, ack on success)
- [X] T011 Implement `services/alert-engine/cmd/main.go` skeleton: `run()` function that loads config, opens primary + replica pgxpool connections, connects go-redis, connects nats.go + JetStream context, initialises `RuleCache` and calls `Load()`, starts HTTP server on chi router with `GET /health/live` (200 OK) and `GET /health/ready` (checks DB ping + Redis ping + NATS conn status), calls `signal.NotifyContext` for graceful shutdown; no matching logic yet — consumers return nil handler stubs

**Checkpoint**: `go run ./cmd/main.go` starts, `/health/ready` returns 200, rule cache loads from DB.

---

## Phase 3: User Story 1 — Instant Alert on Matching Listing (Priority: P1) 🎯 MVP

**Goal**: A scored listing that matches an instant-frequency alert rule triggers exactly one `alerts.notifications.{country}` NATS event within 500ms, with correct user ID, rule ID, listing summary, and channel.

**Independent Test**: Insert one active instant rule in DB. Publish one matching `scored.listings` NATS message. Subscribe to `alerts.notifications.ES` and assert one event arrives within 500ms with correct fields.

- [X] T012 [P] [US1] Implement `services/alert-engine/internal/matcher/filter.go`: define `RuleFilter` struct (all optional fields: `PropertyType`, `PriceMin/Max`, `AreaMin/Max`, `BedroomsMin/Max`, `DealTierMax`, `Features []string`) with JSON tags; implement `Evaluate(listing ScoredListingEvent) bool` that checks each non-nil field against the listing, short-circuits on first non-match; empty `RuleFilter` always returns true
- [X] T013 [P] [US1] Implement `services/alert-engine/internal/matcher/zone.go`: implement `InAnyZone(listing ScoredListingEvent, zoneIDs []uuid.UUID, cache *cache.RuleCache, db *pgxpool.Pool) (bool, error)`: (1) for each zone ID retrieve `ZoneGeometry` from cache; (2) BBOX pre-check `listing.Lat` and `listing.Lon` against all zones — if no zones pass BBOX return false immediately; (3) for BBOX candidates run `SELECT ST_Contains(geom, ST_SetSRID(ST_MakePoint($2,$3),4326)) FROM zones WHERE id=$1` per candidate zone using the replica pool; return true if any zone contains the point
- [X] T014 [US1] Implement `services/alert-engine/internal/matcher/engine.go`: define `Engine` struct with `cache *cache.RuleCache`, `db *pgxpool.Pool`, `poolSize int`; implement `Match(ctx, listing ScoredListingEvent) ([]*cache.CachedRule, error)` that: (1) fetches `cache.Get(listing.CountryCode)`; (2) fans out rule evaluation across an `errgroup`-bounded goroutine pool of size `poolSize` (default GOMAXPROCS); each worker calls `filter.Evaluate` then `zone.InAnyZone` (if rule has zone_ids); (3) collects matching rules into result slice; return matches
- [X] T015 [US1] Implement `services/alert-engine/internal/router/router.go`: define `Router` struct with `publisher *publisher.Publisher`; implement `RouteInstant(ctx, rule *cache.CachedRule, listing ScoredListingEvent) error` that iterates `rule.Channels`, builds a `NotificationEvent` (event_id = new uuid, triggered_at = now, is_digest = false, listing_summary populated from listing fields), and calls `publisher.PublishNotification` for each channel; return first error
- [X] T016 [P] [US1] Implement `services/alert-engine/internal/repository/history.go`: define `HistoryRepo` struct with primary `*pgxpool.Pool`; implement `InsertHistory(ctx, ruleID, listingID uuid.UUID, channel string) error` that inserts a row into `alert_history` with `delivery_status='pending'`, `triggered_at=NOW()`
- [X] T017 [US1] Update `services/alert-engine/internal/worker/consumer.go`: replace the `StartScoredListings` handler stub with the real pipeline — for each decoded `ScoredListingEvent`: call `engine.Match`, then for each matched instant-frequency rule call `router.RouteInstant` + `historyRepo.InsertHistory`; skip digest-frequency rules in this phase (log and continue); ack message after processing; nak and re-queue on unrecoverable error
- [X] T018 [US1] Update `services/alert-engine/cmd/main.go` to complete US1 wiring: instantiate `matcher.Engine`, `router.Router`, `repository.HistoryRepo`; pass real handler function to `consumer.StartScoredListings`; start consumer goroutine under `errgroup`

**Checkpoint**: Instant alert end-to-end works. One scored listing → one `alerts.notifications.ES` event. Three users × one matching listing → three events.

---

## Phase 4: User Story 2 — Digest of Ranked Deals (Priority: P2)

**Goal**: Listings matching digest-frequency rules (hourly/daily) are buffered in Redis sorted sets by deal score. Hourly and daily ticker goroutines compile and dispatch single `alerts.notifications.{country}` digest events containing up to 20 listings ranked by deal score.

**Independent Test**: Insert one daily digest rule. Buffer 5 matching listings via `ZADD`. Trigger `compiler.RunDaily()`. Assert one `alerts.notifications.ES` event published with `is_digest=true`, 5 listings ranked descending by deal_score, Redis key deleted after send.

- [X] T019 [P] [US2] Implement `services/alert-engine/internal/digest/buffer.go`: define `Buffer` struct wrapping `*redis.Client`; implement `Add(ctx, userID, ruleID uuid.UUID, frequency string, listingID uuid.UUID, dealScore float64) error` that calls `ZADD alerts:digest:{userID}:{ruleID}:{frequency} {dealScore} {listingID}` followed by `EXPIRE` (3600 for hourly, 86400 for daily); implement `Flush(ctx, key string, limit int) ([]string, error)` that calls `ZREVRANGEBYSCORE key +inf -inf WITHSCORES LIMIT 0 limit` and then `DEL key` atomically via pipeline
- [X] T020 [US2] Update `services/alert-engine/internal/router/router.go`: add `buffer *digest.Buffer` field; implement `RouteDigest(ctx, rule *cache.CachedRule, listing ScoredListingEvent) error` that calls `buffer.Add(userID, ruleID, rule.Frequency, listingID, dealScore)`; update `RouteInstant` to check `rule.Frequency == "instant"` so the caller can dispatch correctly
- [X] T021 [P] [US2] Add `FetchListingSummaries(ctx, listingIDs []uuid.UUID) (map[uuid.UUID]ListingSummary, error)` to `services/alert-engine/internal/repository/rules.go`: query `listings` table for `id, title, price_eur, area_m2, bedrooms, city, country_code, deal_score, deal_tier` WHERE `id = ANY($1)` using replica pool; return map keyed by UUID
- [X] T022 [US2] Implement `services/alert-engine/internal/digest/compiler.go`: define `Compiler` struct with `redis *redis.Client`, `repo *repository.Repo`, `publisher *publisher.Publisher`, `historyRepo *repository.HistoryRepo`, `cache *cache.RuleCache`; implement `compile(ctx, frequency string)` that: (1) `SCAN 0 MATCH alerts:digest:*:{frequency} COUNT 100` to find all keys; (2) for each key, parse `userID` and `ruleID` from key; (3) check rule still active in cache — skip if not; (4) call `buffer.Flush` for top 20 listing IDs; (5) call `repo.FetchListingSummaries`; (6) build `NotificationEvent` with `is_digest=true`, listings ranked by score, grouped by country_code; (7) publish via `publisher.PublishNotification`; (8) call `historyRepo.InsertHistory` per listing; implement `StartHourly(ctx)` with `time.NewTicker(time.Hour)` calling `compile(ctx, "hourly")`; implement `StartDaily(ctx)` with `time.NewTicker(24*time.Hour)` calling `compile(ctx, "daily")`
- [X] T023 [US2] Update `services/alert-engine/internal/worker/consumer.go` handler: after `engine.Match`, dispatch instant-frequency matches via `router.RouteInstant` and digest-frequency matches via `router.RouteDigest`; update `services/alert-engine/cmd/main.go` to instantiate `digest.Buffer`, `digest.Compiler`, pass to router, and start `compiler.StartHourly` and `compiler.StartDaily` goroutines under the errgroup

**Checkpoint**: Digest compilation works. Buffer 5 listings manually, call `compiler.compile(ctx, "daily")`, assert one NATS digest event published with all 5 listings sorted by deal_score descending.

---

## Phase 5: User Story 3 — No Duplicate Notifications (Priority: P3)

**Goal**: Once a (user, listing) pair has triggered a notification, subsequent re-scores of the same listing produce no further notification for that user within 7 days. A price drop event clears the dedup record so the listing can re-trigger.

**Independent Test**: Route one matching listing → assert one notification + dedup SET contains listing_id. Route same listing again → assert zero notifications. Publish a price change event → assert dedup SET cleared. Route listing again → assert one notification.

- [X] T024 [US3] Implement `services/alert-engine/internal/dedup/dedup.go`: define `Dedup` struct wrapping `*redis.Client`; implement `IsSent(ctx, userID, listingID uuid.UUID) (bool, error)` calling `SISMEMBER alerts:sent:{userID} {listingID}`; implement `MarkSent(ctx, userID, listingID uuid.UUID) error` calling `SADD` then `EXPIRE 604800` (7 days); implement `ClearSent(ctx, userID, listingID uuid.UUID) error` calling `SREM`; on Redis error, `IsSent` returns `(false, err)` — caller must fail-open (allow notification through) and log the error
- [X] T025 [US3] Update `services/alert-engine/internal/matcher/engine.go`: add `dedup *dedup.Dedup` field; after rule evaluation produces a match, call `dedup.IsSent(ctx, rule.UserID, listing.ListingID)` — if already sent (and no Redis error), skip dispatch; after successful `router.RouteInstant` or `router.RouteDigest`, call `dedup.MarkSent`; on Redis error in `IsSent` fail open: log warning and proceed with dispatch
- [X] T026 [US3] Update `services/alert-engine/internal/worker/consumer.go` `StartPriceChanges` handler: for each `PriceChangeEvent` where `NewPriceEUR < OldPriceEUR` (price drop): query `alert_history` via `historyRepo` to find all `rule_id`s that previously triggered for `listing_id`; for each distinct `user_id` from those rules, call `dedup.ClearSent(ctx, userID, listingID)`; update `services/alert-engine/cmd/main.go` to pass `dedup` instance to engine and start `consumer.StartPriceChanges` goroutine

**Checkpoint**: Dedup works. Same listing sent twice → only one notification. Price drop → dedup cleared → next score triggers again.

---

## Phase 6: User Story 4 — Scale Across 10k Rules (Priority: P4)

**Goal**: With 10,000 active rules loaded, a single scored listing is fully evaluated and matching notifications dispatched within 500ms. Rule evaluation is parallelised across a GOMAXPROCS-bounded pool; NATS consumption uses batch fetch of 100.

**Independent Test**: Seed 10,000 active rules for country "ES" via a test helper. Publish one scored listing. Assert full evaluation + dispatch completes in < 500ms measured with `time.Since`.

- [X] T027 [P] [US4] Verify and enforce GOMAXPROCS-bounded pool in `services/alert-engine/internal/matcher/engine.go`: ensure `poolSize` defaults to `runtime.GOMAXPROCS(0)` when config value is 0; use `golang.org/x/sync/errgroup` with `SetLimit(poolSize)` so no more than `poolSize` concurrent rule evaluations run per listing
- [X] T028 [P] [US4] Verify batch NATS fetch in `services/alert-engine/internal/worker/consumer.go`: `StartScoredListings` must use `js.PullSubscribe` with `nats.MaxAckPending(batchSize)` and fetch up to `batchSize` messages per tick in a `for` loop; ensure individual message processing errors result in `msg.Nak()` without blocking the batch
- [X] T029 [P] [US4] Create `services/alert-engine/internal/metrics/metrics.go`: define and register Prometheus metrics — `alertEngineRulesCached` (Gauge), `alertEngineEventsProcessed` (CounterVec by `event_type`), `alertEngineMatches` (Counter), `alertEngineDedupHits` (Counter), `alertEngineNotificationsPublished` (CounterVec by `channel`, `frequency`), `alertEngineDigestBufferDepth` (GaugeVec by `frequency`), `alertEngineRuleEvalDuration` (Histogram with buckets 1ms–1s)
- [X] T030 [US4] Instrument matching pipeline with Prometheus metrics: in `internal/matcher/engine.go` record `alertEngineRuleEvalDuration` per listing evaluation and increment `alertEngineMatches`; in `internal/worker/consumer.go` increment `alertEngineEventsProcessed`; in `internal/dedup/dedup.go` increment `alertEngineDedupHits` on cache hit; in `internal/publisher/publisher.go` increment `alertEngineNotificationsPublished`; in `internal/cache/rules.go` set `alertEngineRulesCached` after each refresh
- [X] T031 [US4] Update `services/alert-engine/cmd/main.go` chi router to add `GET /metrics` handler using `promhttp.Handler()` from `prometheus/client_golang/prometheus/promhttp`

**Checkpoint**: `/metrics` returns Prometheus text. Load test with 10k rules confirms < 500ms p95 eval latency.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Helm deployment, linting, integration test, and final validation.

- [X] T032 [P] Add Helm `Deployment` template for `alert-engine` in `helm/estategap/templates/alert-engine-deployment.yaml`: 1 replica, `readinessProbe` and `livenessProbe` on `GET /health/ready` and `GET /health/live`, env vars from `ConfigMap` + `Secret`, resource requests/limits matching other Go services
- [X] T033 [P] Add `alert-engine` values block in `helm/estategap/values.yaml` and `values-staging.yaml`: image ref, replica count, env vars (`DATABASE_URL` from secret, `REDIS_URL`, `NATS_URL`, `RULE_CACHE_REFRESH_INTERVAL`, `WORKER_POOL_SIZE`, `BATCH_SIZE`, `HEALTH_PORT`)
- [X] T034 [P] Add NATS durable consumer declarations for `alert-engine` in Helm NATS config (`helm/estategap/values.yaml`): consumer `alert-engine-scored` on stream `scored-listings` (pull, durable, MaxAckPending=100, AckWait=30s); consumer `alert-engine-price` on stream `price-changes` (pull, durable, MaxAckPending=50, AckWait=30s)
- [X] T035 [P] Create `services/alert-engine/.golangci.yml` lint config: enable `errcheck`, `govet`, `staticcheck`, `godot`, `exhaustive`, `noctx`; match the pattern used in `services/api-gateway/.golangci.yml` if it exists
- [X] T036 Write integration test `services/alert-engine/internal/matcher/engine_integration_test.go` (build tag `//go:build integration`): use `testcontainers-go` to spin up PostgreSQL+PostGIS and Redis; seed one instant rule + zone; call `engine.Match` with a matching `ScoredListingEvent`; assert one rule returned; assert dedup SET populated after `MarkSent`
- [ ] T037 Run `golangci-lint run ./...` from `services/alert-engine/` and fix all lint errors
- [ ] T038 Follow `specs/016-alert-engine/quickstart.md` end-to-end verification steps: start dependencies, run migration, start service, publish test NATS messages, verify `/health/ready`, `/metrics`, and notification events

**Checkpoint**: `helm lint`, `go test ./...`, `golangci-lint run ./...` all pass. Service deploys to staging.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **blocks all user story phases**
- **User Story Phases (3–6)**: All depend on Phase 2 completion; US3 (dedup) integrates with US1 components; otherwise independent
- **Polish (Phase 7)**: Depends on all desired user story phases complete

### User Story Dependencies

| Story | Depends On | Can Start After |
|-------|-----------|-----------------|
| US1 — Instant Alert (P1) | Phase 2 complete | T011 checkpoint |
| US2 — Digest (P2) | Phase 2 + US1 router | T018 checkpoint |
| US3 — Dedup (P3) | Phase 2 + US1 engine | T018 checkpoint |
| US4 — Scale (P4) | Phase 2 + US1 engine | T018 checkpoint (metrics instrument after US1 works) |

### Within Each Phase

- Models / types → services → wiring
- `[P]` tasks within the same phase can execute concurrently (different files)
- Ack message only after full processing

### Parallel Opportunities

```bash
# Phase 1: all three tasks can run together
T001 (go.mod) | T002 (dirs) | T003 (Dockerfile)

# Phase 2: three independent foundations
T004 (migration) | T005 (libs model) | T006 (config)
# → then T007 (repository/rules.go)
# → then T008 (cache) | T009 (publisher)
# → then T010 (consumer) → T011 (main.go skeleton)

# Phase 3: models in parallel, then services
T012 (filter.go) | T013 (zone.go) | T016 (history.go)
# → then T014 (engine.go) → T015 (router.go) → T017 (consumer wire) → T018 (main.go)

# Phase 4: buffer + summaries in parallel
T019 (buffer.go) | T021 (FetchListingSummaries)
# → then T020 (router update) → T022 (compiler.go) → T023 (main.go)

# Phase 7: all infra tasks in parallel
T032 | T033 | T034 | T035
```

---

## Implementation Strategy

### MVP First (US1 Only — Instant Alerts)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL)
3. Complete Phase 3: US1 — Instant Alert
4. **STOP and VALIDATE**: one scored listing → one notification event in < 500ms
5. Service is production-useful at this point

### Incremental Delivery

1. Setup + Foundational → service boots, health passes
2. US1 → instant alerts work end-to-end ← **MVP**
3. US2 → digest delivery works
4. US3 → dedup prevents noise
5. US4 → metrics + scale hardening
6. Polish → Helm, lint, integration test

### Parallel Team Strategy

After Phase 2:
- **Dev A**: US1 (T012–T018)
- **Dev B**: US2 (T019–T023) — can start on `buffer.go` in parallel with Dev A
- **Dev C**: US3 (T024–T026) — can start `dedup.go` before US1 is complete; integration step T025 waits for T014

---

## Notes

- `[P]` = different files, no unmet dependencies in current phase
- `[Story]` label maps task to user story for traceability
- Each story phase is independently completable and testable before moving on
- Dedup (US3) integrates into the `Engine` struct (T025) — coordinate with the US1 `engine.go` author
- The `libs/pkg/models/alert.go` update (T005) is a breaking change for any other service importing it — check `api-gateway` imports after applying
- Run `go work sync` from repo root after updating `services/alert-engine/go.mod`
