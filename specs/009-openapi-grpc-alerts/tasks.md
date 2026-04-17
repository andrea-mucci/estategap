# Tasks: OpenAPI Documentation, gRPC Clients & Alert Rules

**Input**: Design documents from `specs/009-openapi-grpc-alerts/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Organization**: Tasks are grouped by user story. Three independent delivery streams:
- **Stream A** (US1): Swagger UI + OpenAPI spec — no DB or gRPC dependencies
- **Stream B** (US2): gRPC client hardening + ML estimate endpoint
- **Stream C** (US3 + US4): Alert rules DB migration → repository → CRUD handlers → history

All three streams can begin after Phase 2 (Foundational) completes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3, US4)
- Exact file paths included in every description

---

## Phase 1: Setup

**Purpose**: Add new dependencies required by this feature

- [X] T001 Add `gopkg.in/yaml.v3` to `services/api-gateway/go.mod` and run `go mod tidy` in `services/api-gateway/`
- [X] T002 [P] Add `openapi-typescript` as a devDependency in `frontend/package.json` and add script `"generate:types": "openapi-typescript ../services/api-gateway/openapi.yaml -o src/types/api.ts"`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Infrastructure that blocks multiple user stories — complete before any story work

**⚠️ CRITICAL**: US3 and US4 cannot start until T003 (migration) is done. US2 cannot start until T004–T005 are done.

- [X] T003 Write Alembic migration in `services/pipeline/alembic/versions/<timestamp>_add_alert_rules_and_history.py` creating `alert_rules` and `alert_history` tables with all columns, constraints, and indexes exactly as specified in `specs/009-openapi-grpc-alerts/data-model.md`; verify with `cd services/pipeline && uv run alembic upgrade head && uv run alembic downgrade -1 && uv run alembic upgrade head`
- [X] T004 [P] Update `services/api-gateway/internal/config/config.go` to load and expose `GRPCMLScorerAddr` (env: `GRPC_ML_SCORER_ADDR`, default: `ml-scorer.estategap-intelligence.svc.cluster.local:50051`), `GRPCChatAddr` (env: `GRPC_AI_CHAT_ADDR`, default: `ai-chat-service.estategap-intelligence.svc.cluster.local:50051`), `GRPCTimeoutSeconds` (env: `GRPC_TIMEOUT_SECONDS`, default: `5`), `GRPCCBThreshold` (env: `GRPC_CB_THRESHOLD`, default: `5`), `GRPCCBWindowSeconds` (env: `GRPC_CB_WINDOW_SECONDS`, default: `30`), `GRPCCBCooldownSeconds` (env: `GRPC_CB_COOLDOWN_SECONDS`, default: `30`)
- [X] T005 [P] Write `services/api-gateway/internal/grpc/circuit_breaker.go` implementing `CircuitBreaker` struct with three `sync/atomic` fields (`state int32`, `failures int32`, `lastFailureUnix int64`), configurable `Threshold int`, `WindowSecs int64`, `CooldownSecs int64`, and methods `Allow() bool`, `RecordSuccess()`, `RecordFailure()` implementing the closed→open→half-open→closed state machine described in `specs/009-openapi-grpc-alerts/research.md`

**Checkpoint**: Migration applied; config fields available; circuit breaker type ready — stream work can begin

---

## Phase 3: User Story 1 — Interactive API Documentation (Priority: P1) 🎯 MVP Stream A

**Goal**: Swagger UI loads at `/api/docs`; full OpenAPI 3.1 spec served at `/api/openapi.json`; "Try it out" works with JWT

**Independent Test**: Start the API Gateway locally, open `http://localhost:8080/api/docs`, click Authorize, enter a valid JWT, and successfully execute `GET /api/v1/auth/me` from the UI

### Implementation

