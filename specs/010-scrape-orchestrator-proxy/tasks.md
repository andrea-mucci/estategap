# Tasks: Scrape Orchestrator & Proxy Manager

**Input**: Design documents from `/specs/010-scrape-orchestrator-proxy/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to
- Paths follow the monorepo layout defined in plan.md

---

## Phase 1: Setup (Proto & Module Scaffolding)

**Purpose**: Update shared proto contract and wire both service `go.mod` files before any
implementation can begin. Both services depend on the generated proto bindings.

- [X] T001 Update `proto/estategap/v1/proxy.proto` — add `string session_id = 3` to `GetProxyRequest` per `contracts/proxy.proto.updated`
- [ ] T002 Run `buf generate` from repo root and verify Go bindings regenerated in `libs/pkg/proto/estategap/v1/`
- [X] T003 [P] Update `services/scrape-orchestrator/go.mod` — add chi v5.2.1, pgx v5.7.2, go-redis v9.7.0, nats.go v1.37.0, uuid v1.6.0, viper v1.19.0, estategap/libs; run `go mod tidy`
- [X] T004 [P] Update `services/proxy-manager/go.mod` — add go-redis v9.7.0, grpc v1.67.1, prometheus/client_golang v1.20.5, uuid v1.6.0, viper v1.19.0, estategap/libs; run `go mod tidy`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared infrastructure packages for both services. No user story work can begin
until config, Redis clients, DB pool, NATS client, and provider adapters exist.

**⚠️ CRITICAL**: These tasks block all user story phases.

- [X] T005 [P] Implement `services/scrape-orchestrator/internal/config/config.go` — viper-backed struct with DATABASE_URL, REDIS_URL, NATS_URL, HTTP_PORT (8082), PORTAL_RELOAD_INTERVAL (5m), JOB_TTL (86400)
- [X] T006 [P] Implement `services/proxy-manager/internal/config/config.go` — viper-backed struct with REDIS_URL, GRPC_PORT (50052), METRICS_PORT (9090), BLACKLIST_TTL (1800), STICKY_TTL (600), HEALTH_THRESHOLD (0.5), PROXY_COUNTRIES + per-country provider/endpoint/username/password vars
- [X] T007 [P] Implement `services/scrape-orchestrator/internal/redisclient/client.go` — go-redis v9 pool setup, Ping health check, exported `Client` type
- [X] T008 [P] Implement `services/proxy-manager/internal/redisclient/client.go` — go-redis v9 pool setup, Ping health check, exported `Client` type
- [X] T009 Implement `services/scrape-orchestrator/internal/db/db.go` — pgxpool setup + `QueryPortals(ctx) ([]Portal, error)` selecting name, country, scrape_frequency, search_urls from portals where enabled=true
- [X] T010 Implement `services/scrape-orchestrator/internal/natsutil/client.go` — JetStream connection wrapper with `Publish(subject string, payload []byte) error` and reconnect-on-error logic
- [X] T011 [P] Implement `services/proxy-manager/internal/provider/provider.go` — `ProxyProvider` interface with `BuildProxyURL(username, password, endpoint, sessionID string) string` and `Name() string`
- [X] T012 [P] Implement `services/proxy-manager/internal/provider/brightdata.go` — `BrightDataAdapter` building `http://{user}-session-{sid}:{pass}@{endpoint}` (omit session suffix when sessionID is empty)
- [X] T013 [P] Implement `services/proxy-manager/internal/provider/smartproxy.go` — `SmartProxyAdapter` building `http://{user}:{pass}@{endpoint}` (SmartProxy uses username suffix for sticky: append `-sessid-{sid}`)
- [X] T014 [P] Implement `services/proxy-manager/internal/provider/oxylabs.go` — `OxylabsAdapter` building `http://{user}-sessid-{sid}:{pass}@{endpoint}` (omit sessid suffix when empty)
- [X] T015 Implement `services/proxy-manager/internal/provider/registry.go` — `NewProvider(name string) (ProxyProvider, error)` returning correct adapter; `provider_test.go` with table-driven tests for all three URL formats (with and without session ID)

