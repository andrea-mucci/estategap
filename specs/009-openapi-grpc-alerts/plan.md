# Implementation Plan: OpenAPI Documentation, gRPC Clients & Alert Rules

**Branch**: `009-openapi-grpc-alerts` | **Date**: 2026-04-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/009-openapi-grpc-alerts/spec.md`

## Summary

Add three capabilities to the existing Go API Gateway: (1) hand-written OpenAPI 3.1 spec served with embedded Swagger UI at `/api/docs`; (2) production-grade gRPC client wrappers for ml-scorer and ai-chat-service with circuit breaker, retry policy, and 5s timeout; (3) alert rules CRUD endpoints backed by new `alert_rules` and `alert_history` tables, with server-side JSONB filter validation, zone ID validation, and subscription tier enforcement.

## Technical Context

**Language/Version**: Go 1.23
**Primary Dependencies**: chi v5.2.1, pgx v5.7.2, go-redis v9.7.0, google.golang.org/grpc (existing), gopkg.in/yaml.v3 (for YAML→JSON conversion), embed (stdlib)
**Storage**: PostgreSQL 16 + PostGIS 3.4 (new tables: alert_rules, alert_history); Redis 7 (existing; not used by this feature directly)
**Testing**: Go table-driven unit tests; testcontainers-based integration tests for repository layer
**Target Platform**: Linux (Kubernetes, amd64)
**Project Type**: web-service (API Gateway)
**Performance Goals**: Alert rule creation < 200ms p95; ML estimate proxy < 5s hard timeout; spec serving < 50ms
**Constraints**: No new third-party resilience libraries; circuit breaker via stdlib `sync/atomic`; Swagger UI assets embedded (no CDN)
**Scale/Scope**: Same user base as existing API (~10k concurrent users); alert rules: ~5–50 per user typical

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Polyglot Service Architecture | ✅ PASS | Changes are entirely within the Go api-gateway service. No service imports another service's internal packages. |
| II. Event-Driven Communication | ✅ PASS | gRPC used for ml-scorer and ai-chat — synchronous request/response pattern, correct per constitution. No direct HTTP between services. |
| III. Country-First Data Sovereignty | ✅ PASS | alert_rules.zone_ids references zones table (country-partitioned). No new denormalized country storage. |
| IV. ML-Powered Intelligence | ✅ PASS | `/api/v1/model/estimate` exposes ML scoring to end users, including SHAP values for explainability — directly supports this principle. |
| V. Code Quality Discipline | ✅ PASS | Go stdlib `slog` logging, `pgx` direct queries (no ORM), chi router, table-driven tests, golangci-lint. |
| VI. Security & Ethical Scraping | ✅ PASS | JWT auth enforced on all new authenticated endpoints. Tier limits enforced at DB query level. OpenAPI spec served without auth (documentation is public). |
| VII. Kubernetes-Native Deployment | ✅ PASS | gRPC targets use K8s service DNS. No new Helm chart changes needed; env vars cover config. |

**Post-Design Re-check**: All principles maintained. The embedded Swagger UI static assets (committed to `internal/docs/swagger-ui/`) increase binary size marginally (~500KB) but do not violate any constitution principle.

## Project Structure

### Documentation (this feature)

```text
specs/009-openapi-grpc-alerts/
├── plan.md                        # This file
├── spec.md                        # Feature specification
├── research.md                    # Phase 0 research & decisions
├── data-model.md                  # Phase 1 data model
├── quickstart.md                  # Phase 1 quickstart guide
├── contracts/
│   └── openapi-new-endpoints.yaml # Phase 1 OpenAPI contract (new endpoints only)
└── checklists/
    └── requirements.md            # Spec quality checklist
```

### Source Code (repository root)

```text
services/api-gateway/
├── openapi.yaml                              # NEW: Hand-written OpenAPI 3.1 spec (full)
├── internal/
│   ├── docs/
│   │   └── swagger-ui/                       # NEW: Embedded Swagger UI static assets
│   │       ├── index.html                    # Patched to point at /api/openapi.json
│   │       ├── swagger-ui.css
│   │       └── swagger-ui-bundle.js
│   ├── grpc/
│   │   ├── circuit_breaker.go                # NEW: Atomic circuit breaker (closed/open/half-open)
│   │   ├── ml_client.go                      # UPDATED: Add CB + retry ServiceConfig + 5s timeout
│   │   └── chat_client.go                    # UPDATED: Add retry ServiceConfig + 5s timeout
│   ├── handler/
│   │   ├── docs.go                           # NEW: Swagger UI handler + spec serving
│   │   ├── ml.go                             # NEW: GET /api/v1/model/estimate
│   │   └── alert_rules.go                    # NEW: CRUD + tier enforcement + validation
│   └── repository/
│       └── alert_rules.go                    # NEW: alert_rules + alert_history DB queries