- [X] T006 [US1] Create directory `services/api-gateway/internal/docs/swagger-ui/`; download Swagger UI v5.x distribution files (`swagger-ui-bundle.js`, `swagger-ui-bundle.js.map`, `swagger-ui.css`) from the official GitHub release and place them there; write `services/api-gateway/internal/docs/swagger-ui/index.html` as a minimal Swagger UI bootstrap page with `url: "/api/openapi.json"`, `persistAuthorization: true`, `deepLinking: true`, and `dom_id: "#swagger-ui"`
- [X] T007 [P] [US1] Write `services/api-gateway/openapi.yaml` as a complete, hand-authored OpenAPI 3.1 specification covering: all auth endpoints (`/api/v1/auth/*`), all listing/zone endpoints (`/api/v1/listings/*`, `/api/v1/zones/*`), subscription endpoints (`/api/v1/subscriptions/*`), webhook endpoint, health/readiness/metrics endpoints, and all new endpoints from `specs/009-openapi-grpc-alerts/contracts/openapi-new-endpoints.yaml`; include `BearerAuth` security scheme, request body schemas, response schemas for all 2xx and error responses, and `example` values on all fields
- [X] T008 [US1] Write `services/api-gateway/internal/handler/docs.go` with: `//go:embed` directive for `../docs/swagger-ui/*`; an `init`-time conversion of the embedded `openapi.yaml` bytes to JSON using `gopkg.in/yaml.v3` and `encoding/json`, cached as a package-level `[]byte`; `ServeOpenAPISpec(w http.ResponseWriter, r *http.Request)` handler returning the cached JSON with `Content-Type: application/json`; `ServeSwaggerUI(w http.ResponseWriter, r *http.Request)` handler serving static files from the embedded FS with correct MIME types
- [X] T009 [US1] Register routes in the API Gateway router setup file (locate via `grep -r "chi.NewRouter\|r.Get\|r.Route" services/api-gateway/cmd/` or `services/api-gateway/internal/`): add `r.Get("/api/openapi.json", docsHandler.ServeOpenAPISpec)`, `r.Get("/api/docs", http.RedirectHandler("/api/docs/", http.StatusMovedPermanently).ServeHTTP)`, `r.Get("/api/docs/*", docsHandler.ServeSwaggerUI)` — all without auth middleware
- [X] T010 [US1] Write `services/api-gateway/internal/handler/docs_test.go` with table-driven unit tests using `net/http/httptest`: verify `GET /api/openapi.json` returns 200 with `Content-Type: application/json` and valid parseable JSON; verify `GET /api/docs/index.html` returns 200 with `Content-Type: text/html`; verify spec JSON contains `"openapi": "3.1.0"` and `"title"` fields

**Checkpoint**: US1 fully functional — navigate to `/api/docs` in browser and test an endpoint end-to-end

---

## Phase 4: User Story 2 — On-Demand Property Valuation (Priority: P1) Stream B

**Goal**: `GET /api/v1/model/estimate?listing_id=<uuid>` returns ML valuation within 5s; circuit breaker opens after 5 consecutive failures and recovers after 30s cooldown

**Independent Test**: Call the estimate endpoint with a valid JWT and listing ID; bring down ml-scorer port-forward and call 6 times to confirm the 6th call returns 503 immediately (circuit open)

### Implementation

