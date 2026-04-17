# gRPC Contract: AIChatService

**Feature**: 018-ai-chat-service | **Date**: 2026-04-17
**Proto source**: `proto/estategap/v1/ai_chat.proto`
**Generated Python stubs**: `libs/common/proto/estategap/v1/ai_chat_pb2{,_grpc}.py`

---

## Service Definition

```protobuf
service AIChatService {
  // Bidirectional streaming: client sends user turns, server streams tokens back.
  rpc Chat(stream ChatRequest) returns (stream ChatResponse);

  // Unary: retrieve full conversation state and history.
  rpc GetConversation(GetConversationRequest) returns (GetConversationResponse);

  // Unary: list conversations for a user (paginated).
  rpc ListConversations(ListConversationsRequest) returns (ListConversationsResponse);
}
```

**gRPC port**: `50053` (configurable via `GRPC_PORT` env var)

---

## Chat RPC (bidirectional streaming)

### `ChatRequest` (client → server)

| Field | Type | Description |
|-------|------|-------------|
| `conversation_id` | `string` | UUID of the conversation; empty string to start a new conversation |
| `user_message` | `string` | The user's natural-language message |
| `country_code` | `string` | ISO 3166-1 alpha-2 (e.g., `"IT"`, `"FR"`); required on first turn |

**gRPC metadata (set by api-gateway)**:
| Key | Value |
|-----|-------|
| `x-user-id` | Authenticated user UUID |
| `x-subscription-tier` | `"free"` \| `"basic"` \| `"pro_plus"` |

### `ChatResponse` (server → client, streamed)

| Field | Type | Description |
|-------|------|-------------|
| `conversation_id` | `string` | UUID of the conversation (echoed on every chunk) |
| `chunk` | `string` | A single streamed token or a JSON payload (see below) |
| `is_final` | `bool` | `true` on the last message of a turn; `false` for intermediate tokens |
| `listing_ids` | `repeated string` | Populated only on the finalization response |

### Streaming Protocol

```
Client → Server: ChatRequest{conversation_id="", user_message="...", country_code="IT"}
Server → Client: ChatResponse{chunk="Ciao! ", is_final=false}
Server → Client: ChatResponse{chunk="Che tipo di ", is_final=false}
Server → Client: ChatResponse{chunk="proprietà cerchi?", is_final=false}
Server → Client: ChatResponse{chunk="\n```json\n{...criteria json...}\n```", is_final=false}
Server → Client: ChatResponse{chunk="", is_final=true, conversation_id="<uuid>"}

# On criteria ready + user confirms:
Server → Client: ChatResponse{chunk="<listing summaries JSON>", is_final=false}
Server → Client: ChatResponse{chunk="<alert confirmation JSON>", is_final=false}
Server → Client: ChatResponse{chunk="", is_final=true, listing_ids=["id1","id2",...]}
```

**Special chunk payloads** (JSON-encoded, sent as `chunk` before the `is_final=true` marker):
- **Criteria block**: ` ```json\n{CriteriaState}\n``` ` — always present on `is_final=false` before final
- **Visual references** (when `show_visual_references=true`): JSON array of `{id, image_url, description}` objects embedded in an ` ```json ` block
- **Finalization results**: listing summaries and alert confirmation sent as a JSON chunk

### Error Codes

| gRPC Status | Condition |
|-------------|-----------|
| `RESOURCE_EXHAUSTED` | Subscription limit exceeded (daily conv count or turn count) |
| `NOT_FOUND` | `conversation_id` not found in Redis |
| `UNAUTHENTICATED` | Missing or invalid `x-user-id` metadata |
| `INTERNAL` | Both primary and fallback LLM providers failed |
| `DEADLINE_EXCEEDED` | Used internally for market context fetch; not propagated to client |

---

## GetConversation RPC (unary)

### `GetConversationRequest`

| Field | Type | Description |
|-------|------|-------------|
| `conversation_id` | `string` | UUID of the conversation to retrieve |

### `GetConversationResponse`

| Field | Type | Description |
|-------|------|-------------|
| `conversation_id` | `string` | UUID |
| `turns` | `repeated ConversationTurn` | Full message history in chronological order |
| `criteria_state` | `string` | Latest `CriteriaState` as JSON string |
| `turn_count` | `int32` | Total turns completed |
| `language` | `string` | Detected language code |

### `ConversationTurn`

| Field | Type | Description |
|-------|------|-------------|
| `role` | `string` | `"user"` or `"assistant"` |
| `content` | `string` | Message text |
| `timestamp` | `Timestamp` | When the message was created |

---

## ListConversations RPC (unary)

### `ListConversationsRequest`

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | `string` | UUID of the user |
| `pagination` | `PaginationRequest` | `page_size` (default 20) + `page_token` |

### `ListConversationsResponse`

| Field | Type | Description |
|-------|------|-------------|
| `conversations` | `repeated ConversationSummary` | List of conversation summaries |
| `pagination` | `PaginationResponse` | `next_page_token`, `total_count` |

### `ConversationSummary`

| Field | Type | Description |
|-------|------|-------------|
| `conversation_id` | `string` | UUID |
| `created_at` | `Timestamp` | Start time |
| `last_active_at` | `Timestamp` | Last interaction time |
| `turn_count` | `int32` | Number of completed turns |
| `criteria_status` | `string` | `"in_progress"` or `"ready"` |

---

## Downstream gRPC Dependencies

The `ai-chat` service calls these existing api-gateway RPCs:

### Market Context (called before each LLM turn)

```
api-gateway:50051  →  GetZoneMarketData(zone_ids: repeated string)
                   ←  ZoneMarketDataResponse(zones: repeated ZoneMarketData)
```
Timeout: 500 ms. On failure: proceeds without market data.

### Finalization — Listing Search

```
api-gateway:50051  →  SearchListings(ListingsSearchRequest)
                   ←  ListingsSearchResponse(listing_ids, summaries)
```

### Finalization — Alert Creation

```
api-gateway:50051  →  CreateAlertRule(AlertRuleRequest)
                   ←  AlertRuleResponse(alert_rule_id)
```
