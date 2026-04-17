# Research: API Gateway

**Date**: 2026-04-17  
**Branch**: `006-api-gateway`

All technical decisions were provided explicitly in the planning input. This document records the rationale and alternatives considered for each choice.

---

## Decision 1: chi Router over gorilla/mux or stdlib only

**Decision**: `github.com/go-chi/chi/v5`

**Rationale**: chi is a lightweight, idiomatic Go router that composes cleanly with `net/http` middleware via `chi.Router`. It provides URL parameters, subrouters, and middleware chaining without the weight of a full framework. It is the router mandated in the EstateGap constitution (Principle V references stdlib + chi).

**Alternatives considered**:
- `gorilla/mux`: Heavier, archival status as of 2023; chi is the active community standard.
- `gin`: Full framework with custom context; diverges from stdlib `http.Handler` interface; constitution explicitly mandates stdlib + chi.
- Stdlib only: Insufficient URL parameter extraction for REST routes; significantly more boilerplate.

---

## Decision 2: pgx/v5/pgxpool with Read/Write Splitting

**Decision**: `github.com/jackc/pgx/v5/pgxpool` — two separate pools (primary, replica), selected at repository call site.

**Rationale**: pgx is the high-performance, low-allocation PostgreSQL driver mandated by the constitution (Principle V: "pgx for PostgreSQL, no ORM"). Two connection pools allow reads to be routed to replicas, reducing primary load. Selection logic lives in the repository layer; middleware and handlers are pool-agnostic.

**Alternatives considered**:
- `pgxpool` with single pool: Simpler but loses read-scale benefit; replica provision is already part of the infrastructure plan.
- ORM (GORM/ent): Explicitly prohibited by the constitution.
- Connection-level proxy (PgBouncer): Complements but does not replace application-level routing; out of scope for this feature.

---

## Decision 3: JWT — HS256, 15-minute Access Tokens + Redis-stored Refresh Tokens

**Decision**: `github.com/golang-jwt/jwt/v5` with HS256 signing. Access token TTL = 15 min. Refresh token = UUID stored in Redis with 7d TTL. Logout blacklists the access token in Redis for its remaining TTL.

**Rationale**:
- HS256 is appropriate for a single-service gateway where the signing and verification authority are the same service.
- 15-minute access tokens limit the blast radius of token theft.
- Storing refresh tokens in Redis (not as signed JWTs) enables immediate revocation on logout without a secondary lookup table in PostgreSQL.
- Blacklisting access tokens on logout prevents immediate reuse during the remaining TTL window.

**Alternatives considered**:
- RS256 asymmetric signing: Useful when multiple services verify tokens independently; in EstateGap, internal services receive the user ID via gRPC headers, not raw JWTs, so HS256 suffices.
- Opaque refresh tokens in PostgreSQL: More durable but higher latency per refresh; Redis TTL-based cleanup is simpler.
- No blacklist on logout: Leaves a 15-minute window where a stolen token remains valid after logout; unacceptable for a security-conscious platform.

---

## Decision 4: Google OAuth2 — State in Redis, 10-minute TTL

**Decision**: `golang.org/x/oauth2`. State nonce stored in Redis at `oauth:state:{nonce}` with 10-minute TTL.

**Rationale**: The OAuth2 state parameter prevents CSRF attacks by binding the redirect to the initiating request. Redis TTL naturally expires stale states without a cron job. 10 minutes is generous enough for a human to complete the Google consent screen.

**Alternatives considered**:
- State in signed cookie: Viable but requires cookie infrastructure; Redis approach is consistent with the rest of the session storage strategy.
- State in PostgreSQL: Higher latency, requires periodic cleanup; Redis TTL is cleaner.

---

## Decision 5: Rate Limiting — Redis INCR Sliding Window per User

**Decision**: Redis `INCR` + `EXPIRE` per key `ratelimit:{user_id}`. Key TTL = 60s. If count exceeds tier limit → 429 + `Retry-After`.

