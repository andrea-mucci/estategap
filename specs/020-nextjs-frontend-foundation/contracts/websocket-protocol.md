# Contract: WebSocket Protocol (Frontend ↔ ws-server)

**Date**: 2026-04-17  
**Server**: `services/ws-server` (Go, gorilla/websocket)  
**Client**: `frontend/src/lib/ws.ts` (TypeScript, browser WebSocket API)

---

## Connection

**Endpoint**: `ws(s)://{WS_HOST}/ws/chat`  
**Auth**: JWT passed as query parameter `?token={accessToken}`  
**Upgrade**: Standard HTTP → WebSocket upgrade (HTTP 101)

```
GET /ws/chat?token=eyJ... HTTP/1.1
Upgrade: websocket
Connection: Upgrade
```

On auth failure (invalid/expired JWT): server responds `401 Unauthorized` (JSON body) — no upgrade.  
On capacity limit: server responds `503 Service Unavailable` with `Retry-After: 5` header.

---

## Message Format

All messages (both directions) use a JSON envelope:

```json
{
  "type": "<message_type>",
  "session_id": "<optional uuid>",
  "payload": { ... }
}
```

`session_id` is omitted when not applicable (e.g., `ping`/`pong`, `error`).

---

## Client → Server Messages

### `chat_message`
Send a user's natural language query to the AI.

```json
{
  "type": "chat_message",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": {
    "user_message": "Find me a 3-bedroom apartment in Madrid under 400k",
    "country_code": "ES"
  }
}
```

### `image_feedback`
User likes or dismisses a listing shown in the carousel.

```json
{
  "type": "image_feedback",
  "session_id": "550e8400-...",
  "payload": {
    "listing_id": "abc123",
    "action": "like"
  }
}
```

`action` values: `"like"` | `"dismiss"`

### `criteria_confirm`
User confirms or adjusts the extracted search criteria.

```json
{
  "type": "criteria_confirm",
  "session_id": "550e8400-...",
  "payload": {
    "confirmed": true,
    "notes": "Actually I prefer 2 bedrooms"
  }
}
```

### `ping`
Heartbeat sent by client every 25 seconds to keep the connection alive.

```json
{ "type": "ping", "payload": {} }
```

---

## Server → Client Messages

### `text_chunk`
Streaming AI response token. Multiple chunks arrive; `is_final: true` marks the last.

```json
{
  "type": "text_chunk",
  "session_id": "550e8400-...",
  "payload": {
    "text": "I found several great options",
    "conversation_id": "conv-789",
    "is_final": false
  }
}
```

Client action: accumulate into the streaming message; flip `isStreaming` to false when `is_final=true`.

### `chips`
Multiple-choice options for the user to select from.

```json
{
  "type": "chips",
  "payload": {
    "options": [
      { "label": "Madrid", "value": "ES-MAD" },
      { "label": "Barcelona", "value": "ES-BCN" }
    ]
  }
}
```

### `image_carousel`
A set of listing cards to display visually.

```json
{
  "type": "image_carousel",
  "payload": {
    "listings": [
      {
        "listing_id": "abc123",
        "title": "Bright 3BR in Salamanca",
        "price_eur": 385000,
        "area_m2": 95.0,
        "city": "Madrid",
        "photo_urls": ["https://..."],
        "deal_score": 0.87
      }
    ]
  }
}
```

### `criteria_summary`
The AI has extracted structured search criteria and is requesting confirmation.

```json
{
  "type": "criteria_summary",
  "session_id": "550e8400-...",
  "payload": {
    "conversation_id": "conv-789",
    "criteria": {
      "country": "ES",
      "city": "Madrid",
      "bedrooms_min": 3,
      "price_max_eur": 400000
    },
    "ready_to_search": true
  }
}
```

### `search_results`
Final search results after criteria are confirmed.

```json
{
  "type": "search_results",
  "payload": {
    "conversation_id": "conv-789",
    "total_count": 42,
    "listings": [
      {
        "listing_id": "abc123",
        "title": "Bright 3BR",
        "price_eur": 385000,
        "area_m2": 95.0,
        "bedrooms": 3,
        "city": "Madrid",
        "deal_score": 0.87,
        "deal_tier": 1,
        "image_url": "https://...",
        "analysis_url": "/listing/abc123"
      }
    ]
  }
}
```

### `deal_alert`
A real-time push notification when an alert rule fires. Delivered to all authenticated connections for the user, regardless of active chat session.

```json
{
  "type": "deal_alert",
  "payload": {
    "event_id": "evt-001",
    "listing_id": "xyz789",
    "title": "Penthouse in Malasaña",
    "address": "Calle del Pez 14, Madrid",
    "price_eur": 320000,
    "area_m2": 78.0,
    "deal_score": 0.92,
    "deal_tier": 1,
    "photo_url": "https://...",
    "analysis_url": "/listing/xyz789",
    "rule_name": "Madrid < 350k",
    "triggered_at": "2026-04-17T14:32:00Z"
  }
}
```

### `error`
An error from the server (auth failure, validation error, AI provider error, etc.).

```json
{
  "type": "error",
  "payload": {
    "code": "SESSION_NOT_FOUND",
    "message": "Chat session has expired. Start a new conversation."
  }
}
```

### `pong`
Heartbeat acknowledgment in response to a `ping`.

```json
{ "type": "pong", "payload": {} }
```

---

## Connection Lifecycle

```
Client                          Server
  |                               |
  |-- GET /ws/chat?token=... ---> |
  |<-- 101 Switching Protocols -- |
  |                               |
  |-- ping (every 25s) ---------> |
  |<-- pong -------------------- |
  |                               |
  |-- chat_message -------------> |
  |<-- text_chunk (streaming) -- |
  |<-- text_chunk (is_final) --- |
  |<-- chips ------------------- |
  |-- criteria_confirm ---------> |
  |<-- criteria_summary -------- |
  |<-- search_results ---------- |
  |                               |
  |  (alert fires via NATS)       |
  |<-- deal_alert -------------- |
  |                               |
  |-- Close (navigating away) --> |
```

---

## Reconnection Contract

The frontend `WebSocketManager` is solely responsible for reconnection. The server holds no session state between connections (stateless upgrade). Upon reconnect:
- The client re-authenticates with a fresh JWT (obtained from NextAuth session).
- The client re-sends any unacknowledged message if needed (chat continuation is handled by server session state stored in Redis via `session_id`).

**Backoff schedule**: 1s → 2s → 4s → 8s → 16s → 30s (capped). Reset to 1s on successful open.
