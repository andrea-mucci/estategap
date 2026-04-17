# Research: OpenAPI Documentation, gRPC Clients & Alert Rules

**Branch**: `009-openapi-grpc-alerts` | **Date**: 2026-04-17
**Phase**: 0 — Research & Decision Log

---

## 1. OpenAPI Serving Strategy

### Decision
Hand-write the OpenAPI 3.1 specification as `services/api-gateway/openapi.yaml`. Embed the Swagger UI static assets into the Go binary using `embed.FS`. Serve the spec at `GET /api/openapi.json` and the UI at `GET /api/docs`.

### Rationale
- `swaggo/swag` requires annotation comments scattered across all handler files and a code-generation step, creating tight coupling between comments and generated YAML. Maintaining generated YAML in version control causes noise diffs. Hand-written YAML is the single source of truth, stays in one file, and avoids generation drift.
- Embedding Swagger UI static files (downloaded once at project setup, committed to `services/api-gateway/internal/docs/swagger-ui/`) eliminates any CDN dependency at runtime—critical for air-gapped Kubernetes environments.
- Serving at `/api/openapi.json` (not `/api/openapi.yaml`) matches conventional tooling expectations (openapi-typescript, Redoc, Postman import).
- The spec file is separate from the binary's embedded static assets: `openapi.yaml` is embedded as a raw file and re-served as JSON after YAML→JSON conversion at startup.

### Alternatives Considered
| Option | Rejected Because |
|--------|-----------------|
| `swaggo/swag` annotations | Scatters spec across handler files; generated YAML in VCS creates noisy diffs; requires regeneration on every handler change |
| External CDN for Swagger UI | Runtime CDN dependency; fails in air-gapped K8s clusters |
| Redoc (instead of Swagger UI) | Swagger UI is industry standard for "Try it out" interactivity; Redoc is read-only |
| OpenAPI 3.0 (not 3.1) | 3.1 aligns JSON Schema fully; better tooling support in openapi-typescript v7+ |

### Implementation Notes
- Convert `openapi.yaml` → JSON at startup using `gopkg.in/yaml.v3` + `encoding/json`; cache the result in memory.
- Swagger UI `initializer.js` is patched to point `url` at `/api/openapi.json` and set `persistAuthorization: true`.
- Route registration: `r.Get("/api/docs", docsRedirect)`, `r.Get("/api/docs/*", swaggerUIHandler)`, `r.Get("/api/openapi.json", specHandler)`.

---

## 2. gRPC Client Architecture

### Decision
Enhance the existing `internal/grpc/` package. Add:
- `circuit_breaker.go`: custom atomic-counter circuit breaker
- Update `ml_client.go` and `chat_client.go` to use `grpc.WithDefaultServiceConfig` for retry, context-scoped 5s timeout, and circuit breaker wrapping

### Rationale
- The existing `grpc.Dial` calls are bare stubs with no retry, no timeout, no circuit breaker. Production traffic to ml-scorer (a Python service that may cold-start slowly) requires all three.
- `grpc.WithDefaultServiceConfig` with a JSON service config string is the canonical Go gRPC way to specify client-side retry policy—no additional library needed.
- A custom atomic circuit breaker (three `sync/atomic` integers: failure count, last failure Unix timestamp, state) avoids importing a third-party resilience library (sony/gobreaker, etc.). Keeps the dependency tree minimal, aligns with the constitution's "no ORM" / minimal-abstraction philosophy.
- Connection pooling: gRPC multiplexes requests over a single HTTP/2 connection by default. One `*grpc.ClientConn` per upstream is sufficient; no explicit pool needed.

### Retry Service Config (JSON)
```json
{
  "methodConfig": [{
    "name": [{"service": ""}],
    "retryPolicy": {
      "maxAttempts": 4,
      "initialBackoff": "0.1s",
      "maxBackoff": "1s",
      "backoffMultiplier": 2.0,
      "retryableStatusCodes": ["UNAVAILABLE"]
    },
    "timeout": "5s"
  }]
}
```
`maxAttempts: 4` = 1 initial + 3 retries, matching the spec requirement.

### Circuit Breaker State Machine

```
CLOSED ──(5 failures in 30s)──> OPEN
OPEN   ──(30s elapsed)────────> HALF-OPEN
HALF-OPEN ──(probe succeeds)──> CLOSED
HALF-OPEN ──(probe fails)─────> OPEN (reset cooldown)
```

Implementation: Three atomics — `state int32` (0=closed, 1=open, 2=half-open), `failures int32`, `lastFailureUnix int64`. On each call:
- If OPEN and cooldown not elapsed → return 503 immediately
- If OPEN and cooldown elapsed → CAS to HALF-OPEN, allow one call
- If HALF-OPEN → allow one call; on success CAS to CLOSED + reset failures; on failure CAS back to OPEN
- If CLOSED → on success reset failures; on failure increment + check threshold