**Rationale**: The INCR + EXPIRE pattern is atomic enough for rate limiting without requiring Lua scripts or Redis modules. The TTL creates a fixed 60-second window. For a first version this is a fixed window (not true sliding window), which is simpler and sufficient. True sliding window can be added later with a sorted set per user if needed.

**Limits by tier**:
| Tier   | Requests/min |
|--------|-------------|
| free   | 30          |
| basic  | 120         |
| pro    | 300         |
| global | 600         |
| api    | 1200        |

**Alternatives considered**:
- Token bucket (Redis + Lua): More burst-friendly; deferred to a future iteration once usage patterns are understood.
- Redis rate-limit libraries (redis-rate, throttled): Additional dependency for minimal gain at this scale; raw INCR is sufficient.
- In-memory rate limiting: Does not survive pod restarts and is inaccurate under horizontal scaling.

---

## Decision 6: bcrypt, 12 rounds

**Decision**: `golang.org/x/crypto/bcrypt` with cost factor 12.

**Rationale**: bcrypt cost 12 provides ~250ms hashing time on modern hardware — slow enough to resist brute-force attacks but fast enough to not degrade registration/login UX. This is well within the 300ms p95 target for auth flows.

**Alternatives considered**:
- argon2id: More modern and memory-hard; however, bcrypt is battle-tested and widely supported. Migration to argon2id can be done transparently on next login (rehash on verify).
- bcrypt cost 10 (default): Faster but less resistant; cost 12 is the current community recommendation for new systems.

---

## Decision 7: Prometheus metrics with client_golang

**Decision**: `github.com/prometheus/client_golang` with `promhttp.Handler()` at `/metrics`.

**Rationale**: kube-prometheus-stack is already deployed in the EstateGap cluster (Principle VII). Using the official client ensures out-of-the-box compatibility with the existing PodMonitor/ServiceMonitor CRDs.

**Metrics registered**:
- `http_requests_total` — counter, labels: `method`, `path`, `status`
- `http_request_duration_seconds` — histogram, labels: `method`, `path`
- `active_connections` — gauge (tracked via middleware)

---

## Decision 8: Multi-stage Dockerfile → scratch base image

**Decision**: Two-stage build: `golang:1.23-alpine` for compilation, `scratch` (or `gcr.io/distroless/static-debian12`) for the final image.

**Rationale**: The acceptance criteria require image < 20 MB. A scratch-based image contains only the statically compiled binary and CA certificates, achieving ~10-14 MB. The constitution mandates containerized services (Principle VII).

**Alternatives considered**:
- Alpine final image: ~5 MB base + binary ≈ 15-18 MB; adds shell attack surface.
- distroless/static: Slightly larger than scratch but includes timezone data and CA certs; preferred if timezone handling is needed.
- Ubuntu/Debian: 70+ MB; too large.

---

## Decision 9: Viper for Configuration

**Decision**: `github.com/spf13/viper` reading from environment variables.

**Rationale**: Viper is already used in `libs/pkg/config/config.go` in the shared lib. Consistent tooling across services. All secrets injected as environment variables via Kubernetes Sealed Secrets (Principle VI).

**Environment variables**:
| Variable | Purpose |
|----------|---------|
| `DB_PRIMARY_URL` | PostgreSQL primary DSN |
| `DB_REPLICA_URL` | PostgreSQL replica DSN |
| `REDIS_URL` | Redis connection string |
| `JWT_SECRET` | HS256 signing key (min 32 bytes) |
| `GOOGLE_CLIENT_ID` | Google OAuth2 client ID |
| `GOOGLE_CLIENT_SECRET` | Google OAuth2 client secret |
| `GOOGLE_REDIRECT_URL` | OAuth2 callback URL |
| `ALLOWED_ORIGINS` | Comma-separated CORS origins |
| `PORT` | HTTP listen port (default: 8080) |
| `NATS_URL` | NATS server URL for readyz check |
