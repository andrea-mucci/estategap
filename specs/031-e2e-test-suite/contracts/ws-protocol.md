# Contract: WebSocket Protocol (E2E Test Reference)

**Source of truth**: `services/ws-server/internal/protocol/messages.go`  
**Endpoint**: `ws://localhost:8081/ws?token=<jwt>`

This document is the E2E test suite's reference for the WebSocket wire protocol. Tests assert against these exact message shapes.

---

## Envelope

All messages (inbound and outbound) use this wrapper:

```json
{
  "type": "<message_type>",
  "session_id": "<uuid | omit>",
  "payload": { }
}
```

---

## Client → Server Messages

### `chat_message`

```json
{
  "type": "chat_message",
  "session_id": "optional-uuid-for-reconnection",
  "payload": {
    "user_message": "Looking for 3BR apartment in Milan under 300k EUR",
    "country_code": "IT"
  }
}
```

### `image_feedback`

```json
{
  "type": "image_feedback",
  "session_id": "uuid",
  "payload": {
    "listing_id": "uuid",
    "action": "like | dislike | skip"
  }
}
```

### `criteria_confirm`

```json
{
  "type": "criteria_confirm",
  "session_id": "uuid",
  "payload": {
    "confirmed": true,
    "notes": "optional free-text override"
  }
}
```

---

## Server → Client Messages

### `text_chunk`

Streamed progressively while LLM generates the response.

```json
{
  "type": "text_chunk",
  "session_id": "uuid",
  "payload": {
    "text": "I can help you find apartments in Milan...",
    "conversation_id": "uuid",
    "is_final": false
  }
}
```

The final chunk has `"is_final": true`. Tests MUST collect all chunks until `is_final` is true, then assert the accumulated text is non-empty.

### `chips`

Optional; sent when the AI identifies selectable options.

```json
{
  "type": "chips",
  "session_id": "uuid",
  "payload": {
    "options": [
      { "label": "Milan centre", "value": "milan-centre" },
      { "label": "Milan suburbs", "value": "milan-suburbs" }
    ]
  }
}
```

### `criteria_summary`

Sent after LLM turn completes and criteria are extracted. Always follows the last `text_chunk` with `is_final: true`.

```json
{
  "type": "criteria_summary",
  "session_id": "uuid",
  "payload": {
    "conversation_id": "uuid",
    "criteria": {
      "country_code": "IT",
      "city": "Milan",
      "min_bedrooms": 3,
      "max_price_eur": 300000
    },
    "ready_to_search": true
  }
}
```

### `image_carousel`

Sent when the AI wants to gather user preferences via visual selection.

```json
{
  "type": "image_carousel",
  "session_id": "uuid",
  "payload": {
    "listings": [
      {
        "listing_id": "uuid",
        "title": "Elegant 3BR in Brera",
        "price_eur": 285000,
        "area_m2": 95,
        "city": "Milan",
        "photo_urls": ["https://..."],
        "deal_score": 0.87
      }
    ]
  }
}
```

### `search_results`

Sent after criteria confirmation triggers a search.

```json
{
  "type": "search_results",
  "session_id": "uuid",
  "payload": {
    "conversation_id": "uuid",
    "total_count": 47,
    "listings": [
      {
        "listing_id": "uuid",
        "title": "Spacious 3BR near Duomo",
        "price_eur": 270000,
        "area_m2": 98,
        "bedrooms": 3,
        "city": "Milan",
        "deal_score": 0.91,
        "deal_tier": 1,
        "image_url": "https://..."
      }
    ]
  }
}
```

### `deal_alert`

Pushed by the server when a scored listing matches the user's alert rules.

```json
{
  "type": "deal_alert",
  "payload": {
    "event_id": "uuid",
    "listing_id": "uuid",
    "title": "Spacious 3BR near Duomo",
    "address": "Via Brera 12, Milan",
    "price_eur": 270000,
    "area_m2": 98,
    "deal_score": 0.91,
    "deal_tier": 1,
    "photo_url": "https://...",
    "analysis_url": "https://...",
    "rule_name": "Milan 3BR deals",
    "triggered_at": "2026-04-17T10:23:44Z"
  }
}
```

### `error`

```json
{
  "type": "error",
  "payload": {
    "code": "UNAUTHORIZED | RATE_LIMITED | INTERNAL_ERROR",
    "message": "Human-readable description"
  }
}
```

---

## Connection Lifecycle

| Event | Details |
|-------|---------|
| **Authentication** | Token passed as `?token=<jwt>` query param at connect time |
| **Invalid JWT** | Server closes with WebSocket close code `4001` |
| **Ping interval** | Server sends WebSocket ping every 30 s (overridable via `WS_PING_INTERVAL_SECS` in test env) |
| **Idle timeout** | Server closes with code `1001` after 30 min of no client messages (overridable via `WS_IDLE_TIMEOUT_SECS`) |
| **Reconnection** | Client reconnects with same `session_id` in the first `chat_message`; server restores conversation history |
