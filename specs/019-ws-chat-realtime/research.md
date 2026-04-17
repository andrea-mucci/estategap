# Research: WebSocket Chat & Real-Time Notifications

**Branch**: `019-ws-chat-realtime` | **Date**: 2026-04-17

## WebSocket Library Selection

**Decision**: `gorilla/websocket v1.5`

**Rationale**: gorilla/websocket is the de-facto standard for Go WebSocket servers. It exposes explicit read/write deadline APIs and a `SetPongHandler` callback that maps directly to the ping/pong lifecycle described in the spec. At 10,000 connections per pod the library's per-connection goroutine model (read pump + write pump) is well understood and battle-tested in production. nhooyr.io/websocket is context-native and avoids the single-writer restriction, but its error model and connection lifecycle are less familiar and not used elsewhere in the codebase.

**Key constraint**: gorilla/websocket connections are not goroutine-safe for writes. All writes MUST be serialised through a single write goroutine (the write pump) per connection. The send channel (`chan []byte`) acts as the synchronisation boundary.

**Alternatives considered**:
- `nhooyr.io/websocket` — rejected; not used in codebase, fewer production deployments at 10k scale, less documentation on deadline behaviour.
- `gobwas/ws` — rejected; low-level, requires manual frame handling, unnecessary complexity.

---

## Goroutine Model per Connection

**Decision**: Two goroutines per connection — `readPump` and `writePump`.

**Read pump responsibilities**:
1. Set read deadline on upgrade (`30min idle timeout`).
2. Register `SetPongHandler` to reset the read deadline on pong receipt.
3. Loop: `ReadMessage()` → parse JSON envelope → dispatch to protocol handler → update `lastActivity`.
4. On any read error (deadline exceeded, close frame, network error): signal `done` channel, trigger hub deregister.

**Write pump responsibilities**:
1. Ticker at 30 s — send `websocket.PingMessage`.
2. Separate deadline timer at `ping + 10 s` — if pong not received (read pump reset), write pump closes the connection by sending close frame.
3. Loop: select on `send` channel → `WriteMessage(websocket.TextMessage, payload)` → on close signal → drain and exit.

**Rationale**: This is the canonical gorilla/websocket pattern. Separating read and write into two goroutines avoids the need for a write mutex. The `done` channel provides clean teardown coordination. At 10,000 connections this creates 20,000 goroutines, each consuming ~8 KB stack — approximately 160 MB baseline, well within pod memory budgets.

---

## JWT Extraction on WebSocket Upgrade

**Decision**: Accept token from query parameter `?token=<JWT>` as primary method; fallback to `Authorization: Bearer <token>` header.

**Rationale**: Browser WebSocket clients (`new WebSocket(url)`) cannot set custom HTTP headers. The query-parameter approach is the standard solution. The token is validated before `Upgrader.Upgrade()` is called — if invalid, return HTTP 401 and the upgrade never happens.

**Validation logic** (mirrors api-gateway `middleware/auth.go`):
1. Parse with `jwt.ParseWithClaims` using `jwt.SigningMethodHMAC` (HS256) and the same shared secret.
2. Check Redis key `blacklist:<jti>` — if present, reject.
3. Extract `Subject` (userID), `Tier` claims from `AccessTokenClaims`.
4. Do NOT perform Redis blacklist refresh mid-connection — the token's `exp` claim provides the outer bound; 15-minute access tokens expire during long sessions (clients must reconnect with a fresh token).

**Access token expiry during a live connection**: Connections are authenticated at upgrade time only. If a token expires mid-session, the connection remains open until the next reconnect. This is standard practice for WebSocket services; the 30-minute idle timeout provides a natural reconnection point. Alternatively, the client may proactively reconnect when it detects token expiry.

---

## Hub Design

**Decision**: In-memory `map[string][]*Connection` protected by `sync.RWMutex`. Per-pod; no cross-pod synchronisation.

**Rationale**: NATS JetStream uses fanout — every ws-server pod receives every `alerts.notifications.>` message. Each pod checks its local hub for the target user. If connected, deliver. If not, `Ack()` and move on. This avoids any distributed coordination overhead (no Redis pub/sub, no cluster messaging). The tradeoff is that a deal alert for a user whose connection is on a different pod is silently dropped at the WS layer and handled by the external channels (email/Telegram) via the alert-dispatcher.

**Operations**:
- `Register(conn *Connection)` — write-locks, appends to slice.
- `Unregister(conn *Connection)` — write-locks, removes from slice; deletes key if slice is empty.
- `Send(userID string, payload []byte)` — read-locks, iterates slice, non-blocking send on each connection's `send` channel (drop if channel full — log metric `ws_send_dropped_total`).
- `ConnectionCount() int` — read-locks, sums slice lengths (for Prometheus gauge).
- `Shutdown()` — write-locks, sends close frame to all connections, waits up to 5 s, force-closes remainder.

