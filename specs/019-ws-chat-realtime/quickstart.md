# Quickstart: ws-server

**Service**: `services/ws-server/`  
**Port**: 8081 (WebSocket + HTTP health)  
**Language**: Go 1.23

---

## Prerequisites

- Go 1.23+
- Docker (for integration tests)
- `ai-chat` service running on `localhost:50053` (or set `AI_CHAT_GRPC_ADDR`)
- NATS JetStream on `localhost:4222` (or set `NATS_ADDR`)
- Redis on `localhost:6379` (or set `REDIS_ADDR`) — used for JWT blacklist

---

## Environment Variables

Copy `.env.example` and set values:

```bash
cp services/ws-server/.env.example services/ws-server/.env
```

| Variable | Default | Description |
|---|---|---|
| `PORT` | `8081` | HTTP/WebSocket listen port |
| `JWT_SECRET` | — | HS256 secret (same as api-gateway) |
| `REDIS_ADDR` | `localhost:6379` | Redis for JWT blacklist check |
| `AI_CHAT_GRPC_ADDR` | `ai-chat:50053` | ai-chat gRPC endpoint |
| `NATS_ADDR` | `nats://localhost:4222` | NATS connection URL |
| `MAX_CONNECTIONS` | `10000` | Per-pod WebSocket connection limit |
| `PING_INTERVAL` | `30s` | Keepalive ping frequency |
| `PONG_TIMEOUT` | `10s` | Pong wait timeout before disconnect |
| `IDLE_TIMEOUT` | `30m` | Idle connection timeout |
| `SHUTDOWN_TIMEOUT` | `5s` | Graceful shutdown drain timeout |
| `NATS_WORKERS` | `4` | NATS notification consumer goroutines |
| `LOG_LEVEL` | `info` | Logging level (debug, info, warn, error) |

---

## Run Locally

```bash
cd services/ws-server
go run ./cmd/...
```

Or with `go.work` from repo root:

```bash
go run ./services/ws-server/cmd/...
```

---

## Test a Connection

Using `websocat` (install: `cargo install websocat` or `brew install websocat`):

```bash
# Get a JWT from the api-gateway first
TOKEN=$(curl -s -X POST http://localhost:8080/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"test@example.com","password":"password"}' | jq -r '.access_token')

# Connect
websocat "ws://localhost:8081/ws/chat?token=$TOKEN"

# Send a chat message
{"type":"chat_message","session_id":"","payload":{"user_message":"Hello, find me flats in Madrid","country_code":"ES"}}
```

---

## Run Tests

```bash
cd services/ws-server

# Unit tests
go test ./internal/...

# Integration tests (requires Docker for NATS testcontainer)
go test ./tests/integration/... -tags=integration
```

From repo root:

```bash
go test ./services/ws-server/...
```

---

## Lint

```bash
cd services/ws-server
golangci-lint run ./...
```

---

## Health Endpoints

| Path | Method | Description |
|---|---|---|
| `/healthz` | GET | Liveness probe — returns `200 OK` if process is alive |
| `/readyz` | GET | Readiness probe — returns `200 OK` if NATS + Redis + gRPC connections are healthy |
| `/metrics` | GET | Prometheus metrics exposition |

---

## Key Dependencies to Add to `go.mod`

```bash
cd services/ws-server

go get github.com/gorilla/websocket@v1.5.3
go get github.com/golang-jwt/jwt/v5@v5.2.1
go get github.com/go-chi/chi/v5@v5.2.1
go get github.com/nats-io/nats.go@v1.37.0
go get github.com/redis/go-redis/v9@v9.7.0
go get google.golang.org/grpc@v1.64.0
go get github.com/prometheus/client_golang@v1.19.0
go get github.com/spf13/viper@v1.19.0
go get github.com/estategap/libs/pkg
```

---

## Directory Layout

```
services/ws-server/
├── Dockerfile
├── go.mod
├── .env.example
├── .golangci.yml
├── cmd/
│   ├── main.go          # startup: config → clients → hub → NATS consumer → HTTP server
│   └── routes.go        # chi router: GET /ws/chat, GET /healthz, GET /readyz, GET /metrics
├── internal/
│   ├── config/
│   │   └── config.go    # viper env loading → Config struct
│   ├── hub/
│   │   ├── hub.go       # Hub: Register/Unregister/Send/Shutdown
│   │   └── connection.go # Connection: readPump / writePump goroutines
│   ├── handler/
│   │   ├── ws.go        # HTTP handler: JWT check → upgrade → register → pump goroutines
│   │   └── health.go    # /healthz + /readyz
│   ├── middleware/
│   │   └── auth.go      # JWT parse helper (called by ws.go before upgrade)
│   ├── protocol/
│   │   ├── messages.go  # Envelope + all payload structs
│   │   └── dispatch.go  # Route inbound message type to handler
│   ├── grpc/
│   │   └── chat_client.go  # OpenChatStream(ctx, userID, tier) → stream management
│   ├── nats/
│   │   └── consumer.go  # JetStream pull consumer: setup + worker pool
│   └── metrics/
│       └── metrics.go   # Prometheus metric registration + helpers
└── tests/
    ├── integration/
    │   └── ws_test.go   # end-to-end: connect → chat → deal_alert
    └── unit/
        └── hub_test.go  # register, unregister, send, capacity limit
```
