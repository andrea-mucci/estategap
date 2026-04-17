# Contract: WebSocket Message Protocol

**Feature**: `021-ai-chat-search-ui`  
**Counterparty**: `019-ws-chat-realtime` (Go WebSocket server)  
**Date**: 2026-04-17

---

## Connection

- **URL**: `wss://<host>/ws/chat`
- **Authentication**: JWT Bearer token sent as query param `?token=<jwt>` (existing convention from `019-ws-chat-realtime`).
- **Subprotocol**: none (plain text JSON frames).

---

## Message Envelope

All frames are JSON objects with a mandatory `type` string discriminator:

```json
{ "type": "<event-type>", ...fields }
```

---

## Incoming Messages (Server → Client)

### `session_ready`

Sent once when the session is established and the AI is ready to receive input.

```json
{ "type": "session_ready", "sessionId": "uuid" }
```

### `text_chunk`

One token of a streaming assistant response.

```json
{
  "type": "text_chunk",
  "sessionId": "uuid",
  "messageId": "uuid",
  "chunk": "apartment"
}
```

### `stream_end`

Signals the end of a streaming assistant response.

```json
{ "type": "stream_end", "sessionId": "uuid", "messageId": "uuid" }
```

### `attachments`

Structured UI attachments to embed in the message bubble.

```json
{
  "type": "attachments",
  "sessionId": "uuid",
  "messageId": "uuid",
  "attachments": [
    {
      "type": "chips",
      "chips": [
        { "id": "1", "label": "Yes, under €400k" },
        { "id": "2", "label": "No, up to €600k" }
      ]
    }
  ]
}
```

### `criteria_update`

The AI has extracted or updated search criteria.

```json
{
  "type": "criteria_update",
  "sessionId": "uuid",
  "criteria": {
    "city": "Barcelona",
    "maxPrice": "500000",
    "bedrooms": "3",
    "propertyType": "apartment"
  }
}
```

### `error`

A recoverable error from the server.

```json
{ "type": "error", "code": "LLM_TIMEOUT", "message": "The AI service timed out. Please try again." }
```

---

## Outgoing Messages (Client → Server)

### `chat_message`

User's typed or voice-transcribed message.

```json
{
  "type": "chat_message",
  "sessionId": "uuid",
  "content": "I'm looking for a 3-bedroom apartment in Barcelona"
}
```

### `image_feedback`

User's Like/Not-this action on a carousel card.

```json
{
  "type": "image_feedback",
  "sessionId": "uuid",
  "listingId": "listing-uuid",
  "action": "like"
}
```

*`action` values*: `"like"` | `"dislike"`

### `criteria_confirm`

User confirms the criteria summary card — triggers listing search.

```json
{
  "type": "criteria_confirm",
  "sessionId": "uuid",
  "criteria": {
    "city": "Barcelona",
    "maxPrice": "500000",
    "bedrooms": "3",
    "propertyType": "apartment"
  }
}
```

---

## Error Codes

| Code | Meaning |
|------|---------|
| `AUTH_EXPIRED` | JWT has expired; client must refresh and reconnect |
| `SESSION_NOT_FOUND` | Provided sessionId does not exist |
| `LLM_TIMEOUT` | AI service did not respond in time |
| `RATE_LIMITED` | Too many messages per minute |

---

## Versioning

This contract is versioned alongside `019-ws-chat-realtime`. Breaking changes require updating both services simultaneously.
