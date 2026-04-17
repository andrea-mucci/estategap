# Contract: WebSocket Protocol

**Service**: `ws-server`  
**Endpoint**: `ws://<host>:8081/ws/chat`  
**Protocol**: WebSocket (RFC 6455) over HTTP/1.1 upgrade  
**Message encoding**: UTF-8 JSON

---

## Authentication

The JWT access token MUST be provided during the HTTP upgrade handshake via one of:

1. **Query parameter** (preferred for browser clients): `?token=<JWT>`
2. **Authorization header**: `Authorization: Bearer <JWT>`

If the token is absent, expired, or has an invalid signature the server returns `HTTP 401 Unauthorized` and the upgrade is refused. No WebSocket connection is established.

If the per-pod connection limit (10,000) is reached the server returns `HTTP 503 Service Unavailable`.

---

## Message Envelope

Every message in both directions is a JSON object with this top-level structure:

```json
{
  "type":       "<message-type>",
  "session_id": "<conversation-uuid-or-empty>",
  "payload":    { ... }
}
```

| Field | Required | Description |
|---|---|---|
| `type` | always | Identifies the message type (see below) |
| `session_id` | conditional | Conversation UUID. Client sets this on `chat_message`. Server echoes it on all response messages for that conversation. Empty string starts a new conversation. |
| `payload` | always | Type-specific object (see schemas below) |

---

## Client → Server Message Types

### `chat_message`

Send a natural-language query to the AI assistant.

```json
{
  "type": "chat_message",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": {
    "user_message": "Show me 3-bedroom flats in Milan under €300k near the metro",
    "country_code": "IT"
  }
}
```

| Field | Required | Description |
|---|---|---|
| `user_message` | always | Natural-language text from the user |
| `country_code` | first turn only | ISO 3166-1 alpha-2 (e.g., `"IT"`, `"ES"`, `"DE"`) |

**Notes**:
- Sending a `chat_message` while a streaming response is in progress is undefined behaviour. Clients SHOULD wait for the final `text_chunk` (`is_final: true`) before sending the next message.
- `session_id` empty or omitted starts a new conversation; the server echoes the assigned ID in the first response.

---

### `image_feedback`

Report user interaction with a property in an image carousel.

```json
{
  "type": "image_feedback",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": {
    "listing_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "action": "like"
  }
}
```

| Field | Values |
|---|---|
| `action` | `"like"` \| `"dislike"` \| `"view"` |

---

### `criteria_confirm`

Confirm or reject the criteria summary card.

```json
{
  "type": "criteria_confirm",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": {
    "confirmed": true,
    "notes": "Also consider Navigli area"
  }
}
```

| Field | Required | Description |
|---|---|---|
| `confirmed` | always | `true` = proceed with search; `false` = continue refining |
| `notes` | optional | Additional context for the AI on rejection |

---

## Server → Client Message Types

### `text_chunk`

Streamed token fragment from the LLM. Arrives multiple times per turn; `is_final: true` signals end of this assistant turn.

```json
{
  "type": "text_chunk",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": {
    "text": "Sure! Here are some options",
    "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
    "is_final": false
  }
}
```

```json
{
  "type": "text_chunk",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": {
    "text": "",
    "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
    "is_final": true
  }
}
```

Clients SHOULD concatenate `text` fields in order to reconstruct the full assistant message.

---

### `chips`

Quick-reply buttons for the user to tap.

```json
{
  "type": "chips",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": {
    "options": [
      { "label": "Increase budget to €350k",  "value": "increase budget to 350k" },
      { "label": "Add parking requirement",    "value": "I need parking" },
      { "label": "Start over",                 "value": "start over" }
    ]
  }
}
```

The client SHOULD send the selected `value` as the `user_message` of the next `chat_message`.

---

### `image_carousel`

A deck of property images for the user to swipe through.

