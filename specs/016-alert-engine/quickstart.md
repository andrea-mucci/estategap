# Quickstart: Alert Engine (016)

**Date**: 2026-04-17
**Branch**: `016-alert-engine`

## Prerequisites

- Go 1.23+
- Docker + `docker compose` (for local PostgreSQL, Redis, NATS)
- Access to the running estategap infrastructure or local dev stack

---

## Service Location

```
services/alert-engine/
├── cmd/
│   └── main.go
├── internal/
│   ├── config/
│   ├── cache/
│   ├── matcher/
│   ├── dedup/
│   ├── router/
│   ├── digest/
│   ├── repository/
│   └── publisher/
├── go.mod
├── go.sum
└── Dockerfile
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | required | PostgreSQL DSN (primary, for rule cache load + history writes) |
| `DATABASE_REPLICA_URL` | `DATABASE_URL` | Read replica DSN |
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `NATS_URL` | `nats://localhost:4222` | NATS server URL |
| `RULE_CACHE_REFRESH_INTERVAL` | `60s` | How often to reload rules from DB |
| `WORKER_POOL_SIZE` | `0` (= GOMAXPROCS) | Goroutine pool size for rule evaluation |
| `BATCH_SIZE` | `100` | NATS fetch batch size |
| `HEALTH_PORT` | `8080` | HTTP health/metrics port |
| `LOG_LEVEL` | `info` | debug / info / warn / error |

---

## Running Locally

```bash
# From repo root — start dependencies
docker compose up -d postgres redis nats

# Run migrations (adds frequency column)
cd services/pipeline
uv run alembic upgrade head

# Build and run alert-engine
cd services/alert-engine
go run ./cmd/main.go
```

The service will:
1. Connect to PostgreSQL, Redis, NATS
2. Load all active alert rules into memory
3. Pre-load zone geometries
4. Start NATS consumers for `scored.listings` and `listings.price-change.>`
5. Start digest scheduler goroutines (hourly + daily tickers)
6. Expose `/health` and `/metrics` on port 8080

---

## Running Tests

```bash
cd services/alert-engine

# Unit tests (no external dependencies)
go test ./internal/matcher/... ./internal/dedup/... -v

# Integration tests (requires testcontainers)
go test ./internal/... -tags integration -v
```

Integration tests use `testcontainers-go` to spin up PostgreSQL + PostGIS and Redis.

---

## Key Health Checks

```bash
# Liveness
curl http://localhost:8080/health/live

# Readiness (checks DB + Redis + NATS connections)
curl http://localhost:8080/health/ready

# Prometheus metrics
curl http://localhost:8080/metrics
```

Key metrics exposed:
- `alert_engine_rules_cached_total` — gauge: active rules in cache
- `alert_engine_events_processed_total` — counter by event type
- `alert_engine_matches_total` — counter: rules matched
- `alert_engine_dedup_hits_total` — counter: deduplicated (skipped)
- `alert_engine_notifications_published_total` — counter by channel + frequency
- `alert_engine_digest_buffer_depth` — gauge per user+rule
- `alert_engine_rule_eval_duration_seconds` — histogram

---

## Verifying End-to-End

1. Insert an active alert rule in PostgreSQL with `frequency = 'instant'`
2. Publish a scored listing to `scored.listings` NATS subject matching the rule
3. Subscribe to `alerts.notifications.{country}` and verify a notification event arrives within 500ms
4. Publish the same scored listing again — verify no second notification arrives (dedup)
5. Publish a price change event for the same listing — verify a new notification arrives

---

## Helm Deployment

The alert engine is deployed as a `Deployment` with replicas and a `PodDisruptionBudget`.

```bash
helm upgrade --install estategap helm/estategap \
  -f helm/estategap/values.yaml \
  -f helm/estategap/values-staging.yaml \
  --namespace estategap-system
```

KEDA `ScaledObject` can be added later to autoscale based on NATS consumer lag.
