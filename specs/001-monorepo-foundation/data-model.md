# Data Model: Monorepo Foundation

**Branch**: `001-monorepo-foundation` | **Date**: 2026-04-16

> This phase defines the **shared entity contracts** — the Pydantic models and Proto message types that cross service boundaries. No database schema is created in this phase (that belongs to the data-layer feature).

---

## Protobuf Messages

### `common.proto` — Shared Types

| Message | Fields | Notes |
|---------|--------|-------|
| `Timestamp` | `int64 seconds`, `int32 nanos` | Aligned with `google.protobuf.Timestamp`; kept local to avoid well-known type import issues in buf v2 |
| `Money` | `string currency_code` (ISO 4217), `int64 units`, `int32 nanos` | EUR-normalized companion stored separately |
| `GeoPoint` | `double latitude`, `double longitude` | WGS84 |
| `PaginationRequest` | `int32 page_size`, `string page_token` | Standard AIP-158 pattern |
| `PaginationResponse` | `string next_page_token`, `int32 total_size` | |

---

### `listings.proto` — Internal Listing Types

| Message | Fields | Notes |
|---------|--------|-------|
| `Listing` | `string id`, `string external_id`, `string portal`, `string country_code`, `ListingType type`, `ListingStatus status`, `Money price`, `Money price_eur`, `float area_sqm`, `GeoPoint location`, `string zone_id`, `Timestamp created_at`, `Timestamp updated_at` | Canonical internal listing |
| `RawListing` | `string external_id`, `string portal`, `string country_code`, `string raw_json`, `Timestamp scraped_at` | Pre-normalization payload from spiders |
| `PriceHistory` | `string listing_id`, `Money price`, `Money price_eur`, `Timestamp recorded_at` | Append-only audit trail |
| `ListingType` (enum) | `RESIDENTIAL`, `COMMERCIAL`, `INDUSTRIAL`, `LAND` | Constitution-mandated property types |
| `ListingStatus` (enum) | `ACTIVE`, `SOLD`, `WITHDRAWN`, `EXPIRED` | |

---

### `ai_chat.proto` — AI Chat Service

| Element | Type | Details |
|---------|------|---------|
| `AIChatService` | Service | Conversational property search |
| `Chat` | RPC (bidi streaming) | `ChatMessage` stream → `ChatResponse` stream |
| `GetConversation` | RPC (unary) | `GetConversationRequest` → `Conversation` |
| `ListConversations` | RPC (unary) | `ListConversationsRequest` → `ListConversationsResponse` |
| `ChatMessage` | Message | `string conversation_id`, `string content`, `string role` (`user`/`assistant`), `Timestamp sent_at` |
| `ChatResponse` | Message | `string conversation_id`, `string content`, `bool is_final`, `repeated string listing_ids` |
| `Conversation` | Message | `string id`, `string user_id`, `repeated ChatMessage messages`, `Timestamp created_at` |

---

### `ml_scoring.proto` — ML Scoring Service

| Element | Type | Details |
|---------|------|---------|
| `MLScoringService` | Service | Per-country deal scoring |
| `ScoreListing` | RPC (unary) | `ScoreListingRequest` → `ScoringResult` |
| `ScoreBatch` | RPC (server streaming) | `ScoreBatchRequest` → stream of `ScoringResult` |
| `GetComparables` | RPC (unary) | `GetComparablesRequest` → `GetComparablesResponse` |
| `ScoringResult` | Message | `string listing_id`, `float deal_score` (0–1), `repeated ShapValue shap_values`, `string model_version`, `Timestamp scored_at` |
| `ShapValue` | Message | `string feature_name`, `float value` | SHAP explainability (constitution §IV) |
| `GetComparablesResponse` | Message | `repeated Listing comparables`, `PaginationResponse pagination` |

---

### `proxy.proto` — Proxy Manager Service

| Element | Type | Details |
|---------|------|---------|
| `ProxyService` | Service | Geo-targeted proxy pool management |
| `GetProxy` | RPC (unary) | `GetProxyRequest` → `Proxy` |
| `ReportResult` | RPC (unary) | `ReportResultRequest` → `ReportResultResponse` |
| `Proxy` | Message | `string id`, `string host`, `int32 port`, `string country_code`, `string protocol` |
| `GetProxyRequest` | Message | `string country_code`, `string portal` |
| `ReportResultRequest` | Message | `string proxy_id`, `bool success`, `int32 status_code`, `int64 latency_ms` |

---

## Python Pydantic v2 Models (`libs/common/estategap_common/models/`)

### `listing.py`

```python
class Listing(BaseModel):
    id: str
    external_id: str
    portal: str
    country_code: str  # ISO 3166-1 alpha-2
    listing_type: ListingType
    status: ListingStatus
    price: Decimal
    currency_code: str
    price_eur: Decimal
    area_sqm: float
    latitude: float
    longitude: float
    zone_id: str | None = None
    created_at: datetime
    updated_at: datetime

class RawListing(BaseModel):
    external_id: str
    portal: str
    country_code: str
    raw_json: str
    scraped_at: datetime
```

### `zone.py`

```python
class Zone(BaseModel):
    id: str
    name: str
    country_code: str
    geometry_wkt: str  # PostGIS WKT polygon
    parent_zone_id: str | None = None
```

### `alert.py`

```python
class AlertRule(BaseModel):
    id: str
    user_id: str
    country_code: str
    zone_ids: list[str]
    listing_types: list[ListingType]
    max_price_eur: Decimal | None = None
    min_area_sqm: float | None = None
    min_deal_score: float | None = None  # 0.0–1.0
    active: bool = True
    created_at: datetime
```

### `scoring.py`

```python
class ShapValue(BaseModel):
    feature_name: str
    value: float

class ScoringResult(BaseModel):
    listing_id: str
    deal_score: float  # 0.0–1.0
    shap_values: list[ShapValue]
    model_version: str
    country_code: str
    scored_at: datetime
```

### `conversation.py`

```python
class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str
    sent_at: datetime
    listing_ids: list[str] = []

class ConversationState(BaseModel):
    id: str
    user_id: str
    messages: list[ChatMessage] = []
    created_at: datetime
    updated_at: datetime
```

---

## Validation Rules

- `country_code`: must be a valid ISO 3166-1 alpha-2 code (2 uppercase letters).
- `deal_score`: float in range [0.0, 1.0]; outside this range is a data error.
- `price_eur` and `price`: must be ≥ 0.
- `area_sqm`: must be > 0.
- `ChatMessage.role`: only `"user"` or `"assistant"` accepted (Literal type enforced by Pydantic).
- All `datetime` fields use timezone-aware UTC (Pydantic `model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})`).

---

## State Transitions

### `ListingStatus`

```
ACTIVE → SOLD
ACTIVE → WITHDRAWN
ACTIVE → EXPIRED
WITHDRAWN → ACTIVE  (relisting)
```

All transitions recorded in `PriceHistory` when price changes; status changes tracked in a separate `listing_status_history` table (future data-layer phase).
