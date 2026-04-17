# Data Model: WebSocket Chat & Real-Time Notifications

**Branch**: `019-ws-chat-realtime` | **Date**: 2026-04-17

> `ws-server` is a stateless transport layer. It holds no persistent state. All entities below are in-process runtime structures (not persisted to PostgreSQL or Redis by this service).

---

## Runtime Entities

### Connection

Represents a single active WebSocket session for an authenticated user.

| Field | Type | Description |
|---|---|---|
| `userID` | `string` (UUID) | Authenticated user from JWT `sub` claim |
| `tier` | `string` | Subscription tier from JWT (`free`, `basic`, `pro_plus`) |
| `conn` | `*websocket.Conn` | Underlying gorilla/websocket connection handle |
| `send` | `chan []byte` | Outbound message queue (buffered, 256 items) |
| `done` | `chan struct{}` | Closed when this connection is torn down |
| `connectedAt` | `time.Time` | Timestamp of successful upgrade (UTC) |
| `lastActivity` | `time.Time` | Updated on each inbound `chat_message` from client |

**Lifecycle**: Created on successful upgrade. Destroyed on read error, idle timeout, pong timeout, server shutdown, or explicit client close.

**Write safety**: Only the `writePump` goroutine writes to `conn`. All other code sends to the `send` channel.

---

### Hub

Central in-memory registry of all active connections on this pod.

| Field | Type | Description |
|---|---|---|
| `mu` | `sync.RWMutex` | Protects `conns` map |
| `conns` | `map[string][]*Connection` | userID → slice of active connections |
| `maxConns` | `int` | Per-pod connection limit (default 10,000) |

**Operations**:
- `Register(*Connection)` — add connection to user's slice
- `Unregister(*Connection)` — remove connection; prune empty slices
- `Send(userID string, payload []byte)` — fan-out to all connections for this user
- `ConnectionCount() int` — total connections across all users
- `Shutdown()` — graceful close all connections

---

## Message Protocol Types (in-process structs)

All WebSocket messages use a common JSON envelope:

```go
type Envelope struct {
    Type      string          `json:"type"`
    SessionID string          `json:"session_id,omitempty"`
    Payload   json.RawMessage `json:"payload"`
}
```

### Inbound Messages (client → server)

#### `chat_message`
```go
type ChatMessagePayload struct {
    UserMessage  string `json:"user_message"`           // required
    CountryCode  string `json:"country_code,omitempty"` // ISO 3166-1 alpha-2; required on first turn
}
```

#### `image_feedback`
```go
type ImageFeedbackPayload struct {
    ListingID string `json:"listing_id"` // UUID of the listing the user reacted to
    Action    string `json:"action"`     // "like" | "dislike" | "view"
}
```

#### `criteria_confirm`
```go
type CriteriaConfirmPayload struct {
    Confirmed bool   `json:"confirmed"`        // true = proceed to search
    Notes     string `json:"notes,omitempty"`  // optional override note
}
```

---

### Outbound Messages (server → client)

#### `text_chunk`
Streamed token fragment from the LLM.
```go
type TextChunkPayload struct {
    Text           string `json:"text"`                      // token fragment
    ConversationID string `json:"conversation_id"`           // echoed from gRPC response
    IsFinal        bool   `json:"is_final"`                  // true on last chunk of this turn
}
```

#### `chips`
Quick-reply options the user can tap.
```go
type ChipsPayload struct {
    Options []ChipOption `json:"options"`
}

type ChipOption struct {
    Label   string `json:"label"`   // display text
    Value   string `json:"value"`   // value to echo back as chat_message
}
```

#### `image_carousel`
Swipeable property photo deck.
```go
type ImageCarouselPayload struct {
    Listings []CarouselItem `json:"listings"`
}

type CarouselItem struct {
    ListingID string   `json:"listing_id"`
    Title     string   `json:"title"`
    PriceEUR  float64  `json:"price_eur"`
    AreaM2    float64  `json:"area_m2"`
    City      string   `json:"city"`
    PhotoURLs []string `json:"photo_urls"`
    DealScore float64  `json:"deal_score,omitempty"`
}
```