**Checkpoint**: All shared infrastructure ready — user story phases can now begin.

---

## Phase 3: User Story 3 — Healthy Proxy Selection (Priority: P1) 🎯 MVP

**Goal**: The proxy manager gRPC server returns a healthy, non-blacklisted proxy within 10ms,
with support for sticky sessions and provider-specific URL construction.

**Independent Test**: Start proxy-manager with `PROXY_COUNTRIES=IT` and mock provider creds.
Call `GetProxy("IT", "immobiliare", "")` via grpcurl → receive a proxy URL.
Report a 429 via `ReportResult` → same proxy no longer returned.
Call `GetProxy` with `session_id="s1"` twice → same proxy returned both times.

- [X] T016 [P] [US3] Implement `services/proxy-manager/internal/pool/health.go` — `HealthWindow` circular buffer `[100]bool` with `Record(success bool)`, `Score() float64` (returns 1.0 when count=0), and `health_test.go` with table-driven tests covering: fresh window, all failures, 50% boundary, score recovery after failures
- [X] T017 [P] [US3] Implement `services/proxy-manager/internal/blacklist/blacklist.go` — `IsBlacklisted(ctx, ip string) bool` (Redis GET), `Blacklist(ctx, ip string, ttl time.Duration) error` (Redis SET EX); `blacklist_test.go` using testcontainers-go Redis
- [X] T018 [P] [US3] Implement `services/proxy-manager/internal/sticky/sticky.go` — `Get(ctx, sessionID string) (proxyID string, found bool)` (Redis GETEX to renew TTL), `Set(ctx, sessionID, proxyID string, ttl time.Duration) error`; `sticky_test.go` using testcontainers-go Redis verifying TTL renewal
- [X] T019 [US3] Implement `services/proxy-manager/internal/pool/pool.go` — `ProxyPool` with `map[string][]*Proxy` + `sync.RWMutex`; `LoadFromConfig(cfg *config.Config, registry ProviderRegistry) error` building pool from env vars; `Select(ctx, country string, redis *redisclient.Client, blacklist *blacklist.Blacklist, sessionID string, sticky *sticky.Sticky) (*Proxy, error)` implementing round-robin with health filtering and Redis pipeline batch blacklist check; `pool_test.go` with cases: healthy selection, all-blacklisted returns error, sticky returns same proxy
- [X] T020 [US3] Implement `services/proxy-manager/internal/grpc/server.go` — `ProxyServiceServer` implementing `GetProxy` (load sticky → filter healthy → batch blacklist check → round-robin select → set sticky if session → build URL via adapter → return) and `ReportResult` (record to HealthWindow → if status 403/429 call blacklist → update metrics); `server_test.go` with unit tests mocking Redis
- [X] T021 [US3] Wire `services/proxy-manager/cmd/main.go` — load config, init Redis client, load proxy pool, start gRPC server on configured port, register graceful shutdown on SIGTERM/SIGINT (`grpcServer.GracefulStop()`)

**Checkpoint**: `go run ./cmd/main.go` in proxy-manager starts gRPC on :50052. `GetProxy` returns
a proxy URL; `ReportResult` with status 429 blacklists the IP.

---

## Phase 4: User Story 1 — Scheduled Scrape Job Dispatch (Priority: P1)

**Goal**: The orchestrator loads all enabled portals from PostgreSQL on startup, creates one
ticker per portal at its configured interval, and publishes NATS job messages automatically.
Config reloads on SIGHUP or every 5 minutes without restart.

**Independent Test**: Insert a test portal row in DB with `scrape_frequency='15 seconds'` and
`enabled=true`. Start orchestrator. Within 15s a JSON message appears on
`scraper.commands.{country}.{portal}` in NATS. Send SIGHUP after disabling the portal in DB →
no further messages published for that portal.

