# Tasks: API Gateway

**Input**: Design documents from `specs/006-api-gateway/`  
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/openapi.yaml ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.  
**Tests**: Not explicitly requested — no test tasks included. Add TDD tasks if desired before running `/speckit-implement`.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US5)

---

## Phase 1: Setup

**Purpose**: Go module, project skeleton, and build tooling.

- [X] T001 Create directory tree `services/api-gateway/cmd/`, `internal/config/`, `internal/handler/`, `internal/middleware/`, `internal/repository/`, `internal/grpc/`
- [X] T002 Create `services/api-gateway/go.mod` with module `estategap/services/api-gateway`, Go 1.23, and all dependencies: `github.com/go-chi/chi/v5`, `github.com/jackc/pgx/v5`, `github.com/redis/go-redis/v9`, `github.com/golang-jwt/jwt/v5`, `golang.org/x/oauth2`, `golang.org/x/crypto`, `github.com/prometheus/client_golang`, `github.com/spf13/viper`, `github.com/nats-io/nats.go`, `github.com/google/uuid`
- [X] T003 Add `services/api-gateway` to the root `go.work` file so the monorepo workspace resolves the new module
- [X] T004 [P] Create `services/api-gateway/.golangci.yml` enabling `errcheck`, `govet`, `staticcheck`, `exhaustive`, `goimports`
- [X] T005 [P] Create a two-stage `services/api-gateway/Dockerfile`: stage 1 `golang:1.23-alpine` builds a statically linked binary (`CGO_ENABLED=0 GOOS=linux`); stage 2 `gcr.io/distroless/static-debian12` copies the binary and sets `ENTRYPOINT`

**Checkpoint**: `go mod tidy` runs without errors; `docker build` produces an image.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core wiring that every user story depends on — config, DB pools, Redis client, chi router with graceful shutdown, and shared response helpers.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 Implement `services/api-gateway/internal/config/config.go`: use Viper to bind environment variables `DB_PRIMARY_URL`, `DB_REPLICA_URL`, `REDIS_URL`, `JWT_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URL`, `ALLOWED_ORIGINS` (comma-separated), `PORT` (default `8080`), `NATS_URL`; expose a `Config` struct and `Load() (*Config, error)` function
- [X] T007 [P] Implement `services/api-gateway/internal/db/db.go`: `NewPrimaryPool(ctx, dsn) (*pgxpool.Pool, error)` and `NewReplicaPool(ctx, dsn) (*pgxpool.Pool, error)` using `pgxpool.New`; configure max conns, health-check period
- [X] T008 [P] Implement `services/api-gateway/internal/redisclient/client.go`: `New(url string) (*redis.Client, error)` using `go-redis`; ping on startup to validate connectivity
- [X] T009 [P] Implement `services/api-gateway/internal/natsutil/client.go`: `Connect(url string) (*nats.Conn, error)` wrapping `nats.Connect` with reconnect options; used only for the readiness probe
- [X] T010 Implement `services/api-gateway/internal/respond/respond.go`: helpers `JSON(w, status, v)`, `Error(w, status, message, requestID)`, `NoContent(w)` writing `Content-Type: application/json`; define `ErrorResponse{Error string, RequestID string}`
- [X] T011 Implement `services/api-gateway/internal/ctxkey/keys.go`: unexported context key type and exported sentinel values `UserID`, `UserEmail`, `UserTier`, `RequestID`, `JTI` — avoids context key collisions across middleware
- [X] T012 Implement `services/api-gateway/cmd/main.go`: load config, build DB pools + Redis + NATS clients, instantiate repositories and handlers, build chi router, register all routes (stubs OK at this phase), start `http.Server` on `cfg.Port`, handle `SIGINT`/`SIGTERM` with `server.Shutdown(ctx)` and a 30-second drain timeout

**Checkpoint**: `go build ./...` succeeds; `go run ./cmd/main.go` starts and binds to `:8080`.

---

## Phase 3: User Story 4 — Health & Readiness Probes (Priority: P1)

**Goal**: `/healthz` and `/readyz` endpoints so Kubernetes liveness and readiness probes work correctly.

