# Quickstart: Scrape Orchestrator & Proxy Manager

**Branch**: `010-scrape-orchestrator-proxy` | **Date**: 2026-04-17

## Prerequisites

- Go 1.23 (`go version`)
- PostgreSQL 16 + Redis 7 running locally (or via Docker Compose)
- NATS JetStream running locally
- `buf` CLI for proto generation

## Proto Generation

```bash
# Run from repo root
buf generate

# Verify generated files
ls libs/pkg/proto/estategap/v1/
```

## Scrape Orchestrator

### Environment

```bash
# services/scrape-orchestrator/.env.example → .env
DATABASE_URL=postgres://estategap:secret@localhost:5432/estategap?sslmode=disable
REDIS_URL=redis://localhost:6379
NATS_URL=nats://localhost:4222
HTTP_PORT=8082
LOG_LEVEL=INFO

# Optional
PORTAL_RELOAD_INTERVAL=5m   # default: 5m
JOB_TTL=86400               # default: 86400s (24h)
```

### Run Locally

```bash
cd services/scrape-orchestrator
go mod tidy
go run ./cmd/main.go
```

### Trigger a Manual Job

```bash
curl -X POST http://localhost:8082/jobs/trigger \
  -H "Content-Type: application/json" \
  -d '{
    "portal": "immobiliare",
    "country": "IT",
    "mode": "full",
    "zone_filter": [],
    "search_url": "https://www.immobiliare.it/vendita-case/roma/"
  }'
```

### Check Job Status

```bash
curl http://localhost:8082/jobs/{job_id}/status
```

### Check Stats

```bash
curl http://localhost:8082/jobs/stats
```

### Reload Config (no restart)

```bash
kill -HUP $(pgrep -f "scrape-orchestrator")
```

---

## Proxy Manager

### Environment

```bash
# services/proxy-manager/.env.example → .env
REDIS_URL=redis://localhost:6379
GRPC_PORT=50052
LOG_LEVEL=INFO

# Proxy pool config (one set per country)
PROXY_COUNTRIES=IT,ES
PROXY_IT_PROVIDER=brightdata
PROXY_IT_ENDPOINT=zproxy.lum-superproxy.io:22225
PROXY_IT_USERNAME=your_username
PROXY_IT_PASSWORD=your_password
PROXY_ES_PROVIDER=smartproxy
PROXY_ES_ENDPOINT=gate.smartproxy.com:7000
PROXY_ES_USERNAME=your_username
PROXY_ES_PASSWORD=your_password

# Optional
BLACKLIST_TTL=1800      # default: 1800s (30min)
STICKY_TTL=600          # default: 600s (10min)
HEALTH_THRESHOLD=0.5    # default: 0.5
METRICS_PORT=9090       # default: 9090
```

### Run Locally

```bash
cd services/proxy-manager
go mod tidy
go run ./cmd/main.go
```

### Test GetProxy via grpcurl

```bash
grpcurl -plaintext -d '{
  "country_code": "IT",
  "portal_id": "immobiliare",
  "session_id": ""
}' localhost:50052 estategap.v1.ProxyService/GetProxy
```

### Report a Failure

```bash
grpcurl -plaintext -d '{
  "proxy_id": "proxy-uuid-here",
  "success": false,
  "status_code": 429,
  "latency_ms": 1200
}' localhost:50052 estategap.v1.ProxyService/ReportResult
```

### View Metrics

```bash
curl http://localhost:9090/metrics | grep proxy_
```

---

## Running Tests

```bash
# Scrape Orchestrator
cd services/scrape-orchestrator
go test ./... -race -count=1

# Proxy Manager
cd services/proxy-manager
go test ./... -race -count=1
```

Integration tests use `testcontainers-go` to spin up Redis and NATS.

## Adding a New Proxy Provider

1. Create `services/proxy-manager/internal/provider/{name}.go`
2. Implement the `ProxyProvider` interface:
   ```go
   type ProxyProvider interface {
       BuildProxyURL(username, password, endpoint, sessionID string) string
       Name() string
   }
   ```
3. Register in `internal/provider/registry.go`
4. Add environment variable documentation to `.env.example`