- [X] T022 [P] [US1] Implement `services/scrape-orchestrator/internal/job/job.go` — `ScrapeJob` struct matching NATS JSON schema (job_id, portal, country, mode, zone_filter, search_url, created_at); `Save(ctx, rdb) error` writing Redis hash `jobs:{job_id}` with TTL; `Marshal() ([]byte, error)` for NATS payload; `job_test.go` with unit tests for serialization and Redis round-trip using testcontainers-go
- [X] T023 [US1] Implement `services/scrape-orchestrator/internal/scheduler/scheduler.go` — `Scheduler` struct holding `map[string]*portalTicker` (keyed by portal name) + `sync.Mutex`; `Start(ctx, db, nats, rdb)` loading portals and creating tickers; `publishJob(portal Portal, mode string)` generating UUID job_id, building `ScrapeJob`, publishing to `scraper.commands.{country}.{portal}`, saving status `pending` to Redis; `Reload(ctx, db)` reconciling ticker map (add new, stop removed, restart changed-interval); `scheduler_test.go` verifying tick fires, reload adds/removes portals
- [X] T024 [US1] Implement SIGHUP + periodic reload goroutine in `services/scrape-orchestrator/internal/scheduler/scheduler.go` — `WatchReload(ctx, db, interval time.Duration)` listening on `signal.Notify(sigCh, syscall.SIGHUP)` and also firing a `time.Ticker` at the configured interval; calls `Reload` on both triggers

**Checkpoint**: Orchestrator publishes to NATS on schedule. Manual `kill -HUP` triggers reload.
Jobs appear in Redis as `pending` with correct fields and 24h TTL.

---

## Phase 5: User Story 2 — Manual Job Trigger (Priority: P1)

**Goal**: An operator can POST to `/jobs/trigger` to immediately publish a scrape job outside
the regular schedule, and retrieve its current status via `/jobs/{id}/status`.

**Independent Test**: `curl -X POST http://localhost:8082/jobs/trigger` with valid body →
202 response with job_id → `curl http://localhost:8082/jobs/{id}/status` returns `pending`.
NATS message visible on correct subject within 1 second.

- [X] T025 [P] [US2] Implement `services/scrape-orchestrator/internal/handler/trigger.go` — `POST /jobs/trigger` handler: decode request body (portal, country, mode, zone_filter, search_url), validate required fields, call scheduler's `publishJob`, return 202 with job_id; return 400 on missing fields, 503 if NATS publish fails
- [X] T026 [P] [US2] Implement `services/scrape-orchestrator/internal/handler/status.go` — `GET /jobs/{id}/status` handler: read Redis hash `jobs:{id}` via HGETALL, return 200 with all fields as JSON, return 404 if key missing
- [X] T027 [P] [US2] Implement `services/scrape-orchestrator/internal/handler/health.go` — `GET /health` handler: ping PostgreSQL, NATS, and Redis; return 200 `{"status":"ok","db":"ok","nats":"ok","redis":"ok"}` or 503 with failing components
- [X] T028 [P] [US2] Implement `services/scrape-orchestrator/internal/middleware/logging.go` — chi middleware wrapping `slog` structured request logging (method, path, status code, duration)
- [X] T029 [US2] Wire `services/scrape-orchestrator/cmd/main.go` — load config, init DB pool, Redis client, NATS client, scheduler (Start + WatchReload goroutines), chi router with all handlers and logging middleware on port 8082, graceful shutdown on SIGTERM/SIGINT (stop scheduler tickers, drain NATS, close DB pool)

**Checkpoint**: Full orchestrator running. Manual trigger works end-to-end. Scheduled ticks
and manual triggers both produce NATS messages and trackable Redis job records.

---

## Phase 6: User Story 4 — Proxy Health Observability (Priority: P2)

**Goal**: Prometheus metrics `proxy_pool_size`, `proxy_healthy_count`, and `proxy_block_rate`
are exposed per country and provider, updated after every `ReportResult` call.

**Independent Test**: Start proxy-manager. `curl http://localhost:9090/metrics | grep proxy_`
returns all three metric families with correct `country` and `provider` labels. Blacklist a
proxy via `ReportResult(429)` → `proxy_healthy_count` decreases, `proxy_block_rate` increases.