**Independent Test**: `curl localhost:8080/healthz` returns `200 {"status":"ok"}`; `curl localhost:8080/readyz` returns `200` when all deps up, `503` when Postgres is stopped.

- [X] T013 [US4] Implement `services/api-gateway/internal/handler/health.go`: `HealthHandler` struct holding `*pgxpool.Pool` (primary), `*redis.Client`, `*nats.Conn`; `Healthz(w, r)` writes `200 {"status":"ok"}` with no dependency checks; `Readyz(w, r)` pings all three dependencies concurrently with a 2-second timeout, builds `ReadinessStatus{Status, Checks map[string]string}`, returns `200` if all `"ok"` else `503`
- [X] T014 [US4] Register health routes in `cmd/main.go` (or router setup): `GET /healthz → handler.Healthz`, `GET /readyz → handler.Readyz` — both outside any auth middleware group

**Checkpoint**: `curl localhost:8080/healthz` → `200`; `curl localhost:8080/readyz` → `200` with all deps running; stopping Redis makes `/readyz` return `503` with `"redis":"error"`.

---

## Phase 4: User Story 1 — Secure Account Registration and Login (Priority: P1) 🎯 MVP

**Goal**: Complete JWT-based auth flow: register → login → access protected endpoint → refresh → logout.

**Independent Test**: Register a new email, login, call `GET /v1/auth/me` with the access token, call `/v1/auth/refresh`, call `/v1/auth/logout`, verify the old access token is rejected with 401.

### Repository

- [X] T015 [US1] Implement `services/api-gateway/internal/repository/users.go`: `UsersRepo` struct with `primary *pgxpool.Pool` and `replica *pgxpool.Pool`; methods: `CreateUser(ctx, email, passwordHash string) (*models.User, error)`, `GetUserByEmail(ctx, email string) (*models.User, error)` (replica), `UpdateLastLogin(ctx, userID uuid.UUID) error` (primary), `GetUserByID(ctx, userID uuid.UUID) (*models.User, error)` (replica); import `libs/pkg/models`

### Auth Service

- [X] T016 [US1] Implement `services/api-gateway/internal/service/auth.go`: `AuthService` struct; `HashPassword(plain string) (string, error)` using `bcrypt.GenerateFromPassword` cost 12; `CheckPassword(hash, plain string) bool`; `IssueAccessToken(user *models.User) (string, error)` — HS256 JWT with claims `sub`, `email`, `tier`, `jti` (random UUID), `iat`, `exp` (now+900s); `IssueRefreshToken(ctx, userID uuid.UUID) (string, error)` — random UUID stored in Redis at `refresh:{uuid}` with 7-day TTL; `RevokeRefreshToken(ctx, token string) error` — DEL the Redis key; `BlacklistAccessToken(ctx, jti string, ttl time.Duration) error` — SET `blacklist:{jti}` with TTL; `IsBlacklisted(ctx, jti string) (bool, error)` — EXISTS check
- [X] T017 [US1] Implement `services/api-gateway/internal/handler/auth.go`: `AuthHandler` struct with `*service.AuthService`, `*repository.UsersRepo`; handlers: `Register(w, r)` — decode body, validate email+password (min 8 chars), check duplicate email (409), hash password, create user, issue token pair, return 201; `Login(w, r)` — lookup by email, verify password, issue token pair, update last_login, return 200; `Refresh(w, r)` — GET Redis `refresh:{token}`, load user, issue new token pair, delete old refresh key (rotation), return 200 or 401; `Logout(w, r)` — extract access token JTI from context, delete refresh token from Redis, add JTI to blacklist with remaining TTL, return 204; `Me(w, r)` — read user ID from context, fetch user from replica, return profile

### Auth Middleware

- [X] T018 [US1] Implement `services/api-gateway/internal/middleware/auth.go`: `Authenticator(jwtSecret string, redisClient *redis.Client) func(http.Handler) http.Handler`; extract `Authorization: Bearer <token>`; parse and validate HS256 JWT; check `blacklist:{jti}` in Redis; store `sub`, `email`, `tier`, `jti` in context via ctxkey values; on any error return `401` via `respond.Error`; provide a second middleware `RequireAuth` that checks context for user ID and returns 401 if absent

### Route Registration