---

## gRPC Streaming Protocol to ai-chat

**Decision**: For each inbound `chat_message`, open a new bidirectional gRPC stream (`AIChatService.Chat`) to the ai-chat service. Reuse a single `grpc.ClientConn` (connection pool managed by gRPC transport layer).

**Metadata headers** (per spec 018 contract):
- `x-user-id`: authenticated user UUID from JWT claims.
- `x-subscription-tier`: tier from JWT claims (`free`, `basic`, `pro_plus`).

**Stream lifecycle**:
1. Client sends one `ChatRequest{conversation_id, user_message, country_code}`.
2. For each `ChatResponse` received with `is_final=false`: forward as `text_chunk` WS message.
3. On `ChatResponse{is_final=true}`: parse `listing_ids` and `chunk` (may contain JSON-encoded chips/criteria) → dispatch appropriate outbound WS message types.
4. On gRPC error: send `error` WS message; close stream; connection remains open.

**`conversation_id` management**: The WS client provides `session_id` in the `chat_message` envelope. This maps to `conversation_id` in the gRPC request. Empty `session_id` starts a new conversation (ai-chat service generates the ID and echoes it in the first `ChatResponse`). The WS server relays this ID back to the client in the first `text_chunk` message.

**gRPC connection target**: `AI_CHAT_GRPC_ADDR` env var (default `ai-chat:50053`).

---

## NATS Consumer for Deal Notifications

**Decision**: JetStream pull consumer with durable name `ws-server-notifications` on the `ALERTS` stream.

**Configuration** (mirrors alert-dispatcher consumer, with adjusted durable name):
```
Stream:         ALERTS
FilterSubject:  alerts.notifications.>
Durable:        ws-server-notifications
AckPolicy:      AckExplicit
AckWait:        10s   (shorter than dispatcher — ws delivery is fast)
MaxDeliver:     1     (no retry — if user not connected, skip)
MaxAckPending:  1000
DeliverPolicy:  DeliverNew
ReplayPolicy:   ReplayInstant
```

**MaxDeliver=1 rationale**: If the target user is not connected, there is no value in retrying. The alert-dispatcher has already queued the notification for email/Telegram. Re-delivering would cause duplicate notifications once the user reconnects.

**Fan-out logic**: On message receipt, parse `user_id` from the `NotificationEvent` JSON. Look up hub. If one or more connections found, encode a `deal_alert` WS message and send. Ack immediately after hub lookup (regardless of delivery success — the channel buffer drop is acceptable). If no connections found, Ack immediately.

**Worker pool**: 4 goroutines (configurable via `NATS_NOTIFICATION_WORKERS` env var) to process the pull batch in parallel.

---

## Connection Limit Enforcement

**Decision**: Enforce the 10,000-connection limit in the HTTP upgrade handler before calling `Upgrader.Upgrade()`.

**Logic**: `hub.ConnectionCount() >= maxConnections` → return HTTP 503 with `Connection: close`. The load balancer / Kubernetes ingress detects 503 and routes subsequent upgrade requests to another pod.

---

## Prometheus Metrics

| Metric | Type | Labels | Description |
|---|---|---|---|
| `ws_connections_active` | Gauge | — | Current number of open connections |
| `ws_messages_sent_total` | Counter | `type` | Messages sent to clients, by message type |
| `ws_messages_received_total` | Counter | `type` | Messages received from clients, by type |
| `ws_send_dropped_total` | Counter | — | Messages dropped due to full send channel |
| `ws_grpc_stream_duration_seconds` | Histogram | `status` | Duration of gRPC chat stream per turn |
| `ws_nats_notifications_delivered_total` | Counter | — | NATS notifications delivered to connected users |
| `ws_nats_notifications_skipped_total` | Counter | — | NATS notifications skipped (user not connected) |
| `ws_upgrade_rejected_total` | Counter | `reason` | Upgrade rejections (auth, capacity) |

---

## Graceful Shutdown Sequence

1. `SIGTERM` received → signal shutdown channel.
2. HTTP server: `srv.Shutdown(ctx)` with 5 s context — stops accepting new HTTP/WS upgrades.
3. Hub: `hub.Shutdown()` — send WebSocket close frame (`1001 Going Away`) to all connections, wait for write pumps to drain (up to 5 s), force-close any remaining.
4. NATS consumer: `sub.Unsubscribe()` → `nc.Drain()` with timeout.
5. gRPC client pool: `cc.Close()`.
6. Process exits.

Total shutdown budget: 15 s (Kubernetes `terminationGracePeriodSeconds: 30` leaves headroom).
