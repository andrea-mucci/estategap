# Tasks: WebSocket Chat & Real-Time Notifications

**Input**: Design documents from `specs/019-ws-chat-realtime/`  
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US5)
- All paths are relative to repo root

---

## Phase 1: Setup (Project Initialization)

**Purpose**: Scaffold the `services/ws-server/` module with working build tooling. The skeleton (`cmd/main.go` stub, empty `internal/` stubs) already exists.

- [X] T001 Add Go module dependencies to `services/ws-server/go.mod`: gorilla/websocket v1.5, golang-jwt/jwt v5, go-chi/chi v5, nats.go v1.37, redis/go-redis v9, google.golang.org/grpc v1.64+, prometheus/client_golang v1.19, spf13/viper v1.19
- [X] T002 [P] Create `services/ws-server/.env.example` with all env vars from `specs/019-ws-chat-realtime/quickstart.md` (PORT, JWT_SECRET, REDIS_ADDR, AI_CHAT_GRPC_ADDR, NATS_ADDR, MAX_CONNECTIONS, PING_INTERVAL, PONG_TIMEOUT, IDLE_TIMEOUT, SHUTDOWN_TIMEOUT, NATS_WORKERS, LOG_LEVEL)
- [X] T003 [P] Create `services/ws-server/.golangci.yml` following the same structure as `services/api-gateway/.golangci.yml`
- [X] T004 [P] Create `services/ws-server/Dockerfile` following the multi-stage pattern used in `services/api-gateway/Dockerfile` (build stage → minimal runtime image, EXPOSE 8081)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core types, config, and connection lifecycle machinery. **No user story work can begin until this phase is complete.**