- [X] T019 [US1] Register auth routes in `cmd/main.go` router: `POST /v1/auth/register`, `POST /v1/auth/login`, `POST /v1/auth/refresh`, `POST /v1/auth/logout` (protected), `GET /v1/auth/me` (protected) — protected routes wrapped in `middleware.RequireAuth`

**Checkpoint**: Full auth flow works end-to-end. Invalid/expired JWT returns 401. Missing token returns 401.

---

## Phase 5: User Story 2 — Google OAuth2 Social Login (Priority: P2)

**Goal**: Users can sign in via Google; existing email accounts are linked automatically.

**Independent Test**: Hit `GET /v1/auth/google`, follow the redirect, complete the Google consent screen in a browser; confirm tokens are returned and a user row is created/linked in the DB.

### Repository extension

- [X] T020 [US2] Add methods to `services/api-gateway/internal/repository/users.go`: `GetUserByOAuth(ctx, provider, subject string) (*models.User, error)` (replica); `CreateOAuthUser(ctx, email, provider, subject, displayName, avatarURL string) (*models.User, error)` (primary); `LinkOAuth(ctx, userID uuid.UUID, provider, subject string) error` (primary)

### OAuth Service

- [X] T021 [US2] Implement `services/api-gateway/internal/service/oauth.go`: `OAuthService` with `redisClient`, `oauth2Config *oauth2.Config`, `usersRepo`; `BeginFlow(ctx) (redirectURL, state string, error)` — generate random state UUID, store `oauth:state:{state}` in Redis TTL 600s, return Google auth URL with state; `HandleCallback(ctx, code, state string) (*TokenPair, *models.User, error)` — GETDEL `oauth:state:{state}` (atomic, returns 400 if missing/expired), exchange code for Google token, fetch userinfo, find-or-create user (link by email if exists), issue token pair

### Handler

- [X] T022 [US2] Implement `services/api-gateway/internal/handler/google_oauth.go`: `GoogleOAuthHandler` with `*service.OAuthService`; `Redirect(w, r)` calls `BeginFlow` and issues `http.Redirect` 302 to Google; `Callback(w, r)` calls `HandleCallback` with query params `code` and `state`, returns 400 on error or 200 with token pair + user profile

### Route Registration

- [X] T023 [US2] Register OAuth routes: `GET /v1/auth/google → handler.Redirect`, `GET /v1/auth/google/callback → handler.Callback`

**Checkpoint**: Full Google OAuth2 flow completes. Invalid state returns 400. Existing email account is linked (no duplicate user created).

---

## Phase 6: User Story 3 — Rate Limiting by Subscription Tier (Priority: P3)

**Goal**: Per-user Redis INCR rate limiting; requests exceeding tier limits return 429 with `Retry-After`.

**Independent Test**: Authenticate as a free-tier user; send 31 requests in under 60 seconds; verify the 31st returns `429` with a `Retry-After` header; wait for the window to expire and confirm requests succeed again.

- [X] T024 [US3] Implement `services/api-gateway/internal/middleware/ratelimit.go`: `RateLimiter(redisClient *redis.Client) func(http.Handler) http.Handler`; extract user ID from context (skip if unauthenticated — rate limiting only applies to authenticated requests); extract tier from context; look up limit for tier: free=30, basic=120, pro=300, global=600, api=1200; `INCR ratelimit:{userID}`, if result == 1 set `EXPIRE 60`; if count > limit fetch `PTTL ratelimit:{userID}`, set `Retry-After: ceil(pttl/1000)` header, return 429 via `respond.Error`; pass through otherwise
- [X] T025 [US3] Wire `middleware.RateLimiter` into the authenticated route group in `cmd/main.go` (applies after `RequireAuth`, before domain handlers)

**Checkpoint**: Rate limit triggers at the correct threshold per tier. 429 includes `Retry-After`. Requests below limit succeed. Window resets after 60 seconds.

---

## Phase 7: User Story 5 — Structured Logging and Prometheus Metrics (Priority: P3)

**Goal**: Every request produces a structured JSON log line with correlation ID; Prometheus counters and histograms are exposed at `/metrics`.