frontend/
└── src/types/api.ts                          # GENERATED: openapi-typescript output
```

**Structure Decision**: All changes are additive within the existing `services/api-gateway/internal/` structure. New packages: `internal/docs/` (embedded assets), new file `internal/repository/alert_rules.go`. No restructuring of existing packages.

## Phase 0: Research

*Completed. See [research.md](research.md) for full decision log.*

Key decisions resolved:
- **OpenAPI serving**: Hand-written YAML + embedded Swagger UI static files (no swaggo/swag, no CDN)
- **gRPC retry**: `grpc.WithDefaultServiceConfig` with JSON service config (4 attempts = 1 + 3 retries on UNAVAILABLE)
- **Circuit breaker**: Custom `sync/atomic` implementation — no third-party library
- **Alert tier limits**: Static Go map; tier sourced from `users.subscription_tier`
- **Filter validation**: Compile-time allowlist per property category; 422 on violation
- **TypeScript types**: `openapi-typescript` v7+ at build time in `frontend/`

## Phase 1: Design & Contracts

*Completed. Artifacts:*

- **[data-model.md](data-model.md)**: `alert_rules` + `alert_history` DDL; circuit breaker in-memory state; JSONB filter schema; response shapes
- **[contracts/openapi-new-endpoints.yaml](contracts/openapi-new-endpoints.yaml)**: All 8 new endpoints with full request/response schemas, error formats, examples
- **[quickstart.md](quickstart.md)**: Local dev setup, env vars, curl examples, file layout

## Implementation Phases

### Phase A: Swagger UI & OpenAPI Spec

**Goal**: `/api/docs` and `/api/openapi.json` working end-to-end.

Tasks:
1. Download Swagger UI distribution (swagger-ui-bundle.js, swagger-ui.css) and place in `internal/docs/swagger-ui/`. Write a patched `index.html` pointing `url` at `/api/openapi.json` and setting `persistAuthorization: true`.
2. Add `//go:embed internal/docs/swagger-ui/*` directive in `handler/docs.go`.
3. Implement `handler/docs.go`:
   - `ServeOpenAPISpec(w, r)`: embed the YAML, convert to JSON at init, serve from memory.
   - `ServeSwaggerUI(w, r)`: serve static files from embedded FS.
4. Write `openapi.yaml` covering all existing endpoints plus new ones from `contracts/openapi-new-endpoints.yaml`.
5. Register routes in router: `r.Get("/api/openapi.json", h.ServeOpenAPISpec)`, `r.Get("/api/docs", ...)`, `r.Get("/api/docs/*", ...)`.
6. Test: `go test ./internal/handler/` with `httptest`.

### Phase B: gRPC Client Hardening

**Goal**: ml-scorer and ai-chat clients have retry, timeout, and circuit breaker.

Tasks:
1. Write `internal/grpc/circuit_breaker.go` with struct `CircuitBreaker` using `sync/atomic`. Implement `Allow() bool`, `RecordSuccess()`, `RecordFailure()`. States: 0=closed, 1=open, 2=half-open. Threshold=5, window=30s, cooldown=30s (configurable via struct fields).
2. Update `ml_client.go`:
   - Replace `grpc.Dial` with `grpc.NewClient`.
   - Add `grpc.WithDefaultServiceConfig(retryServiceConfigJSON)`.
   - Add context-scoped 5s deadline per call (from env var `GRPC_TIMEOUT_SECONDS`).
   - Embed a `CircuitBreaker` in `MLClient`.
   - Wrap `ScoreListing`: check `cb.Allow()` before calling; call `RecordSuccess`/`RecordFailure`; return 503 if CB is open.
3. Update `chat_client.go`: same retry policy + timeout; no circuit breaker.
4. Update `config/config.go` to read `GRPC_ML_SCORER_ADDR`, `GRPC_AI_CHAT_ADDR`, `GRPC_TIMEOUT_SECONDS`.
5. Unit test `circuit_breaker.go` with table-driven tests covering all state transitions.

### Phase C: ML Estimate Endpoint

**Goal**: `GET /api/v1/model/estimate?listing_id=<uuid>` returns valuation.

Tasks:
1. Write `handler/ml.go` with `Estimate(w http.ResponseWriter, r *http.Request)`:
   - Extract and validate `listing_id` as UUID from query string.
   - Call `mlClient.ScoreListing(ctx, req)` with 5s context deadline.
   - Map gRPC response to `MLEstimate` JSON.
   - Map errors: UNAVAILABLE → 503, NOT_FOUND → 404, circuit open → 503.