- [X] T005 [P] Implement `services/ws-server/internal/config/config.go`: viper-based `Config` struct with all fields from `specs/019-ws-chat-realtime/data-model.md` Config section (Port, JWTSecret, RedisAddr, AIChatGRPCAddr, NATSAddr, MaxConnections, PingInterval, PongTimeout, IdleTimeout, ShutdownTimeout, NATSWorkers); `Load() (*Config, error)` reads from env/file
- [X] T006 [P] Implement `services/ws-server/internal/protocol/messages.go`: define `Envelope` struct (Type, SessionID, Payload json.RawMessage) and all inbound payload types (`ChatMessagePayload`, `ImageFeedbackPayload`, `CriteriaConfirmPayload`) and all outbound payload types (`TextChunkPayload`, `ChipsPayload`, `ChipOption`, `ImageCarouselPayload`, `CarouselItem`, `CriteriaSummaryPayload`, `SearchResultsPayload`, `SearchListing`, `DealAlertPayload`, `ErrorPayload`) exactly as defined in `specs/019-ws-chat-realtime/data-model.md`
- [X] T007 [P] Implement `services/ws-server/internal/middleware/auth.go`: `AccessTokenClaims` struct (Email, Tier, jwt.RegisteredClaims), `ExtractToken(r *http.Request) string` (query param `?token=` → Authorization header fallback), `ValidateToken(tokenStr, jwtSecret string, redisClient *redis.Client) (*AccessTokenClaims, error)` (ParseWithClaims HS256 + Redis blacklist check `blacklist:<jti>`)
- [X] T008 [P] Implement `services/ws-server/internal/metrics/metrics.go`: register Prometheus metrics `ws_connections_active` (Gauge), `ws_messages_sent_total` (Counter, label: type), `ws_messages_received_total` (Counter, label: type), `ws_send_dropped_total` (Counter), `ws_upgrade_rejected_total` (Counter, label: reason), `ws_grpc_stream_duration_seconds` (Histogram, label: status), `ws_nats_notifications_delivered_total` (Counter), `ws_nats_notifications_skipped_total` (Counter)
- [X] T009 Implement `services/ws-server/internal/hub/connection.go`: `Connection` struct with fields: `userID string`, `tier string`, `conn *websocket.Conn`, `send chan []byte` (buffered 256), `done chan struct{}`, `connectedAt time.Time`, `lastActivity time.Time`, `cfg *config.Config`; constructor `NewConnection(userID, tier string, conn *websocket.Conn, cfg *config.Config) *Connection`
- [X] T010 Implement `writePump(hub *Hub)` method on `Connection` in `services/ws-server/internal/hub/connection.go`: 30s ping ticker (`cfg.PingInterval`); select on `send` channel → `conn.SetWriteDeadline` + `WriteMessage(TextMessage)`; on ticker → `WriteMessage(PingMessage)` + set pong deadline (`cfg.PongTimeout`); on `done` channel close → send close frame `1001 Going Away` and return; handle write errors by closing `done`
- [X] T011 Implement `readPump(hub *Hub, dispatch func(*Connection, Envelope))` method on `Connection` in `services/ws-server/internal/hub/connection.go`: `conn.SetReadDeadline(time.Now().Add(cfg.IdleTimeout))`; `conn.SetPongHandler` resets read deadline; loop: `ReadMessage` → JSON unmarshal Envelope → update `lastActivity` → call `dispatch`; on any error → `hub.Unregister(c)` + close `done`
- [X] T012 Implement `services/ws-server/internal/hub/hub.go`: `Hub` struct (`mu sync.RWMutex`, `conns map[string][]*Connection`, `maxConns int`); methods: `Register(c *Connection)`, `Unregister(c *Connection)` (removes from slice, deletes key if empty), `Send(userID string, payload []byte)` (non-blocking send on each connection's channel; increment `ws_send_dropped_total` on full channel), `ConnectionCount() int`, `New(maxConns int) *Hub`
- [X] T013 [P] Implement `services/ws-server/cmd/routes.go`: chi router with routes `GET /ws/chat` → `wsHandler`, `GET /healthz` → `healthHandler.Liveness`, `GET /readyz` → `healthHandler.Readiness`, `GET /metrics` → `promhttp.Handler()`
- [X] T014 Implement `services/ws-server/cmd/main.go`: wire `config.Load()` → Redis client → gRPC `ClientConn` to `cfg.AIChatGRPCAddr` with `WaitForReady(true)` → `hub.New(cfg.MaxConnections)` → instantiate handlers → `http.Server{Addr: ":PORT", Handler: router}` → start HTTP server in goroutine → block on `SIGTERM`/`SIGINT` (partial; SIGTERM drain completed in T027)

**Checkpoint**: `go build ./services/ws-server/...` succeeds. Foundation ready — user story work can begin.

---

## Phase 3: User Story 1 — Authenticated Chat with Streamed AI Responses (Priority: P1) 🎯 MVP

**Goal**: Users authenticate via JWT, send a chat message, and receive streamed LLM response tokens plus structured messages (chips, image carousel, criteria summary, search results) in real-time.

**Independent Test**: Connect with a valid JWT, send `{"type":"chat_message","session_id":"","payload":{"user_message":"flats in Milan","country_code":"IT"}}`, verify `text_chunk` messages stream back incrementally and a final `text_chunk` with `is_final: true` arrives.

- [X] T015 [US1] Implement `services/ws-server/internal/grpc/chat_client.go`: `ChatClient` struct wrapping `estategapv1.AIChatServiceClient`; `New(cc *grpc.ClientConn) *ChatClient`; initial gRPC `ClientConn` setup (insecure in-cluster, `WaitForReady`)
- [X] T016 [US1] Implement `OpenChatStream(ctx context.Context, userID, tier, sessionID, message, countryCode string, sendFn func([]byte)) error` on `ChatClient` in `services/ws-server/internal/grpc/chat_client.go`: inject `x-user-id` and `x-subscription-tier` metadata via `metadata.AppendToOutgoingContext`; send one `ChatRequest{conversation_id: sessionID, user_message: message, country_code: countryCode}`; `CloseSend()`; record stream start time for `ws_grpc_stream_duration_seconds`
- [X] T017 [US1] Implement chunk fan-out loop in `OpenChatStream` in `services/ws-server/internal/grpc/chat_client.go`: for each `ChatResponse`: if `chunk` starts with `{"chips":` → marshal `chips` WS envelope; starts with `{"image_carousel":` → marshal `image_carousel` envelope; starts with `{"criteria_summary":` → marshal `criteria_summary` envelope; else if `is_final=false` → marshal `text_chunk` envelope; if `is_final=true` → marshal final `text_chunk{is_final:true}` + if `listing_ids` non-empty → marshal `search_results` envelope; call `sendFn` for each; map gRPC errors to `error` WS payload codes per `specs/019-ws-chat-realtime/contracts/grpc-ai-chat.md`
- [X] T018 [US1] Implement `services/ws-server/internal/protocol/dispatch.go`: `Dispatch(c *Connection, env Envelope, chatClient *grpc.ChatClient)` — switch on `env.Type`: `"chat_message"` → unmarshal `ChatMessagePayload` → call `chatClient.OpenChatStream` in a goroutine (sendFn writes to `c.send`); `"image_feedback"` / `"criteria_confirm"` → forward to ai-chat as another `ChatRequest` with the JSON-encoded payload as `user_message`; unknown type → write `error{code:"invalid_message"}` to `c.send`; increment `ws_messages_received_total` counter
- [X] T019 [US1] Implement `services/ws-server/internal/handler/ws.go`: `WSHandler` struct holding Hub, ChatClient, Config; `ServeHTTP`: call `auth.ExtractToken` + `auth.ValidateToken` → on failure return `HTTP 401`; check `hub.ConnectionCount() >= cfg.MaxConnections` → on failure return `HTTP 503`; `websocket.Upgrader{CheckOrigin: allowAll}`.`Upgrade(w, r, nil)`; `hub.Register(conn)`; increment `ws_connections_active`; launch `go conn.writePump(hub)` and `go conn.readPump(hub, dispatch.Dispatch)`
- [X] T020 [US1] Write unit tests in `services/ws-server/tests/unit/hub_test.go`: table-driven tests for `hub.Register`, `hub.Unregister`, `hub.Send` (connected user receives message), `hub.Send` (disconnected user is a no-op), `hub.ConnectionCount`, capacity rejection (Register returns error when at limit)

**Checkpoint**: Connecting with a valid JWT and sending a `chat_message` produces streamed `text_chunk` WS messages (requires ai-chat service running).

---

## Phase 4: User Story 2 — Real-Time Deal Alert Delivery (Priority: P2)

**Goal**: Connected users receive `deal_alert` WS messages within 5 s of a matching `alerts.notifications.*` NATS event being published, with no user action required.

**Independent Test**: Establish a connection for a test user, publish a `NotificationEvent` JSON to `alerts.notifications.IT` on the `ALERTS` NATS stream with a matching `user_id`, and verify a `deal_alert` WS message arrives within 5 s.

- [X] T021 [US2] Implement `services/ws-server/internal/nats/consumer.go`: `Consumer` struct holding NATS `JetStreamContext`, `Hub`, `Config`; `New(js nats.JetStreamContext, hub *Hub, cfg *config.Config) *Consumer`; `Setup() error` — call `js.AddConsumer` with config: Stream `ALERTS`, Durable `ws-server-notifications`, FilterSubject `alerts.notifications.>`, AckExplicit, AckWait 10s, MaxDeliver 1, MaxAckPending 1000, DeliverNew, ReplayInstant; then `js.PullSubscribe("alerts.notifications.>", "ws-server-notifications", nats.Bind("ALERTS","ws-server-notifications"), nats.ManualAck(), nats.AckWait(10*time.Second), nats.MaxAckPending(1000))`
- [X] T022 [US2] Implement `Start(ctx context.Context)` on `Consumer` in `services/ws-server/internal/nats/consumer.go`: launch `cfg.NATSWorkers` goroutines; each goroutine loops: `sub.Fetch(10, nats.MaxWait(2*time.Second))`; for each msg: unmarshal `NotificationEvent` JSON (extract `user_id`, `listing_id`, `deal_score`, `deal_tier`, `listing_summary`, `rule_name`, `triggered_at`, `event_id`); build `DealAlertPayload`; marshal `Envelope{Type:"deal_alert"}`; call `hub.Send(userID, payload)`; if hub.Send delivered → increment `ws_nats_notifications_delivered_total`; else → increment `ws_nats_notifications_skipped_total`; `msg.Ack()`; stop on ctx cancellation
- [X] T023 [US2] Wire NATS consumer into `services/ws-server/cmd/main.go`: create NATS connection with retry options (matching pattern in `services/alert-engine/cmd/main.go`); `js, _ := nc.JetStream()`; `consumer.New(js, hub, cfg).Setup()`; `go consumer.Start(ctx)`; add `nc.Drain()` to shutdown sequence

**Checkpoint**: Publishing a matching NATS event delivers a `deal_alert` WS message to the connected user within 5 s.

---

## Phase 5: User Story 3 — Rejected Connection for Unauthenticated Users (Priority: P2)

**Goal**: Connections with missing, expired, or malformed JWTs are rejected at the HTTP upgrade with a clear 401 before any WebSocket session is created.

**Independent Test**: Attempt WebSocket upgrade with no token, an expired token, and a tampered token — each returns HTTP 401. Attempt upgrade when hub is at capacity — returns HTTP 503.

- [X] T024 [US3] Complete auth rejection path in `services/ws-server/internal/handler/ws.go`: ensure `HTTP 401` response body is `{"error":"unauthorized","reason":"<specific_reason>"}` for missing token, invalid signature, expired token, and blacklisted JTI; increment `ws_upgrade_rejected_total{reason="auth"}` counter
- [X] T025 [US3] Complete capacity rejection path in `services/ws-server/internal/handler/ws.go`: ensure `HTTP 503` response body is `{"error":"capacity","reason":"connection limit reached"}` and sets `Retry-After: 5` header; increment `ws_upgrade_rejected_total{reason="capacity"}` counter

**Checkpoint**: HTTP upgrade with invalid token → 401. Upgrade when at capacity → 503. No WebSocket connection created in either case.

---

## Phase 6: User Story 4 — Stable Long-Lived Connection (Priority: P3)

**Goal**: Connections stay alive indefinitely through ping/pong, close cleanly after 30 min idle, and clients can resume their conversation after reconnecting.

**Independent Test**: Establish a connection, observe ping frames every 30 s, verify connection remains open after 60 s of inactivity (≥ 2 pings survived), then stop responding to pings and verify the connection closes within `PingInterval + PongTimeout` (40 s max).

- [X] T026 [US4] Verify and complete `services/ws-server/internal/hub/connection.go`: confirm `writePump` uses `cfg.PingInterval` for the ticker, sets an explicit write deadline of `cfg.PongTimeout` on each ping write, and that `readPump` `SetPongHandler` resets `conn.SetReadDeadline(time.Now().Add(cfg.IdleTimeout))`; the idle timer must reset on user message arrival (`lastActivity` update in readPump) but NOT on keepalive pong
- [X] T027 [US4] Write integration test in `services/ws-server/tests/integration/ws_test.go` (testcontainers NATS): connect with valid JWT → verify at least two ping frames arrive within 70 s → verify connection remains alive → stop answering pings → verify connection closes within 45 s with close code 1001; second test: verify connection closes with code 1001 after `IdleTimeout` with no user messages (set low IdleTimeout in test config)

**Checkpoint**: Connection keeps alive through multiple ping/pong cycles and closes predictably on idle or missed pong.

---

## Phase 7: User Story 5 — Graceful System Maintenance (Priority: P3)

**Goal**: On SIGTERM, all connected users receive a `server_shutting_down` error message before disconnection, and the service exits cleanly within the Kubernetes termination budget.

**Independent Test**: Establish multiple connections, send SIGTERM to the process, verify each client receives `{"type":"error","payload":{"code":"server_shutting_down","message":"..."}}` then a WebSocket close frame with code 1001, all within 5 s.

- [X] T028 [US5] Implement `hub.Shutdown(timeout time.Duration)` in `services/ws-server/internal/hub/hub.go`: write-lock `conns`; for each connection, non-blocking send of `Envelope{Type:"error", Payload: ErrorPayload{Code:"server_shutting_down"}}` to `send` channel; then send close frame signal; wait for all `done` channels with `timeout` deadline using `sync.WaitGroup`; force-close any remaining connections after timeout
- [X] T029 [US5] Complete SIGTERM shutdown sequence in `services/ws-server/cmd/main.go`: on signal → cancel context → `httpSrv.Shutdown(ctx5s)` → `hub.Shutdown(cfg.ShutdownTimeout)` → `consumer.Stop()` + `nc.Drain()` → `grpcConn.Close()` → `os.Exit(0)`; total budget: 15 s (within Kubernetes `terminationGracePeriodSeconds: 30`)

**Checkpoint**: All connections receive shutdown notification and close frame before process exits. `go test` shutdown test passes.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Health endpoints, full metrics emission, integration tests for all user stories, lint gate.

- [X] T030 [P] Implement `services/ws-server/internal/handler/health.go`: `GET /healthz` always returns `200 OK {"status":"ok"}`; `GET /readyz` checks NATS connection via `nc.Status() == nats.CONNECTED`, Redis via `redisClient.Ping(ctx)`, gRPC via `cc.GetState() != connectivity.Shutdown` — returns `200 OK` if all healthy, `503` with failing component names otherwise
- [X] T031 [P] Wire metric emission points: `ws_connections_active.Inc()/Dec()` in `hub.Register/Unregister`; `ws_messages_sent_total` in `hub.Send` (label from Envelope.Type); `ws_messages_received_total` in `protocol/dispatch.go` (already noted in T018); `ws_grpc_stream_duration_seconds` in `grpc/chat_client.go` (already noted in T016); confirm all eight metrics from T008 are being incremented in the correct code paths
- [X] T032 [P] Write end-to-end integration test in `services/ws-server/tests/integration/ws_test.go`: spin up test HTTP server + real gorilla/websocket client; connect with a valid test JWT (sign locally with test secret); send `chat_message` → mock gRPC server streams back 3 `ChatResponse` chunks + 1 final; assert client receives 3 `text_chunk` messages then `text_chunk{is_final:true}`; assert `ws_messages_sent_total` counter incremented
- [X] T033 [P] Write deal alert integration test in `services/ws-server/tests/integration/ws_test.go` (testcontainers NATS): connect; publish `NotificationEvent` JSON to `alerts.notifications.IT` on `ALERTS` stream; assert `deal_alert` WS message arrives within 5 s with correct `listing_id` and `deal_score`
- [ ] T034 Run `golangci-lint run ./...` from `services/ws-server/` and fix all lint errors; run `go test ./...` and confirm all tests pass; follow `specs/019-ws-chat-realtime/quickstart.md` to validate the full service start-up sequence

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — **blocks all user story phases**
- **Phase 3 (US1)**: Depends on Phase 2 — no dependency on US2–US5
- **Phase 4 (US2)**: Depends on Phase 2 — no dependency on US1, US3–US5
- **Phase 5 (US3)**: Depends on Phase 2 + T019 (handler/ws.go created in US1 phase) — starts after Phase 3
- **Phase 6 (US4)**: Depends on Phase 2 + T009–T011 (connection.go complete) — starts after Phase 2
- **Phase 7 (US5)**: Depends on Phase 2 + T012 (hub.go) — starts after Phase 2
- **Phase 8 (Polish)**: Depends on all prior phases being complete

### User Story Dependencies

- **US1 (P1)**: Starts after Phase 2. No dependency on other stories.
- **US2 (P2)**: Starts after Phase 2. No dependency on other stories. Can run in parallel with US1.
- **US3 (P2)**: Starts after Phase 3 (reuses `handler/ws.go` from US1). Completes the auth/capacity rejection paths started in T019.
- **US4 (P3)**: Starts after Phase 2. Verifies connection.go keepalive behaviour built in T009–T011. Can run in parallel with US1/US2.
- **US5 (P3)**: Starts after Phase 2. Adds hub.Shutdown and completes cmd/main.go SIGTERM wiring. Can run in parallel with US1/US2/US4.

### Critical Path

```
T001 → T005-T014 (Phase 2, parallelisable within) → T015-T020 (US1) → DONE MVP
                                                   → T021-T023 (US2) → parallel with US1
```

---

## Parallel Opportunities

### Phase 2 Parallel Batch

```
# These five tasks touch different files — launch together after T001:
T005  services/ws-server/internal/config/config.go
T006  services/ws-server/internal/protocol/messages.go
T007  services/ws-server/internal/middleware/auth.go
T008  services/ws-server/internal/metrics/metrics.go
# Then sequentially:
T009 → T010 → T011  services/ws-server/internal/hub/connection.go
T012                 services/ws-server/internal/hub/hub.go  (after T009, uses Connection type)
T013                 services/ws-server/cmd/routes.go  (parallel with T009-T012)
T014                 services/ws-server/cmd/main.go  (after T012, T013)
```

### US1 Parallel Batch

```
# T015 (grpc/chat_client.go) and T018 (protocol/dispatch.go) are different files:
T015 → T016 → T017  services/ws-server/internal/grpc/chat_client.go  (sequential)
T018                 services/ws-server/internal/protocol/dispatch.go  (parallel with T015-T017, finalised after T017)
T019                 services/ws-server/internal/handler/ws.go  (after T015, T018)
T020                 services/ws-server/tests/unit/hub_test.go  (parallel with T015-T019)
```

### US2 Parallel with US1

```
# US2 touches entirely different files from US1 — both can run simultaneously:
Developer A: T015 → T016 → T017 → T018 → T019 → T020  (US1)
Developer B: T021 → T022 → T023                         (US2)
```

### Phase 8 Parallel Batch

```
T030  internal/handler/health.go
T031  metrics emission wiring (different files)
T032  tests/integration/ws_test.go (chat stream test)
T033  tests/integration/ws_test.go (deal alert test — same file as T032, serialise)
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete **Phase 1** (T001–T004): 4 tasks, parallelisable
2. Complete **Phase 2** (T005–T014): 10 tasks, partially parallelisable — CRITICAL BLOCKER
3. Complete **Phase 3** (T015–T020): 6 tasks — delivers authenticated chat with streaming
4. **STOP AND VALIDATE**: Connect with valid JWT, send `chat_message`, verify streamed `text_chunk` messages
5. Deploy/demo: users can search properties via AI chat

### Incremental Delivery

- After Phase 3: MVP chat streaming is live
- After Phase 4: Real-time deal alerts added (no UI changes needed)
- After Phase 5: Auth rejection hardened with proper HTTP responses
- After Phase 6: Keepalive and idle timeout verified
- After Phase 7: Graceful shutdown production-ready
- After Phase 8: Full lint/test gate, health probes, metrics for observability

### Parallel Team Strategy (2 developers)

1. Both complete Phase 1 + Phase 2 together
2. Once Phase 2 complete:
   - **Dev A**: Phase 3 (US1 — chat streaming, MVP)
   - **Dev B**: Phase 4 (US2 — deal alerts) + Phase 6 (US4 — keepalive)
3. Dev A completes Phase 5 (US3 — auth rejection) using `handler/ws.go` from Phase 3
4. Dev B completes Phase 7 (US5 — graceful shutdown)
5. Both complete Phase 8 (polish, integration tests, lint)

---

## Notes

- `[P]` tasks = different files, no dependencies on incomplete tasks — safe to run in parallel
- `[Story]` label maps each task to the user story it delivers
- The ws-server skeleton already exists (`cmd/main.go` stub, empty `internal/` dirs) — no directory creation needed
- Proto-generated types (`estategapv1.AIChatServiceClient`, `ChatRequest`, `ChatResponse`) come from `libs/pkg` via `go.work`
- JWT validation logic mirrors `services/api-gateway/internal/middleware/auth.go` and `service/auth.go` — copy the `AccessTokenClaims` struct and validation pattern locally; do not import across service boundaries
- NATS `ALERTS` stream is created by `services/alert-engine` — ws-server only adds a new durable consumer and does not create or modify the stream definition
- gorilla/websocket write safety: **only the `writePump` goroutine may call `conn.WriteMessage`** — all other code enqueues on `c.send`