**Independent Test**: Make any request and verify a JSON log line appears with all required fields; `curl localhost:8080/metrics` shows `http_requests_total` and `http_request_duration_seconds`.

- [X] T026 [US5] Implement `services/api-gateway/internal/middleware/logging.go`: `RequestLogger() func(http.Handler) http.Handler`; generate a UUID request ID, store in context via `ctxkey.RequestID`; wrap `w` in a `responseWriter` that captures status code; after handler returns, emit `slog.Info("request", "request_id", ..., "user_id", ..., "method", ..., "path", ..., "status", ..., "duration_ms", ...)` — user_id read from context (empty string if unauthenticated); set `X-Request-ID` response header
- [X] T027 [US5] Implement `services/api-gateway/internal/middleware/metrics.go`: register three collectors at init: `httpRequestsTotal *prometheus.CounterVec` (labels: `method`, `path`, `status`), `httpRequestDuration *prometheus.HistogramVec` (labels: `method`, `path`; buckets: 5ms, 25ms, 100ms, 250ms, 500ms, 1s, 2.5s), `activeConnections prometheus.Gauge`; `MetricsMiddleware() func(http.Handler) http.Handler` increments gauge on entry, decrements on exit, records counter and duration after handler
- [X] T028 [US5] Register `GET /metrics → promhttp.Handler()` in `cmd/main.go` (no auth, no rate limit)
- [X] T029 [US5] Add `middleware.RequestLogger()` and `middleware.MetricsMiddleware()` as global chi middleware (before auth group) in `cmd/main.go`

**Checkpoint**: Every request logged as JSON with all fields. `/metrics` shows counters incrementing. `active_connections` gauge changes under concurrent load.

---

## Phase 8: Domain API Handlers (Listings, Zones, Alerts, Subscriptions)

**Purpose**: Implement the remaining REST endpoints defined in `contracts/openapi.yaml`. These are not standalone user stories in the spec but are required for feature completeness per the plan.

### Repositories

- [X] T030 [P] Implement `services/api-gateway/internal/repository/listings.go`: `ListingsRepo` with replica pool; `SearchListings(ctx, filter ListingFilter) ([]models.Listing, string, error)` — keyset pagination on `(first_seen_at, id)`, filters: country (required), city, min/max price EUR, min/max area, property_category, deal_tier, status; `GetListingByID(ctx, id uuid.UUID) (*models.Listing, error)`
- [X] T031 [P] Implement `services/api-gateway/internal/repository/zones.go`: `ZonesRepo` with replica pool; `ListZones(ctx, country string, cursor string, limit int) ([]models.Zone, string, error)`; `GetZoneByID(ctx, id uuid.UUID) (*models.Zone, error)`; `GetZoneAnalytics(ctx, zoneID uuid.UUID, periodDays int) (*ZoneAnalytics, error)` — aggregate query on listings partitioned by zone
- [X] T032 [P] Implement `services/api-gateway/internal/repository/alerts.go`: `AlertsRepo` with primary + replica pools; `ListAlerts(ctx, userID uuid.UUID, cursor string, limit int) ([]models.AlertRule, string, error)` (replica); `CreateAlert(ctx, userID uuid.UUID, input AlertInput) (*models.AlertRule, error)` (primary) — enforces `alert_limit` from user row; `GetAlertByID(ctx, id, userID uuid.UUID) (*models.AlertRule, error)` (replica — scoped to owner); `UpdateAlert(ctx, id, userID uuid.UUID, input AlertInput) (*models.AlertRule, error)` (primary); `DeleteAlert(ctx, id, userID uuid.UUID) error` (primary); `ListAlertHistory(ctx, alertID, userID uuid.UUID, cursor string, limit int) ([]AlertEvent, string, error)` (replica)

### Handlers