2. Register route: `r.Get("/api/v1/model/estimate", authMW(h.Estimate))`.
3. Integration test with a mock gRPC server using `google.golang.org/grpc/test/bufconn`.

### Phase D: Alert Rules Database Migration

**Goal**: `alert_rules` and `alert_history` tables exist in PostgreSQL.

Tasks:
1. Write Alembic migration with `alert_rules` and `alert_history` DDL from `data-model.md`.
2. Add indexes as specified.
3. Test migration: `uv run alembic upgrade head` and `uv run alembic downgrade -1`.

### Phase E: Alert Rules Repository

**Goal**: All DB operations for alert rules and history.

Tasks:
1. Write `internal/repository/alert_rules.go` with functions:
   - `CountActiveRules(ctx, userID) (int, error)`
   - `CreateRule(ctx, rule AlertRule) (*AlertRule, error)`
   - `ListRules(ctx, userID, page, pageSize, isActive *bool) ([]AlertRule, int, error)`
   - `GetRule(ctx, id, userID) (*AlertRule, error)`
   - `UpdateRule(ctx, id, userID, update UpdateRuleInput) (*AlertRule, error)`
   - `DeleteRule(ctx, id, userID) error` — soft delete
   - `ListHistory(ctx, userID, filter HistoryFilter, page, pageSize) ([]AlertHistoryEntry, int, error)`
   - `ValidateZoneIDs(ctx, zoneIDs []uuid.UUID) ([]uuid.UUID, error)` — returns invalid IDs
2. Table-driven integration tests using testcontainers-go with PostgreSQL 16.

### Phase F: Alert Rules Handler

**Goal**: All 5 new alert endpoint handlers with validation and tier enforcement.

Tasks:
1. Write `internal/handler/alert_rules.go` with handlers for all 5 endpoints.
2. Tier limit map: `var tierAlertRuleLimits = map[string]int{"free":0,"basic":3,"pro":-1,"global":-1,"api":-1}`
3. Filter validation: `validateAlertFilter(category, filter)` against compile-time allowlist.
4. Zone validation: calls `repo.ValidateZoneIDs` → 422 with detail on failure.
5. Tier check: `repo.CountActiveRules` → 403 (free) or 422 (limit reached) as appropriate.
6. Register routes under `r.Route("/api/v1/alerts", ...)` with auth middleware.
7. Unit tests for filter validation and tier enforcement. Integration tests for each endpoint.

### Phase G: TypeScript Type Generation

**Goal**: Frontend has accurate TypeScript types from the OpenAPI spec.

Tasks:
1. Add `openapi-typescript` to `frontend/package.json` devDependencies.
2. Add script: `"generate:types": "openapi-typescript ../services/api-gateway/openapi.yaml -o src/types/api.ts"`.
3. Run generation and commit `src/types/api.ts`.
4. Verify: `tsc --noEmit` with no errors.

## Dependencies Between Phases

```
Phase A (Swagger UI)        — independent
Phase B (gRPC hardening)   → Phase C (ML estimate)
Phase D (DB migration)     → Phase E (Repository) → Phase F (Alert handler)
Phase A + Phase F          → Phase G (TypeScript types, needs complete openapi.yaml)
```

Phases A, B, D can be developed in parallel.

## Test Strategy

| Layer | Tool | Coverage |
|-------|------|----------|
| Circuit breaker unit | Go `testing` | All state transitions |
| Filter validation unit | Go `testing` | All categories × allowed/disallowed fields |
| Tier enforcement unit | Go `testing` | free=reject, basic=3 limit, pro=unlimited |
| Repository integration | testcontainers-go + PostgreSQL 16 | CRUD + count + validation |
| Handler HTTP integration | `net/http/httptest` | All endpoints × success + error paths |
| gRPC integration | `bufconn` mock server | Success + UNAVAILABLE + timeout + CB open |
| E2E (Swagger UI) | Manual browser test | "Try it out" with JWT |

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Proto generated types for ml-scorer stale | Medium | Check `libs/proto/estategap/v1/`; run `buf generate` if needed |
| `alert_rules` conflicts with existing `alerts` table | Low | Different table name; verify in migration |
| Race on Basic tier limit (concurrent creates) | Low | Wrap CountActiveRules + Insert in a transaction with `FOR UPDATE` |
| Swagger UI asset versions becoming stale | Low | Pin version in quickstart; add version comment to index.html |