The circuit breaker wraps the gRPC call at the `MLClient.ScoreListing` level, not at the connection level.

### K8s DNS Targets
- `ml-scorer`: `ml-scorer.estategap-intelligence.svc.cluster.local:50051`
- `ai-chat-service`: `ai-chat-service.estategap-intelligence.svc.cluster.local:50051`

Both configured via environment variables: `GRPC_ML_SCORER_ADDR`, `GRPC_AI_CHAT_ADDR`. Defaults to the K8s DNS names above.

### Alternatives Considered
| Option | Rejected Because |
|--------|-----------------|
| `sony/gobreaker` | Extra dependency; atomic implementation is ~80 lines and fully transparent |
| Connection-level circuit breaker | gRPC already has built-in channel health checking; call-level CB gives finer control per RPC method |
| `grpc-ecosystem/go-grpc-middleware` interceptors | Additional dependency; inline timeout/retry via service config is sufficient |

---

## 3. Alert Rules — Tier Enforcement

### Decision
Enforce tier limits with a `COUNT(*) WHERE user_id = ? AND is_active = true` query before insert. Tier limits sourced from a static Go map keyed on `tier` string: `{"free": 0, "basic": 3, "pro": -1, "global": -1, "api": -1}` (−1 = unlimited).

### Rationale
- A database count query is authoritative (avoids race conditions between concurrent creates by relying on transaction isolation + optional advisory lock for Basic tier).
- Static map is simpler than database config; tier names are stable (defined by Stripe plan IDs in `008-stripe-subscriptions`).
- The tier string is read from `users.subscription_tier` which is kept in sync by the Stripe webhook worker.

### Tier Limit Map
```go
var tierAlertRuleLimits = map[string]int{
    "free":   0,
    "basic":  3,
    "pro":    -1,  // unlimited
    "global": -1,
    "api":    -1,
}
```

---

## 4. Alert Rules — JSONB Filter Validation

### Decision
Define a Go map of allowed filter fields per property category as a compile-time constant. Validate the incoming JSON body's `filter` keys against this map before any database write. Return 422 with per-field error details on violation.

### Allowed Filter Fields (per category)
```
residential: price_eur, area_m2, bedrooms, bathrooms, floor, has_parking, has_elevator, property_type, listing_age_days
commercial:  price_eur, area_m2, floor, has_parking, property_type, listing_age_days
industrial:  price_eur, area_m2, property_type, listing_age_days
land:        price_eur, area_m2, listing_age_days
```

Each field supports operators: `eq`, `lt`, `lte`, `gt`, `gte`, `in`. Example filter:
```json
{
  "bedrooms": {"gte": 3},
  "price_eur": {"lte": 500000},
  "has_parking": {"eq": true}
}
```

### Zone ID Validation
Single query: `SELECT id FROM zones WHERE id = ANY($1) AND is_active = true`. If count of returned rows < count of provided IDs → 422 with list of invalid/inactive zone IDs.

---

## 5. OpenAPI TypeScript Type Generation

### Decision
Add `openapi-typescript` as a dev dependency in `frontend/`. Generate types at build time from `services/api-gateway/openapi.yaml` (or the served `/api/openapi.json`). Output to `frontend/src/types/api.ts`.

### Rationale
- `openapi-typescript` (v7+, maintained by Drizzle team) generates pure TypeScript types (no runtime classes) from OpenAPI 3.1 — fully compatible with the spec version chosen.
- Frontend uses the generated types with `fetch`/TanStack Query; no extra HTTP client wrapper is required.
- Generation command: `npx openapi-typescript services/api-gateway/openapi.yaml -o frontend/src/types/api.ts`

---

## 6. Database Migration Requirements

Two new tables required (Alembic migration in `services/pipeline/` or standalone migration service):

### `alert_rules`
```sql
CREATE TABLE alert_rules (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id       UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name          VARCHAR(255) NOT NULL,
    zone_ids      UUID[] NOT NULL,
    category      VARCHAR(50) NOT NULL,  -- residential|commercial|industrial|land
    filter        JSONB NOT NULL DEFAULT '{}',
    channels      JSONB NOT NULL DEFAULT '[]',  -- [{type: "email"}, {type: "push"}]
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_alert_rules_user_id ON alert_rules(user_id);
CREATE INDEX idx_alert_rules_user_active ON alert_rules(user_id) WHERE is_active = TRUE;
```

### `alert_history`
```sql
CREATE TABLE alert_history (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id         UUID NOT NULL REFERENCES alert_rules(id) ON DELETE CASCADE,
    listing_id      UUID NOT NULL,
    triggered_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    channel         VARCHAR(50) NOT NULL,
    delivery_status VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending|delivered|failed
    error_detail    TEXT,
    delivered_at    TIMESTAMPTZ
);
CREATE INDEX idx_alert_history_rule_id ON alert_history(rule_id);
CREATE INDEX idx_alert_history_user ON alert_history(rule_id);
```