#### `criteria_summary`
Structured card showing the finalised search criteria.
```go
type CriteriaSummaryPayload struct {
    ConversationID string          `json:"conversation_id"`
    Criteria       json.RawMessage `json:"criteria"` // opaque JSON from ai-chat CriteriaState
    ReadyToSearch  bool            `json:"ready_to_search"`
}
```

#### `search_results`
Matching listings after criteria are confirmed.
```go
type SearchResultsPayload struct {
    ConversationID string          `json:"conversation_id"`
    TotalCount     int             `json:"total_count"`
    Listings       []SearchListing `json:"listings"`
}

type SearchListing struct {
    ListingID string  `json:"listing_id"`
    Title     string  `json:"title"`
    PriceEUR  float64 `json:"price_eur"`
    AreaM2    float64 `json:"area_m2"`
    Bedrooms  *int    `json:"bedrooms,omitempty"`
    City      string  `json:"city"`
    DealScore float64 `json:"deal_score"`
    DealTier  int     `json:"deal_tier"`
    ImageURL  string  `json:"image_url,omitempty"`
    AnalysisURL string `json:"analysis_url,omitempty"`
}
```

#### `deal_alert`
Real-time notification pushed from NATS.
```go
type DealAlertPayload struct {
    EventID   string  `json:"event_id"`   // UUID (idempotency key from NotificationEvent)
    ListingID string  `json:"listing_id"`
    Title     string  `json:"title"`
    Address   string  `json:"address"`
    PriceEUR  float64 `json:"price_eur"`
    AreaM2    float64 `json:"area_m2"`
    DealScore float64 `json:"deal_score"`
    DealTier  int     `json:"deal_tier"`
    PhotoURL  string  `json:"photo_url,omitempty"`
    AnalysisURL string `json:"analysis_url,omitempty"`
    RuleName  string  `json:"rule_name"`
    TriggeredAt string `json:"triggered_at"` // RFC3339
}
```

#### `error`
Structured error for client consumption.
```go
type ErrorPayload struct {
    Code    string `json:"code"`    // machine-readable code (see below)
    Message string `json:"message"` // human-readable description
}
```

**Error codes**:

| Code | Trigger |
|---|---|
| `ai_unavailable` | gRPC stream to ai-chat failed or returned INTERNAL |
| `ai_limit_exceeded` | gRPC returned RESOURCE_EXHAUSTED |
| `conversation_not_found` | gRPC returned NOT_FOUND |
| `invalid_message` | Malformed JSON envelope or unknown type |
| `stream_error` | Mid-stream gRPC error after first chunk |
| `server_shutting_down` | Graceful shutdown close notification |

---

## Config

```go
type Config struct {
    Port                 int           // default 8081
    JWTSecret            string        // shared HS256 secret
    RedisAddr            string        // for blacklist check
    AIChatGRPCAddr       string        // default "ai-chat:50053"
    NATSAddr             string        // default "nats:4222"
    MaxConnections       int           // default 10000
    PingInterval         time.Duration // default 30s
    PongTimeout          time.Duration // default 10s
    IdleTimeout          time.Duration // default 30min
    ShutdownTimeout      time.Duration // default 5s
    NATSWorkers          int           // default 4
}
```

---

## State Transitions

```
WebSocket Connection States:

  PENDING ──(JWT valid)──► ACTIVE ──(idle 30min)──► CLOSED
     │                       │
     │(JWT invalid)          ├──(pong timeout)──► CLOSED
     ▼                       │
  REJECTED               ──(SIGTERM)──► DRAINING ──(5s)──► CLOSED
```

```
Chat Stream States (per turn):

  IDLE ──(chat_message recv)──► STREAMING ──(is_final=false × N)──► STREAMING
                                                │
                                         (is_final=true)
                                                │
                                                ▼
                                             IDLE
                                (criteria_summary + search_results sent)
```
