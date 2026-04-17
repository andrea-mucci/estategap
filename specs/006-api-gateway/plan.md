# Implementation Plan: API Gateway

**Branch**: `006-api-gateway` | **Date**: 2026-04-17 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/006-api-gateway/spec.md`

## Summary

Build the Go API Gateway — the sole HTTP entry point for all EstateGap external traffic. The service implements JWT + Google OAuth2 authentication, per-tier Redis-backed rate limiting, structured logging, Prometheus metrics, and a chi-based router with graceful shutdown. All cross-cutting concerns are handled here so downstream services remain focused on domain logic.

## Technical Context

**Language/Version**: Go 1.23  
**Primary Dependencies**: chi v5 (router), pgx/v5/pgxpool (PostgreSQL), redis/go-redis v9 (Redis), golang-jwt/jwt v5 (JWT), golang.org/x/oauth2 (Google OAuth2), golang.org/x/crypto/bcrypt (password hashing), prometheus/client_golang (metrics), spf13/viper (config), nats.go (NATS health check)  
**Storage**: PostgreSQL 16 (pgx, read/write split) + Redis 7 (sessions, rate limits, blacklist, OAuth state)  
**Testing**: Go stdlib `testing` + `testcontainers-go` for integration tests; table-driven unit tests  
**Target Platform**: Linux container (Kubernetes, amd64)  
**Project Type**: Web service (HTTP API gateway)  
**Performance Goals**: p95 auth latency < 300ms; health probe < 500ms; supports 500 concurrent connections  
**Constraints**: Container image < 20 MB (multi-stage build, scratch base); graceful shutdown drains in-flight requests  
**Scale/Scope**: Initial target 10k registered users; rate limiting enforced per user per minute

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Polyglot Service Architecture — API Gateway MUST be Go | ✅ PASS | Go 1.23 + chi; lives in `services/api-gateway/` |
| I. No cross-service internal imports | ✅ PASS | Uses `libs/pkg/models` (shared lib), not another service's internals |
| II. Event-Driven Communication — no direct HTTP to other services | ✅ PASS | Internal calls via gRPC clients (`internal/grpc/`); NATS checked in readyz only |
| II. Inter-service contracts in proto/ | ✅ PASS | gRPC clients consume generated proto stubs from `libs/pkg/proto/` |
| III. Country-First Data Sovereignty — PostgreSQL + PostGIS | ✅ PASS | pgx pool connects to existing partitioned schema |
| V. Code Quality — stdlib net/http + chi, pgx (no ORM), slog, golangci-lint | ✅ PASS | All tooling aligned; structured logging via slog |
| VI. Security — JWT short-lived tokens + refresh, Google OAuth2, rate limiting per tier, no secrets in code | ✅ PASS | bcrypt 12 rounds, Redis-backed refresh/blacklist, Sealed Secrets via K8s |
| VII. Kubernetes-Native — Dockerfile, Helm chart | ✅ PASS | Multi-stage Dockerfile targets scratch; Helm values in `helm/estategap/` |

**Gate result**: ✅ ALL PASS — no violations. Proceed to Phase 1.

## Project Structure

### Documentation (this feature)

```text
specs/006-api-gateway/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── openapi.yaml
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
services/api-gateway/
├── cmd/
│   └── main.go                   # Wire deps, start HTTP server, handle OS signals
├── internal/
│   ├── config/
│   │   └── config.go             # Viper config: DB_PRIMARY_URL, DB_REPLICA_URL,
│   │                             #   REDIS_URL, JWT_SECRET, GOOGLE_CLIENT_ID,
│   │                             #   GOOGLE_CLIENT_SECRET, GOOGLE_REDIRECT_URL,
│   │                             #   ALLOWED_ORIGINS, PORT, NATS_URL
│   ├── handler/
│   │   ├── auth.go               # POST /v1/auth/register|login|refresh|logout
│   │   ├── google_oauth.go       # GET /v1/auth/google  GET /v1/auth/google/callback
│   │   ├── health.go             # GET /healthz  GET /readyz
│   │   ├── listings.go           # GET /v1/listings  GET /v1/listings/{id}
│   │   ├── zones.go              # GET /v1/zones  GET /v1/zones/{id}  GET /v1/zones/{id}/analytics
│   │   ├── alerts.go             # CRUD /v1/alerts  GET /v1/alerts/{id}/history
│   │   └── subscriptions.go      # POST /v1/subscriptions/checkout  POST /v1/webhooks/stripe
│   ├── middleware/
│   │   ├── auth.go               # Bearer JWT extraction + validation; sets ctx user_id/email/tier
│   │   ├── ratelimit.go          # Redis INCR sliding window; returns 429 + Retry-After
│   │   ├── cors.go               # Configurable CORS from allowed origins list
│   │   ├── logging.go            # slog structured request log; injects request_id into ctx
│   │   └── metrics.go            # Prometheus http_requests_total, duration, active_connections
│   ├── repository/
│   │   ├── users.go              # CreateUser, GetUserByEmail, GetUserByOAuth, UpdateUser
│   │   ├── listings.go           # SearchListings, GetListingByID (read replica)
│   │   ├── zones.go              # ListZones, GetZone, GetZoneAnalytics (read replica)
│   │   └── alerts.go             # CRUD AlertRules, GetAlertHistory
│   └── grpc/
│       ├── ml_client.go          # gRPC client → ml-scorer service
│       └── chat_client.go        # gRPC client → ai-search service
├── Dockerfile                    # Multi-stage: golang:1.23-alpine → scratch; image < 20 MB
└── go.mod                        # module estategap/services/api-gateway; go 1.23
```

**Structure Decision**: Single Go service under `services/api-gateway/`. Internal packages are unexported to the rest of the monorepo. Shared types from `libs/pkg/models` and generated proto stubs from `libs/pkg/proto` are the only cross-module dependencies.

## Complexity Tracking

> No constitution violations — this section is not required.