- [X] T011 [US2] Update `services/api-gateway/internal/grpc/ml_client.go`: replace `grpc.Dial` with `grpc.NewClient`; add `grpc.WithDefaultServiceConfig` with JSON retry policy `{"methodConfig":[{"name":[{"service":""}],"retryPolicy":{"maxAttempts":4,"initialBackoff":"0.1s","maxBackoff":"1s","backoffMultiplier":2.0,"retryableStatusCodes":["UNAVAILABLE"]},"timeout":"5s"}]}`; add a `*CircuitBreaker` field to `MLClient`; wrap `ScoreListing` to call `cb.Allow()` before the gRPC call — return a synthetic `codes.Unavailable` error immediately if the CB is open; call `cb.RecordSuccess()` or `cb.RecordFailure()` based on the gRPC call outcome; construct the `CircuitBreaker` in `NewMLClient` using threshold/window/cooldown from the passed-in config values
- [X] T012 [P] [US2] Update `services/api-gateway/internal/grpc/chat_client.go`: replace `grpc.Dial` with `grpc.NewClient`; add the same `grpc.WithDefaultServiceConfig` retry JSON as T011 (no circuit breaker for chat client per research.md); add a 5-second context deadline wrapper in `StreamChat`
- [X] T013 [US2] Write `services/api-gateway/internal/grpc/circuit_breaker_test.go` with table-driven tests covering: 5 failures in window → state transitions to open; call while open returns `Allow()=false`; 30s elapsed → state transitions to half-open; probe success → back to closed; probe failure → back to open; failures outside window do not accumulate (use a mock clock via a `nowFunc func() int64` field on `CircuitBreaker` for testability)
- [X] T014 [US2] Write `services/api-gateway/internal/handler/ml.go` with `Estimate(w http.ResponseWriter, r *http.Request)`: parse and validate `listing_id` query param as UUID (return 400 if missing or malformed); apply a 5-second `context.WithTimeout`; call `mlClient.ScoreListing`; map response proto fields to the `MLEstimate` JSON shape from `specs/009-openapi-grpc-alerts/data-model.md`; map gRPC `codes.Unavailable` (including circuit-open sentinel) → HTTP 503 with `{"error":"ML scoring service is temporarily unavailable","code":"ML_SCORER_UNAVAILABLE"}`; map `codes.NotFound` → HTTP 404; map context deadline exceeded → HTTP 503
- [X] T015 [US2] Register `r.Get("/api/v1/model/estimate", authMiddleware(mlHandler.Estimate))` in the same router setup file updated in T009; wire up the `MLClient` instance using addresses and config from T004
- [X] T016 [US2] Write `services/api-gateway/internal/handler/ml_test.go` with integration tests using `google.golang.org/grpc/test/bufconn` as an in-process gRPC server: test successful estimate returns 200 with all `MLEstimate` fields; test ml-scorer returning `codes.Unavailable` maps to HTTP 503; test context timeout maps to HTTP 503; test invalid UUID returns 400; test circuit breaker opens after 5 simulated failures and subsequent call returns 503 without hitting the mock server

**Checkpoint**: US2 fully functional — estimate endpoint returns valuations; circuit breaker behavior verified

---

## Phase 5: User Story 3 — Alert Rules Management with Tier Limits (Priority: P1) Stream C

**Goal**: Free users get 403 on creation; Basic users are capped at 3; Pro/Global/API users have unlimited rules; all filter fields and zone IDs are validated before save

**Independent Test**: Use the tier-limit matrix: create rules as Pro (succeeds), attempt creation as free (403), create 3 as Basic and attempt 4th (422 TIER_LIMIT_REACHED), submit rule with invalid zone ID (422 INVALID_ZONE_IDS), submit rule with disallowed filter field (422 INVALID_FILTER_FIELDS)

### Implementation