- [X] T030 [P] [US4] Implement `services/proxy-manager/internal/metrics/metrics.go` — register three Prometheus `GaugeVec` metrics (`proxy_pool_size`, `proxy_healthy_count`, `proxy_block_rate`) with labels `country` and `provider`; export `Update(country, provider string, poolSize, healthyCount int, blockRate float64)` function called from `ReportResult`
- [X] T031 [US4] Add Prometheus metrics HTTP endpoint to `services/proxy-manager/cmd/main.go` — start `net/http` server on `METRICS_PORT` (default 9090) serving `promhttp.Handler()` at `/metrics`; update `grpc/server.go` `ReportResult` to call `metrics.Update` after every result recording

**Checkpoint**: Metrics endpoint live. Grafana/Prometheus can scrape proxy pool health per country.

---

## Phase 7: User Story 5 — Job Status Observability (Priority: P2)

**Goal**: `GET /jobs/stats` returns aggregated counts of pending/running/completed/failed jobs,
giving operators a live view of pipeline throughput.

**Independent Test**: Trigger 3 jobs (manual). `curl http://localhost:8082/jobs/stats` →
`{"pending":3,"running":0,"completed":0,"failed":0,"total":3}`.

- [X] T032 [US5] Implement `services/scrape-orchestrator/internal/handler/stats.go` — `GET /jobs/stats` handler: use Redis `SCAN` with pattern `jobs:*` and `COUNT 100` cursor loop, pipeline `HGET status` for each key, aggregate counts by status value, return JSON `{pending, running, completed, failed, total}`; register route in `cmd/main.go` chi router

**Checkpoint**: All five user stories are fully functional and independently verifiable.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Integration tests, environment documentation, and deployment readiness.

- [ ] T033 [P] Write integration test `services/scrape-orchestrator/internal/scheduler/integration_test.go` — testcontainers-go spinning up PostgreSQL + NATS + Redis; insert enabled portal; start scheduler; assert NATS message received within 2× interval; assert Redis job key created with status `pending`
- [ ] T034 [P] Write integration test `services/proxy-manager/internal/grpc/integration_test.go` — testcontainers-go spinning up Redis; load pool with mock provider; call `GetProxy` → assert proxy returned; call `ReportResult(429)` → assert `IsBlacklisted` returns true; call `GetProxy` again → assert different proxy (or NOT_FOUND if single proxy)
- [X] T035 [P] Update `services/scrape-orchestrator/.env.example` with all required vars: DATABASE_URL, REDIS_URL, NATS_URL, HTTP_PORT, PORTAL_RELOAD_INTERVAL, JOB_TTL; one example value per var
- [X] T036 [P] Update `services/proxy-manager/.env.example` with all required vars: REDIS_URL, GRPC_PORT, METRICS_PORT, BLACKLIST_TTL, STICKY_TTL, HEALTH_THRESHOLD, PROXY_COUNTRIES, PROXY_{CC}_PROVIDER/ENDPOINT/USERNAME/PASSWORD (example for IT and ES)
- [ ] T037 Verify both service `Dockerfile`s build cleanly (`docker build -t scrape-orchestrator services/scrape-orchestrator` and `docker build -t proxy-manager services/proxy-manager`) and confirm ENTRYPOINT matches `cmd/main.go` binary path
- [ ] T038 Run `golangci-lint run ./...` in both services and fix any reported issues

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 (T001–T004 complete) — **BLOCKS all user stories**
- **Phase 3 (US3)**: Depends on Phase 2 complete — Proxy Manager core
- **Phase 4 (US1)**: Depends on Phase 2 complete — Orchestrator scheduler (independent of US3)
- **Phase 5 (US2)**: Depends on Phase 4 complete — Orchestrator HTTP API uses scheduler's publishJob
- **Phase 6 (US4)**: Depends on Phase 3 complete — adds metrics to proxy manager
- **Phase 7 (US5)**: Depends on Phase 5 complete — adds stats handler to orchestrator
- **Phase 8 (Polish)**: Depends on Phases 3–7 complete

### User Story Dependencies