- [X] T033 [P] Implement `services/api-gateway/internal/handler/listings.go`: `ListingsHandler` with `*repository.ListingsRepo`; `List(w, r)` — parse query params into `ListingFilter`, call repo, return paginated JSON; `Get(w, r)` — parse `{id}` UUID, call repo, return listing or 404
- [X] T034 [P] Implement `services/api-gateway/internal/handler/zones.go`: `ZonesHandler` with `*repository.ZonesRepo`; `List(w, r)`, `Get(w, r)`, `Analytics(w, r)` — parse query params and path params, call repo, return JSON; return 404 if zone not found
- [X] T035 Implement `services/api-gateway/internal/handler/alerts.go`: `AlertsHandler` with `*repository.AlertsRepo`; `List`, `Create`, `Get`, `Update`, `Delete`, `History` — all scoped to the authenticated user ID from context; `Create` returns 422 when alert limit is reached
- [X] T036 Implement `services/api-gateway/internal/handler/subscriptions.go`: `SubscriptionsHandler` stub — `Checkout(w, r)` returns `501 Not Implemented` with a JSON body `{"error":"stripe integration coming soon"}`; `StripeWebhook(w, r)` returns `501`; these are scaffolded per the plan but full Stripe integration is deferred

### gRPC Clients

- [X] T037 [P] Implement `services/api-gateway/internal/grpc/ml_client.go`: `MLClient` wrapping the generated `MLScoringServiceClient` from `libs/pkg/proto`; `NewMLClient(target string) (*MLClient, error)` sets up a `grpc.Dial` with TLS disabled (dev) / credentials (prod); expose `ScoreListing(ctx, req) (*ml.ScoreResponse, error)` — placeholder, not wired to any handler yet
- [X] T038 [P] Implement `services/api-gateway/internal/grpc/chat_client.go`: `ChatClient` wrapping `AIChatServiceClient`; `NewChatClient(target string) (*ChatClient, error)`; expose `StreamChat(ctx, req) (ai.AIChatService_StreamChatClient, error)` — placeholder, not wired yet

### Route Registration

- [X] T039 Register domain routes in `cmd/main.go` within the authenticated + rate-limited group: `GET /v1/listings`, `GET /v1/listings/{id}`, `GET /v1/zones`, `GET /v1/zones/{id}`, `GET /v1/zones/{id}/analytics`, `GET,POST /v1/alerts`, `GET,PUT,DELETE /v1/alerts/{id}`, `GET /v1/alerts/{id}/history`, `POST /v1/subscriptions/checkout`, `POST /v1/webhooks/stripe`

**Checkpoint**: All 16 endpoints from `contracts/openapi.yaml` return either data or a well-formed error JSON. No endpoint returns an unhandled panic or 500.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: CORS middleware, final Dockerfile hardening, Helm values, and validation of the quickstart.

- [X] T040 Implement `services/api-gateway/internal/middleware/cors.go`: `CORS(allowedOrigins []string) func(http.Handler) http.Handler`; handle `OPTIONS` preflight (return 204 with CORS headers); set `Access-Control-Allow-Origin` to matching origin from allowlist (or first if `*`); set `Access-Control-Allow-Methods: GET,POST,PUT,DELETE,OPTIONS`; set `Access-Control-Allow-Headers: Authorization,Content-Type,X-Request-ID`; set `Access-Control-Max-Age: 86400`
- [X] T041 Wire `middleware.CORS(cfg.AllowedOrigins)` as the outermost chi middleware in `cmd/main.go`
- [ ] T042 [P] Verify the Docker image size: `docker build -t api-gateway:check .` and confirm `docker image inspect` reports < 20 MB; if oversized, ensure `CGO_ENABLED=0`, `GOOS=linux`, and that only the binary (not source) is copied to the distroless stage
- [X] T043 [P] Add `api-gateway` Helm values to `helm/estategap/values.yaml`: image name/tag, `replicaCount: 2`, `resources.requests` (50m CPU, 64Mi RAM), `resources.limits` (200m CPU, 256Mi RAM), `livenessProbe` (`/healthz`), `readinessProbe` (`/readyz`), `env` block for all required env vars (values referencing K8s Sealed Secrets)
- [X] T044 [P] Add `api-gateway` Helm deployment template `helm/estategap/templates/api-gateway-deployment.yaml`: `Deployment` + `Service` (port 8080) + `ServiceMonitor` for Prometheus scraping at `/metrics`
- [ ] T045 Run `golangci-lint run ./...` from `services/api-gateway/` and fix all reported issues
- [ ] T046 Validate `quickstart.md` end-to-end: follow each step in `specs/006-api-gateway/quickstart.md`, confirm all `curl` smoke tests pass, confirm `docker build` produces a working image, confirm `helm lint` passes