```json
{
  "type": "image_carousel",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": {
    "listings": [
      {
        "listing_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        "title": "Bright 3BR in Porta Venezia",
        "price_eur": 289000,
        "area_m2": 95,
        "city": "Milan",
        "photo_urls": [
          "https://cdn.estategap.com/listings/f47ac10b/1.jpg",
          "https://cdn.estategap.com/listings/f47ac10b/2.jpg"
        ],
        "deal_score": 0.84
      }
    ]
  }
}
```

---

### `criteria_summary`

A structured card showing the finalised search criteria. Sent before `search_results` when the AI considers the criteria complete.

```json
{
  "type": "criteria_summary",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": {
    "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
    "criteria": {
      "country": "IT",
      "city": "Milan",
      "property_type": "residential",
      "bedrooms_min": 3,
      "price_max_eur": 300000,
      "amenities": ["metro_proximity"]
    },
    "ready_to_search": true
  }
}
```

The `criteria` object is an opaque JSON value forwarded from the ai-chat service `CriteriaState`.

---

### `search_results`

Matching listings returned after criteria are confirmed.

```json
{
  "type": "search_results",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": {
    "conversation_id": "550e8400-e29b-41d4-a716-446655440000",
    "total_count": 42,
    "listings": [
      {
        "listing_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
        "title": "Bright 3BR in Porta Venezia",
        "price_eur": 289000,
        "area_m2": 95,
        "bedrooms": 3,
        "city": "Milan",
        "deal_score": 0.84,
        "deal_tier": 1,
        "image_url": "https://cdn.estategap.com/listings/f47ac10b/1.jpg",
        "analysis_url": "https://estategap.com/listings/f47ac10b"
      }
    ]
  }
}
```

---

### `deal_alert`

A real-time deal notification pushed from the NATS stream.

```json
{
  "type": "deal_alert",
  "payload": {
    "event_id": "a8098c1a-f86e-11da-bd1a-00112444be1e",
    "listing_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
    "title": "3BR near Duomo — just listed",
    "address": "Via Torino 15, Milan",
    "price_eur": 265000,
    "area_m2": 88,
    "deal_score": 0.91,
    "deal_tier": 1,
    "photo_url": "https://cdn.estategap.com/listings/f47ac10b/1.jpg",
    "analysis_url": "https://estategap.com/listings/f47ac10b",
    "rule_name": "Milan 3BR under 300k",
    "triggered_at": "2026-04-17T14:23:00Z"
  }
}
```

`session_id` is omitted — deal alerts are not associated with a conversation session.

---

### `error`

Returned when the server cannot fulfil a request. The WebSocket connection remains open after an error unless the error type is `server_shutting_down`.

```json
{
  "type": "error",
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "payload": {
    "code": "ai_unavailable",
    "message": "The AI assistant is temporarily unavailable. Please try again in a moment."
  }
}
```

**Error codes**:

| `code` | Meaning | Connection closes? |
|---|---|---|
| `ai_unavailable` | gRPC connection to ai-chat failed | No |
| `ai_limit_exceeded` | Usage quota exceeded for this tier | No |
| `conversation_not_found` | Invalid `session_id` provided | No |
| `invalid_message` | Malformed JSON or unknown message type | No |
| `stream_error` | Mid-stream gRPC error after partial response | No |
| `server_shutting_down` | Graceful shutdown in progress | Yes (connection draining) |

---

## Keepalive

The server sends WebSocket `Ping` frames every **30 seconds**. Clients MUST respond with a `Pong` frame (most WebSocket libraries do this automatically). If no `Pong` is received within **10 seconds** of a `Ping`, the server closes the connection with close code `1001 (Going Away)`.

## Idle Timeout

If no `chat_message`, `image_feedback`, or `criteria_confirm` is received for **30 minutes**, the server closes the connection with close code `1001 (Going Away)`. Keepalive pings/pongs do not reset the idle timer.

## Reconnection

Clients SHOULD implement exponential backoff reconnection (initial delay 1 s, max 30 s). On reconnect, clients provide the previous `session_id` to resume the conversation. The ai-chat service preserves conversation state in Redis and will resume from where the conversation left off.
