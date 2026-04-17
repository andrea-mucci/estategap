# Implementation Plan: WebSocket Chat & Real-Time Notifications

**Branch**: `019-ws-chat-realtime` | **Date**: 2026-04-17 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `specs/019-ws-chat-realtime/spec.md`

## Summary

Build `services/ws-server/`, a Go WebSocket gateway that (1) authenticates users via JWT during the HTTP upgrade handshake, (2) proxies AI chat sessions to the `ai-chat` service via gRPC bidirectional streaming and fans response chunks back as typed JSON messages (`text_chunk`, `chips`, `image_carousel`, `criteria_summary`, `search_results`), and (3) delivers real-time deal alerts by consuming the `ALERTS` NATS JetStream stream and routing notifications to connected users through an in-memory connection hub. The service runs on port 8081 independently of the API gateway and supports up to 10,000 simultaneous connections per pod. The skeleton (`services/ws-server/`) with empty stubs already exists in the monorepo; all implementation is net-new within that directory.

## Technical Context

**Language/Version**: Go 1.23  
**Primary Dependencies**: gorilla/websocket v1.5, golang-jwt/jwt v5, nats.go v1.37, google.golang.org/grpc v1.64+, go-chi/chi v5, prometheus/client_golang v1.19, spf13/viper v1.19, redis/go-redis v9, slog (stdlib), `libs/pkg` (go.work path dep)  
**Storage**: Redis 7 (JWT blacklist check — read-only); no PostgreSQL access  
**Testing**: Go stdlib `testing`, table-driven unit tests, testcontainers for NATS integration  
**Target Platform**: Linux (Kubernetes pod), port 8081  
**Project Type**: web-service (WebSocket + HTTP health/metrics)  
**Performance Goals**: < 500 ms first-token latency end-to-end; ≤ 10,000 simultaneous connections per pod without CPU/memory degradation; deal alerts delivered within 5 s of NATS publish  
**Constraints**: gorilla/websocket is not goroutine-safe for writes — all writes MUST go through the per-connection `writePump` goroutine; JWT validated at upgrade only (not per-message); NATS durable consumer name `ws-server-notifications` must not conflict with `alert-dispatcher`  
**Scale/Scope**: Per-pod in-memory connection store; NATS fanout ensures all pods receive all notifications; horizontal scaling via Kubernetes HPA

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Polyglot Service Architecture | ✅ Pass | Go is the prescribed language for high-throughput, latency-sensitive services; ws-server fits this profile exactly |
| II. Event-Driven Communication | ✅ Pass | NATS JetStream for async deal notifications; gRPC bidirectional streaming for synchronous AI chat — no direct HTTP between services |
| III. Country-First Data Sovereignty | ✅ Pass | ws-server is a stateless transport layer; `country_code` is forwarded to ai-chat via gRPC `ChatRequest`; no data stored |
| IV. ML-Powered Intelligence | ✅ Pass | Not applicable; ws-server does not run ML workloads |
| V. Code Quality Discipline | ✅ Pass | chi router, slog structured logging, golangci-lint, explicit error handling, no ORM, table-driven tests |
| VI. Security & Ethical Scraping | ✅ Pass | JWT HS256 validation on every upgrade; Redis blacklist check; token rejected before upgrade; no secrets in code |
| VII. Kubernetes-Native Deployment | ✅ Pass | Dockerfile + Helm chart values extension required |

**No violations. All gates pass.**

## Project Structure

### Documentation (this feature)

```text
specs/019-ws-chat-realtime/
├── plan.md                          # This file
├── research.md                      # Phase 0: library and design decisions
├── data-model.md                    # Phase 1: runtime entities and message types
├── quickstart.md                    # Phase 1: developer onboarding
├── contracts/
│   ├── websocket-protocol.md        # Phase 1: WS message type schemas (client-facing)
│   └── grpc-ai-chat.md              # Phase 1: gRPC call conventions (ws-server perspective)
└── tasks.md                         # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code

```text
services/ws-server/
├── Dockerfile
├── go.mod                           # module github.com/estategap/services/ws-server
├── .env.example
├── .golangci.yml
├── cmd/
│   ├── main.go                      # Startup: config → clients → hub → NATS consumer → HTTP server → SIGTERM handler
│   └── routes.go                    # chi router: /ws/chat, /healthz, /readyz, /metrics
├── internal/
│   ├── config/
│   │   └── config.go                # Viper env loading → Config struct
│   ├── hub/
│   │   ├── hub.go                   # Hub: RWMutex map[userID][]*Connection; Register/Unregister/Send/Shutdown
│   │   └── connection.go            # Connection struct; readPump / writePump goroutines; ping/pong; idle timeout
│   ├── handler/
│   │   ├── ws.go                    # HTTP handler: JWT validation → capacity check → upgrade → hub.Register → pump goroutines
│   │   └── health.go                # GET /healthz (liveness), GET /readyz (NATS+Redis+gRPC probes)
│   ├── middleware/
│   │   └── auth.go                  # JWT extraction (query param → header fallback) and ParseWithClaims
│   ├── protocol/
│   │   ├── messages.go              # Envelope + all inbound/outbound payload structs
│   │   └── dispatch.go              # Route inbound message type: chat_message → grpc, image_feedback / criteria_confirm → ai-chat
│   ├── grpc/
│   │   └── chat_client.go           # OpenChatStream: metadata injection, chunk fan-out, error mapping → WS messages
│   ├── nats/
│   │   └── consumer.go              # JetStream pull consumer setup (durable ws-server-notifications) + worker pool
│   └── metrics/
│       └── metrics.go               # Prometheus: ws_connections_active, ws_messages_sent_total, etc.
└── tests/
    ├── integration/
    │   └── ws_test.go               # End-to-end: connect → chat → deal_alert (testcontainers NATS)
    └── unit/
        └── hub_test.go              # Hub register/unregister/send/capacity/shutdown
```

**Structure Decision**: Follows the established `cmd/` + `internal/` pattern used by `api-gateway`, `alert-engine`, and `alert-dispatcher`. `libs/pkg` is a go.work path dependency (proto generated types for `estategapv1.AIChatServiceClient`). The `AccessTokenClaims` struct is re-declared locally in `internal/middleware/auth.go` — it is not exported from `libs/pkg` — using the same HS256 algorithm and field names as the api-gateway.

## Complexity Tracking

> No constitution violations. This section is informational only.

| Design choice | Why needed |
|---|---|
| Two goroutines per connection (readPump + writePump) | gorilla/websocket requires single-writer; this is the canonical pattern avoiding mutex on writes |
| In-memory hub (no cross-pod sync) | NATS fanout handles cross-pod delivery; adding Redis pub/sub would add latency and complexity without benefit |
| NATS `MaxDeliver=1` for ws-server consumer | Notifications not delivered to a connected user are already handled by email/Telegram via alert-dispatcher; retrying adds duplicate noise |
