# Data Model: AI Conversational Search Service

**Feature**: 018-ai-chat-service | **Date**: 2026-04-17

---

## Redis Structures

### Conversation State Hash

**Key**: `conv:{session_id}`
**Type**: Redis HASH
**TTL**: 86400 s (24 h), reset on every interaction

| Field | Type | Description |
|-------|------|-------------|
| `user_id` | string (UUID) | Owning user |
| `language` | string | BCP-47 language code detected from conversation (e.g., `"it"`, `"en"`) |
| `criteria_state` | JSON string | Latest `CriteriaState` model serialized to JSON; empty `"{}"` on new conversation |
| `turn_count` | string (int) | Number of completed turns; incremented after each assistant response |
| `created_at` | string (ISO-8601) | First message timestamp |
| `last_active_at` | string (ISO-8601) | Last interaction timestamp; updated every turn |
| `subscription_tier` | string | `"free"` \| `"basic"` \| `"pro_plus"` — copied from request metadata at start |

**Operations**:
- Create: `HSET conv:{id} user_id … created_at … EX 86400`
- Update turn: `HSET conv:{id} criteria_state … last_active_at … turn_count N` + `EXPIRE conv:{id} 86400`
- Read: `HGETALL conv:{id}` (single round-trip)

---

### Message History List

**Key**: `conv:{session_id}:messages`
**Type**: Redis LIST (right-append, left-trim)
**TTL**: 86400 s (same as parent hash; reset together)
**Max length**: 40 messages (sliding window via `LTRIM 0 39` after each `RPUSH`)

**Element schema** (JSON-encoded string):
```json
{
  "role": "user" | "assistant",
  "content": "string",
  "timestamp": "ISO-8601"
}
```

**Operations**:
- Append: `RPUSH conv:{id}:messages <json>` followed by `LTRIM conv:{id}:messages -40 -1`
- Read all: `LRANGE conv:{id}:messages 0 -1` (returns in chronological order)

---

### Daily Conversation Counter

**Key**: `sub:{user_id}:convs:{YYYY-MM-DD}`
**Type**: Redis SORTED SET (score = epoch timestamp, member = session_id)
**TTL**: 90000 s (25 h — covers day boundary with buffer)

**Operations**:
- Record new conversation: `ZADD sub:{uid}:convs:{date} {epoch} {session_id}` + `EXPIRE … 90000`
- Check count: `ZCOUNT sub:{uid}:convs:{date} -inf +inf`

---

## PostgreSQL Table

### `visual_references`

**Purpose**: Curated image library for visual style reference during conversations.

```sql
CREATE TABLE visual_references (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    image_url   TEXT NOT NULL,
    tags        TEXT[] NOT NULL DEFAULT '{}',
    description TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_visual_references_tags ON visual_references USING GIN (tags);
```

**Notes**:
- Not country-partitioned — lookup table independent of property data.
- `tags` indexed with GIN for efficient `@>` containment queries.
- `image_url` points to MinIO/CDN; the service never uploads images, only reads.
- Seed data (200+ images) loaded separately via migration; not managed by this service.

**Runtime query pattern**:
```sql
SELECT id, image_url, description
FROM visual_references
WHERE tags @> ARRAY[$1::text, $2::text]  -- up to 3 tags
LIMIT 5;
```

---

## Pydantic Models (in-process)

### `CriteriaState`

```python
from pydantic import BaseModel, ConfigDict, Field
from typing import Any, Literal

class CriteriaState(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    status: Literal["in_progress", "ready"]
    confidence: float = Field(ge=0.0, le=1.0)
    criteria: dict[str, Any]        # dimension key → value; partial until status=="ready"
    pending_dimensions: list[str]   # e.g. ["price_max", "size_min"]
    suggested_chips: list[str]      # e.g. ["< €300k", "2+ bedrooms", "sea view"]
    show_visual_references: bool
```

**Known criteria dimensions** (10 total):
`location`, `property_type`, `price_range`, `size_range`, `condition`, `style`, `amenities`, `deal_type`, `urgency`, `extras`

---

### `LLMMessage`

```python
from typing import Literal
from pydantic import BaseModel

class LLMMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str
```

Used as the message list passed to `BaseLLMProvider.generate()`. System prompt passed separately as the `system` argument.

---

### `VisualReference`

```python
from uuid import UUID
from pydantic import BaseModel

class VisualReference(BaseModel):
    id: UUID
    image_url: str
    description: str | None
```

Returned from `visual_refs.query_by_tags(tags, pool)` as `list[VisualReference]`.

---

### `MarketData`

```python
from pydantic import BaseModel

class ZoneMarketData(BaseModel):
    zone_id: str
    zone_name: str
    median_price_eur: int
    deal_count: int
    listing_volume: int

class MarketData(BaseModel):
    zones: list[ZoneMarketData]
    fetched_at: str   # ISO-8601
```

Serialized to JSON and injected as the `[MARKET DATA]` block in the LLM message list.

---

## Provider Interface

```python
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator

class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate(
        self,
        messages: list[LLMMessage],
        system: str,
    ) -> AsyncIterator[str]:
        """Yields token strings as they stream from the LLM."""
        ...
```

**Provider registry** (`providers/__init__.py`):
```python
_PROVIDERS: dict[str, type[BaseLLMProvider]] = {
    "claude": ClaudeProvider,
    "openai": OpenAIProvider,
    "litellm": LiteLLMProvider,
}

def get_provider(name: str, config: Config) -> BaseLLMProvider:
    cls = _PROVIDERS.get(name)
    if cls is None:
        raise ValueError(f"Unknown LLM provider: {name!r}")
    return cls(config)
```

---

## Entity Relationships

```
User (from estategap_common.models.user)
 └── has Subscription (tier: Free | Basic | Pro+)
      └── constrains ConversationSession (daily count, turn count)

ConversationSession (Redis)
 ├── has CriteriaState (Redis hash field — JSON)
 └── has [LLMMessage] (Redis list — up to 40)

CriteriaState
 └── triggers VisualReference query (when show_visual_references=True)
 └── drives Finalization (when status="ready" + user confirms)

Finalization
 ├── calls api-gateway SearchListings (gRPC)
 └── calls api-gateway CreateAlertRule (gRPC)
```
