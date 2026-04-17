# Contract: gRPC — ws-server → ai-chat-service

**Caller**: `ws-server`  
**Target**: `ai-chat` service  
**Transport**: gRPC with TLS (in-cluster: plaintext acceptable)  
**Default address**: `ai-chat:50053` (env `AI_CHAT_GRPC_ADDR`)  
**Proto package**: `estategap.v1` (`proto/estategap/v1/ai_chat.proto`)

---

## RPC Used

### `AIChatService.Chat` — bidirectional streaming

Used for every `chat_message` inbound message. `ws-server` opens one stream per chat turn.

**Client stream (ws-server → ai-chat)**:

```protobuf
message ChatRequest {
  string conversation_id = 1;   // empty to start new conversation; non-empty to continue
  string user_message    = 2;   // the user's natural-language input
  string country_code    = 3;   // ISO 3166-1 alpha-2; required on first turn of a conversation
}
```

The client sends exactly **one** `ChatRequest` per stream, then half-closes the send side (`CloseSend()`).

**Server stream (ai-chat → ws-server)**:

```protobuf
message ChatResponse {
  string          conversation_id = 1;  // echoed on every chunk
  string          chunk           = 2;  // token text or JSON payload (see below)
  bool            is_final        = 3;  // true on last message of a turn
  repeated string listing_ids     = 4;  // populated only on finalization (is_final=true)
}
```

**Chunk interpretation**:

| `chunk` content | `is_final` | WS message to emit |
|---|---|---|
| Plain text token | `false` | `text_chunk{text: chunk, is_final: false}` |
| JSON starting with `{"chips":` | `false` | `chips{options: [...]}` |
| JSON starting with `{"image_carousel":` | `false` | `image_carousel{listings: [...]}` |
| JSON starting with `{"criteria_summary":` | `false` | `criteria_summary{...}` |
| Empty string | `true` | `text_chunk{text: "", is_final: true}` + resolve `listing_ids` |
| Any other JSON | `true` | `search_results{...}` (parse as search results payload) |

**Finalization on `is_final=true`**:
1. Emit final `text_chunk` with `is_final: true`.
2. If `listing_ids` is non-empty, emit `search_results` (ws-server fetches full listing data from the API gateway or passes IDs to the client to resolve — see assumption below).
3. Close the gRPC stream.

> **Assumption**: For MVP, `listing_ids` are passed directly to the client in the `search_results` payload and the client fetches details via REST. ws-server does not make a secondary gRPC call to resolve listings.

---

## Required gRPC Metadata

All `AIChatService.Chat` calls MUST include these outgoing metadata headers:

| Key | Value | Source |
|---|---|---|
| `x-user-id` | User UUID (from JWT `sub` claim) | JWT claims on upgrade |
| `x-subscription-tier` | `"free"` \| `"basic"` \| `"pro_plus"` | JWT `tier` claim |

These headers are set via `metadata.AppendToOutgoingContext(ctx, ...)` before opening the stream.

---

## Error Handling

| gRPC Status Code | ws-server action |
|---|---|
| `UNAUTHENTICATED` | Emit `error{code: "ai_unavailable"}` (should not happen if JWT is valid) |
| `RESOURCE_EXHAUSTED` | Emit `error{code: "ai_limit_exceeded"}` |
| `NOT_FOUND` | Emit `error{code: "conversation_not_found"}` |
| `INTERNAL` | Emit `error{code: "ai_unavailable"}` |
| `UNAVAILABLE` | Emit `error{code: "ai_unavailable"}` |
| Mid-stream error (after ≥1 chunk) | Emit `error{code: "stream_error"}` |

After emitting an `error` message, the gRPC stream is closed but the WebSocket connection remains open.

---

## Connection Pooling

A single `grpc.ClientConn` is created at startup and reused for all streams:

```go
cc, err := grpc.NewClient(
    cfg.AIChatGRPCAddr,
    grpc.WithTransportCredentials(insecure.NewCredentials()), // in-cluster only
    grpc.WithDefaultCallOptions(grpc.WaitForReady(true)),
)
client := estategapv1.NewAIChatServiceClient(cc)
```

`WaitForReady(true)` means streams retry the connection when ai-chat is temporarily unavailable rather than failing immediately. Per-stream deadline is set to 5 minutes (maximum expected conversation turn length).

---

## Sequence Diagram

```
Client          ws-server              ai-chat
  │                │                      │
  │ chat_message   │                      │
  │───────────────►│                      │
  │                │  gRPC Chat stream    │
  │                │─────────────────────►│
  │                │  ChatRequest         │
  │                │─────────────────────►│
  │                │  CloseSend()         │
  │                │                      │ (LLM generates...)
  │                │  ChatResponse chunk  │
  │                │◄─────────────────────│
  │ text_chunk     │                      │
  │◄───────────────│                      │
  │    (× N)       │◄─── (× N) ──────────│
  │◄───────────────│                      │
  │                │  ChatResponse(final) │
  │                │◄─────────────────────│
  │ text_chunk     │                      │
  │  (is_final)    │                      │
  │◄───────────────│                      │
  │ search_results │                      │
  │◄───────────────│                      │
  │                │  stream closed       │
```