- [X] T017 [US3] Write `services/api-gateway/internal/repository/alert_rules.go` with the following functions using `pgx/v5` (no ORM): `CountActiveRules(ctx context.Context, db pgxpool.Pool, userID uuid.UUID) (int, error)` using `SELECT COUNT(*) FROM alert_rules WHERE user_id = $1 AND is_active = true`; `CreateRule(ctx, db, rule AlertRuleInput) (*AlertRule, error)` using `INSERT ... RETURNING *`; `ListRules(ctx, db, userID, page, pageSize int, isActive *bool) ([]AlertRule, int, error)` with optional `is_active` filter and `COUNT(*) OVER()` for total; `GetRule(ctx, db, id, userID uuid.UUID) (*AlertRule, error)` selecting by both id and user_id for ownership check; `UpdateRule(ctx, db, id, userID uuid.UUID, input UpdateRuleInput) (*AlertRule, error)` with only non-zero fields updated; `DeleteRule(ctx, db, id, userID uuid.UUID) error` setting `is_active = false, updated_at = NOW()`; `ValidateZoneIDs(ctx, db, zoneIDs []uuid.UUID) (invalid []uuid.UUID, err error)` returning zone IDs not found in `SELECT id FROM zones WHERE id = ANY($1) AND is_active = true`; define Go structs `AlertRule`, `AlertRuleInput`, `UpdateRuleInput` matching the JSON shapes in `data-model.md`
- [X] T018 [US3] Write `services/api-gateway/internal/handler/alert_rules.go` with: package-level `var tierAlertRuleLimits = map[string]int{"free":0,"basic":3,"pro":-1,"global":-1,"api":-1}`; package-level `var allowedFilterFields = map[string]map[string]bool{...}` covering all four categories from `research.md`; `validateAlertFilter(category string, filter map[string]any) []string` returning disallowed field names; `ListAlertRules`, `CreateAlertRule`, `UpdateAlertRule`, `DeleteAlertRule` handler functions; `CreateAlertRule` must: (1) decode request body, (2) look up tier from JWT user context, (3) check `tierAlertRuleLimits[tier]` — return 403 if 0, (4) call `repo.CountActiveRules` and compare to limit (skip if limit == -1) — return 422 with `TIER_LIMIT_REACHED` if exceeded, (5) call `repo.ValidateZoneIDs` — return 422 with `INVALID_ZONE_IDS` + detail if any invalid, (6) call `validateAlertFilter` — return 422 with `INVALID_FILTER_FIELDS` + detail if any invalid, (7) call `repo.CreateRule` and return 201
- [X] T019 [US3] Register alert rules routes in router setup file: `r.Route("/api/v1/alerts", func(r chi.Router) { r.Use(authMiddleware); r.Get("/rules", alertHandler.ListAlertRules); r.Post("/rules", alertHandler.CreateAlertRule); r.Put("/rules/{id}", alertHandler.UpdateAlertRule); r.Delete("/rules/{id}", alertHandler.DeleteAlertRule) })`; wire `alertHandler` with the DB pool from the existing app context
- [X] T020 [P] [US3] Write unit tests in `services/api-gateway/internal/handler/alert_rules_test.go` for `validateAlertFilter`: table-driven test covering every category with an allowed field (expect empty result), a disallowed field (expect that field in result), and an empty filter (expect empty result)
- [X] T021 [P] [US3] Write unit tests in `services/api-gateway/internal/handler/alert_rules_test.go` for tier enforcement: table-driven test with inputs `(tier string, currentCount int, limit int)` and expected HTTP status: free+0 → 403; basic+2 → proceed to next validation; basic+3 → 422 TIER_LIMIT_REACHED; pro+999 → proceed; mock the `repo.CountActiveRules` call with a stub that returns the given count
- [ ] T022 [US3] Write integration tests in `services/api-gateway/internal/repository/alert_rules_test.go` using `testcontainers-go` with a PostgreSQL 16 container: run the migration DDL from `data-model.md` in test setup; test `CountActiveRules` returns correct count after inserts and soft deletes; test `CreateRule` persists all fields correctly; test `ListRules` pagination (page 1 and page 2); test `GetRule` returns 404 (nil) for wrong userID; test `UpdateRule` updates only provided fields; test `DeleteRule` sets is_active=false without deleting row; test `ValidateZoneIDs` returns only the UUIDs not found in the zones table

**Checkpoint**: US3 fully functional — all CRUD endpoints work; tier limits, filter validation, zone validation all enforced

---

## Phase 6: User Story 4 — Alert Delivery History (Priority: P2) Stream C (continued)

**Goal**: `GET /api/v1/alerts/history` returns paginated, filterable log of past firings with delivery status for the authenticated user

**Independent Test**: Insert test rows into `alert_history`; call `GET /api/v1/alerts/history?rule_id=<uuid>&delivery_status=failed&page=1&page_size=5` and verify only matching rows are returned with correct pagination metadata