- **US3 (P1)**: Unblocked after Phase 2 — no dependency on orchestrator stories
- **US1 (P1)**: Unblocked after Phase 2 — no dependency on proxy manager stories
- **US2 (P1)**: Depends on US1 (reuses `publishJob` from scheduler)
- **US4 (P2)**: Depends on US3 (adds metrics layer to existing gRPC server)
- **US5 (P2)**: Depends on US2 (adds stats handler to existing chi router)

### Within Each Phase

- Models/entities before services
- Services before gRPC/HTTP wiring
- Core implementation before integration
- `cmd/main.go` wiring is always last within each service

### Parallel Opportunities

- T003 and T004 (go.mod updates) — parallel, different files
- T005–T015 (foundational) — T005/T006, T007/T008, T011/T012/T013/T014 each parallelizable
- T016, T017, T018 (US3 leaf tasks) — parallel, different packages
- T022 (US1 job entity) — parallel with T025–T028 (US2 handlers, different packages)
- T025, T026, T027, T028 (US2 handlers) — parallel, four different files
- T030 (metrics defs) — parallel with T031 wiring (define before wire)
- T033, T034, T035, T036 (Phase 8 parallel tasks) — fully independent

---

## Parallel Example: Phase 2 (Foundational)

```bash
# Batch 1 — after T001/T002 (proto) complete:
Task T003: Update scrape-orchestrator/go.mod
Task T004: Update proxy-manager/go.mod

# Batch 2 — configs and Redis clients (once go.mod done):
Task T005: scrape-orchestrator config
Task T006: proxy-manager config
Task T007: scrape-orchestrator Redis client
Task T008: proxy-manager Redis client

# Batch 3 — provider adapters (parallel, different files):
Task T011: provider.go interface
Task T012: brightdata.go
Task T013: smartproxy.go
Task T014: oxylabs.go
```

## Parallel Example: Phase 3 (US3 — Proxy Manager)

```bash
# Batch 1 — leaf packages with no inter-dependency:
Task T016: pool/health.go + health_test.go
Task T017: blacklist/blacklist.go + blacklist_test.go
Task T018: sticky/sticky.go + sticky_test.go

# Then sequential:
Task T019: pool/pool.go (depends on health, blacklist, sticky)
Task T020: grpc/server.go (depends on pool)
Task T021: cmd/main.go wiring (depends on T020)
```

---

## Implementation Strategy

### MVP First (US3 + US1 only)

1. Complete Phase 1: Setup (T001–T004)
2. Complete Phase 2: Foundational (T005–T015) — **critical blocker**
3. Complete Phase 3: US3 Proxy Selection (T016–T021)
4. Complete Phase 4: US1 Scheduled Dispatch (T022–T024)
5. **STOP and VALIDATE**: grpcurl returns proxy; NATS messages flow on schedule
6. Deploy for integration testing with spider workers

### Incremental Delivery

1. Setup + Foundational → both services can compile
2. US3 → proxy-manager gRPC operational ✓
3. US1 → scheduled publishing operational ✓
4. US2 → manual trigger + status API operational ✓ (full MVP)
5. US4 → proxy metrics in Grafana ✓
6. US5 → job stats visible ✓
7. Polish → lint clean, integration tests green, Dockerfiles verified ✓

### Parallel Team Strategy

With two developers after Phase 2:
- **Developer A**: Phase 3 (US3 — proxy-manager) → Phase 6 (US4 metrics)
- **Developer B**: Phase 4 (US1 scheduler) → Phase 5 (US2 HTTP API) → Phase 7 (US5 stats)
- Both merge independently; no shared files between the two services

---

## Notes

- [P] tasks = different files, no shared state dependencies — safe to run in parallel
- [USn] label maps every task to a specific user story for traceability
- Proto update (T001–T002) must complete before any service code that imports generated types
- `buf generate` (T002) regenerates `libs/pkg/` — commit generated files before starting service tasks
- Each service `cmd/main.go` wiring task (T021, T029) is always last in its service sequence
- `testcontainers-go` integration tests require Docker — run with `go test -tags integration ./...`
- Commit after each checkpoint to enable bisect if regressions appear