**Checkpoint**: `docker build` < 20 MB. `helm lint` passes. `golangci-lint` clean. All quickstart smoke tests pass.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 completion — **blocks all phases 3–9**
- **Phase 3 (Health Probes)**: Depends on Phase 2
- **Phase 4 (Auth)**: Depends on Phase 2; can run in parallel with Phase 3
- **Phase 5 (OAuth2)**: Depends on Phase 4 (needs AuthService and UsersRepo)
- **Phase 6 (Rate Limiting)**: Depends on Phase 2 and Phase 4 (needs auth context values)
- **Phase 7 (Logging/Metrics)**: Depends on Phase 2; can run in parallel with Phases 3–6
- **Phase 8 (Domain Handlers)**: Depends on Phase 4 (auth middleware must be wired); repos/handlers are otherwise independent of each other
- **Phase 9 (Polish)**: Depends on all phases complete

### User Story Dependencies

| Story | Depends on | Can parallelize with |
|-------|-----------|---------------------|
| US4 Health Probes (Phase 3) | Phase 2 | US1 Phase 4 |
| US1 Auth (Phase 4) | Phase 2 | US4 Phase 3, US5 Phase 7 |
| US2 Google OAuth2 (Phase 5) | Phase 4 (AuthService, UsersRepo) | Phase 7, Phase 8 repos |
| US3 Rate Limiting (Phase 6) | Phase 4 (auth context) | Phase 5, Phase 7 |
| US5 Logging/Metrics (Phase 7) | Phase 2 | Phases 3, 4, 5, 6 |

### Within Each Phase

- Tasks marked `[P]` within the same phase operate on different files — launch them together
- Repository tasks (T030–T032) are fully parallel — different files, no shared state
- Handler tasks (T033–T036) depend only on their own repository — parallel within the group

### Parallel Opportunities

```bash
# Phase 1 — run together:
T004  # .golangci.yml
T005  # Dockerfile

# Phase 2 — run T007/T008/T009 together after T006:
T007  # DB pools
T008  # Redis client
T009  # NATS client

# After Phase 2 — run Phase 3 and Phase 4 together:
[Phase 3: T013, T014]  # Health probes
[Phase 4: T015, then T016/T017/T018 together, then T019]  # Auth

# Phase 8 — run all repo and handler tasks together:
T030, T031, T032  # All repos
T033, T034       # Read-only handlers (after repos)
T037, T038       # gRPC clients

# Phase 9 — run together:
T042  # Docker size check
T043  # Helm values
T044  # Helm templates
```

---

## Implementation Strategy

### MVP First (User Stories US4 + US1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks everything)
3. Complete Phase 3: Health Probes (US4)
4. Complete Phase 4: Auth (US1)
5. **STOP and VALIDATE**: `register → login → /v1/auth/me → refresh → logout` works end-to-end; `/healthz` and `/readyz` pass
6. Deploy to staging — this is a shippable increment

### Incremental Delivery

1. Phases 1–2 → Foundation ready
2. Phase 3 (US4) → K8s probes work — deploy safely
3. Phase 4 (US1) → Auth complete → **MVP deployed**
4. Phases 5–7 (US2, US3, US5) → OAuth, rate limiting, observability
5. Phase 8 → All domain endpoints live
6. Phase 9 → Production hardening

### Parallel Team Strategy

With 2+ developers after Phase 2 is complete:

- **Dev A**: Phase 4 (Auth) → Phase 5 (OAuth2)
- **Dev B**: Phase 3 (Health) + Phase 7 (Logging/Metrics) → Phase 8 repos

---

## Notes

- `[P]` tasks write to different files — safe to run concurrently via `/speckit-implement`
- `[Story]` label enables traceability back to `spec.md` acceptance criteria
- Each phase ends with a verifiable checkpoint — do not proceed until it passes
- The `respond` package (T010) must be implemented before any handler
- The `ctxkey` package (T011) must be implemented before any middleware
- Stripe integration is scaffolded (T036) but deferred — returns `501` intentionally
- gRPC clients (T037, T038) are wired but not connected to handlers yet — they become active in future service features