### Implementation

- [X] T023 [US4] Add `ListHistory(ctx context.Context, db *pgxpool.Pool, userID uuid.UUID, filter HistoryFilter, page, pageSize int) ([]AlertHistoryEntry, int, error)` to `services/api-gateway/internal/repository/alert_rules.go`; `HistoryFilter` struct has optional `RuleID *uuid.UUID`, `DeliveryStatus *string`, `Since *time.Time`; query joins `alert_history` with `alert_rules` on `rule_id` filtering by `alert_rules.user_id = $1` (scopes to authenticated user); apply optional filters as additional `AND` clauses; include `COUNT(*) OVER()` for total count; order by `triggered_at DESC`; add `AlertHistoryEntry` Go struct matching the shape in `data-model.md`
- [X] T024 [US4] Add `ListAlertHistory(w http.ResponseWriter, r *http.Request)` handler to `services/api-gateway/internal/handler/alert_rules.go`: parse `page`, `page_size`, `rule_id`, `delivery_status`, `since` query params with validation (page ≥ 1, page_size 1–100, rule_id as UUID, delivery_status as one of pending/delivered/failed, since as RFC3339); call `repo.ListHistory`; return paginated response envelope matching `data-model.md` `PaginationMeta` shape
- [X] T025 [US4] Register `r.Get("/history", alertHandler.ListAlertHistory)` inside the existing `r.Route("/api/v1/alerts", ...)` block updated in T019
- [X] T026 [US4] Add integration tests for the history endpoint in `services/api-gateway/internal/handler/alert_rules_test.go` using `httptest`: test default pagination (returns up to 20 results); test `rule_id` filter returns only matching entries; test `delivery_status=failed` filter; test `since` timestamp filter; test that user A cannot see user B's history (different user_id in alert_rules)

**Checkpoint**: US4 fully functional — history endpoint paginated and filtered correctly; user isolation verified

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: TypeScript types, lint, and final validation

- [ ] T027 [P] Generate TypeScript types by running `cd frontend && npm run generate:types` (defined in T002); commit the generated `frontend/src/types/api.ts`
- [ ] T028 [P] Verify TypeScript types compile without errors: run `cd frontend && npx tsc --noEmit`; fix any type errors in the generated file or `openapi.yaml` schema definitions
- [ ] T029 Run `golangci-lint run ./...` in `services/api-gateway/` and fix any lint violations introduced by this feature
- [ ] T030 Run quickstart.md manual validation: (1) apply migration and start gateway locally; (2) open `/api/docs` in browser, authorize with JWT, execute one authenticated endpoint; (3) port-forward ml-scorer, call `/api/v1/model/estimate` and verify response; (4) kill ml-scorer port-forward, call estimate 6 times, verify 6th is instant 503; (5) create an alert rule as Pro user, verify 201; (6) attempt creation as free user, verify 403

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — blocks US2, US3, US4
- **Phase 3 (US1)**: Depends on Phase 1 only (no DB or gRPC needed) — can start before Phase 2 finishes (T007 can begin as soon as Phase 1 is done)
- **Phase 4 (US2)**: Depends on Phase 2 (T004, T005 must be complete)
- **Phase 5 (US3)**: Depends on Phase 2 (T003 migration must be applied)
- **Phase 6 (US4)**: Depends on Phase 5 (T023 extends T017 repository; T024 extends T018 handler)
- **Phase 7 (Polish)**: Depends on all story phases complete; T027/T028 need T007 (openapi.yaml) complete

### User Story Dependencies

- **US1**: Depends only on Phase 1 — fully independent of gRPC and DB
- **US2**: Depends on Phase 2 (T004 config, T005 circuit breaker) — independent of DB and alert rules
- **US3**: Depends on Phase 2 (T003 migration) — independent of gRPC
- **US4**: Depends on US3 (same tables, same repo and handler files) — must follow US3 completion

### Within Each User Story

- US1: T006 (assets) → T007 (spec, parallelizable) → T008 (handler) → T009 (routes) → T010 (tests)
- US2: T011 + T012 [P] → T013 → T014 → T015 → T016
- US3: T017 (repo) → T018 (handler) → T019 (routes); T020 + T021 [P] can run after T018; T022 after T017
- US4: T023 (extend repo) → T024 (extend handler) → T025 (register route) → T026 (tests)

### Parallel Opportunities

- T001 and T002 run in parallel (Phase 1)
- T003, T004, T005 run in parallel (Phase 2 — different files)
- T007 can be written in parallel with T006 (different files, both within US1)
- T011 and T012 run in parallel (different Go files, both within US2)
- T020 and T021 run in parallel (same test file, different test functions — coordinate to avoid conflicts or split into two test files)
- T027 and T028 run in parallel after T007 is complete (T027 generates, T028 verifies — T028 depends on T027)
- Once Phase 2 is complete: US1, US2, US3 streams can be executed in parallel by different developers

---

## Parallel Example: US3 (Alert Rules)

```
# After T003 (migration applied), launch repository work:
Task T017: "Write internal/repository/alert_rules.go with CountActiveRules, CreateRule, ListRules, GetRule, UpdateRule, DeleteRule, ValidateZoneIDs"

# After T017 completes, launch handler + tests in parallel:
Task T018: "Write internal/handler/alert_rules.go with all CRUD handlers, tier map, validateAlertFilter"
Task T022: "Write integration tests for repository/alert_rules.go with testcontainers"

# After T018 completes, launch in parallel:
Task T019: "Register alert routes in router"
Task T020: "Unit tests for validateAlertFilter"
Task T021: "Unit tests for tier enforcement"
```

---

## Implementation Strategy

### MVP First (US1 + US2 only, ~15 tasks)

1. Complete Phase 1 (T001, T002)
2. Complete Phase 2 (T003–T005) — in parallel where possible
3. Complete US1 (T006–T010) — Swagger UI working
4. Complete US2 (T011–T016) — ML estimate with circuit breaker
5. **STOP and VALIDATE**: Swagger UI interactive, ML estimate returning valuations, circuit breaker verified
6. Skip alert rules for now; ship US1 + US2

### Full Delivery (all 30 tasks)

1. Phase 1 → Phase 2 (parallel within each)
2. US1 + US2 + US3 streams in parallel (if team capacity allows)
3. US4 after US3
4. Phase 7 (polish) last

### Single Developer Sequence

1. T001 → T002 (quick — add deps)
2. T003 → T004 → T005 (foundational — ~2h)
3. T006 → T007 → T008 → T009 → T010 (US1 — ~3h)
4. T011 → T012 → T013 → T014 → T015 → T016 (US2 — ~3h)
5. T017 → T018 → T019 → T020 → T021 → T022 (US3 — ~4h)
6. T023 → T024 → T025 → T026 (US4 — ~2h)
7. T027 → T028 → T029 → T030 (polish — ~1h)

---

## Notes

- [P] tasks = different files, no mutual dependencies — safe to parallelize
- T020 and T021 write to the same test file; coordinate or split into `alert_rules_filter_test.go` and `alert_rules_tier_test.go`
- The `openapi.yaml` (T007) must document ALL existing endpoints from prior features, not just the new ones — use `specs/009-openapi-grpc-alerts/contracts/openapi-new-endpoints.yaml` as the contract for new endpoints and read existing handler files for all existing endpoint signatures
- T005 (`circuit_breaker.go`) should expose a `nowFunc func() int64` field (defaulting to `time.Now().Unix`) to allow deterministic testing in T013
- The Alembic migration in T003 lives in the `services/pipeline/` service — this is the designated home for DB migrations per project structure; coordinate with any concurrent pipeline changes
- Commit after each phase completes to keep the branch clean and reviewable
