# Research: AI Conversational Search Service

**Feature**: 018-ai-chat-service | **Date**: 2026-04-17

All decisions are grounded in findings from the existing codebase (`services/ml/`, `libs/common/`, `proto/`) plus the user's explicit technical decisions in the plan input.

---

## D-001: Proto Contract

**Decision**: Use `proto/estategap/v1/ai_chat.proto` as-is — no schema changes required.

**Rationale**: The proto file is already complete with `AIChatService` defining `Chat` (bidirectional streaming), `GetConversation`, and `ListConversations`. Generated Python stubs already exist at `libs/common/proto/estategap/v1/ai_chat_pb2_grpc.py`. The `ChatRequest` message carries `conversation_id`, `user_message`, and `country_code`; `ChatResponse` carries `conversation_id`, `chunk`, `is_final`, and `listing_ids` — sufficient for streaming tokens and finalization results.

**Alternatives considered**:
- Add a `visual_references` field to `ChatResponse` — rejected; visual references are communicated as structured JSON within the `chunk` field to keep streaming uniform.
- Create a new proto — rejected; existing proto covers all required RPCs.

---

## D-002: Conversation State Storage Layout

**Decision**: Redis hash `conv:{session_id}` for mutable scalar state; Redis list `conv:{session_id}:messages` for ordered message history. TTL 24 h reset on each interaction. Sliding window: keep last 40 messages (lpush + ltrim).

**Rationale**: Hash semantics allow atomic field updates (e.g., increment `turn_count`, update `criteria_state`) without reading the whole document. List semantics with `RPUSH` / `LTRIM` implement a natural sliding window. Both structures share the same Redis keyspace and TTL can be reset atomically via `EXPIRE`.

**Key layout**:
```
conv:{session_id}         HASH
  user_id                 string (UUID)
  language                string (e.g., "it", "en")
  criteria_state          JSON string (CriteriaState model)
  turn_count              integer string
  created_at              ISO-8601 string
  last_active_at          ISO-8601 string (updated every turn)

conv:{session_id}:messages  LIST (newest at tail)
  [0..N]                  JSON-encoded ChatMessage (role, content, timestamp)
```

**Alternatives considered**:
- Single JSON blob in a Redis string — rejected; concurrent field updates require optimistic locking (WATCH/MULTI); hash is atomic per-field.
- PostgreSQL for state — rejected; Redis is the designated session store per constitution; DB would add latency and write amplification.

---

## D-003: LLM Provider Abstraction

**Decision**: `BaseLLMProvider` ABC with `async def generate(messages, system) → AsyncIterator[str]`. Three concrete implementations selected by `LLM_PROVIDER` env var. Fallback triggered only on `asyncio.TimeoutError`, `RateLimitError`, and `APIConnectionError` — auth errors are not retried.

**Provider details**:
| Provider | Class | Model | SDK |
|----------|-------|-------|-----|
| claude | `ClaudeProvider` | `claude-sonnet-4-20250514` | `anthropic.AsyncAnthropic` |
| openai | `OpenAIProvider` | `gpt-4o` | `openai.AsyncOpenAI` |
| litellm | `LiteLLMProvider` | `$LITELLM_MODEL` env | `litellm.acompletion` |

**Factory pattern**: `providers/__init__.py` exposes `get_provider(name: str) → BaseLLMProvider` using a dict lookup — avoids conditional chains in servicer.

**Fallback**: `servicer.py` wraps the primary `generate()` call; on retryable error, instantiates `get_provider(config.fallback_llm_provider)` and retries once. No circuit breaker in v1 — acceptable given K8s restarts as the outer recovery mechanism.

**Alternatives considered**:
- LiteLLM as the single abstraction for all providers — rejected; direct SDKs give better streaming control and type safety for the primary Claude use case; LiteLLM is kept as the self-hosted escape hatch.
- OpenTelemetry spans per provider call — deferred to observability epic.

---

## D-004: System Prompt Design

**Decision**: Jinja2 template at `prompts/system_prompt.jinja2`. Rendered once per conversation turn with a `PromptContext` dataclass carrying `language`, `countries`, `property_types`, `active_zones`, and `market_data`. Output format instruction mandates a fenced ` ```json ` block at the end of every response.

**Template context variables**:
```python
@dataclass
class PromptContext:
    language: str           # e.g. "it"
    countries: list[str]    # from api-gateway taxonomy
    property_types: list[str]
    active_zones: list[dict]  # [{id, name, country}]
    market_data: dict | None  # None if fetch failed
```

**Output format instruction** (embedded in template):
> Always end your response with a JSON block in this exact format:
> ```json
> {
>   "status": "in_progress" | "ready",
>   "confidence": 0.0–1.0,
>   "criteria": { ... },
>   "pending_dimensions": [...],
>   "suggested_chips": [...],
>   "show_visual_references": true | false
> }
> ```

**Alternatives considered**:
- Hard-coded f-string prompt — rejected; Jinja2 makes iteration easier and keeps logic out of Python code.
- Separate prompts per language — rejected; the LLM handles multilingual output via the `language` instruction.

---

## D-005: Criteria State Parser

**Decision**: `parser.py` extracts the last ` ```json ` ... ` ``` ` block from LLM text via regex, parses with `json.loads`, validates against `CriteriaState` Pydantic model. On parse failure: re-send one retry message ("Please include the JSON criteria block"). If second attempt also fails: return `chunk` text response with `criteria_state` unchanged (last known state).

**`CriteriaState` model** (Pydantic v2):
```python
class CriteriaState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["in_progress", "ready"]
    confidence: float = Field(ge=0.0, le=1.0)
    criteria: dict[str, Any]         # dimension → value
    pending_dimensions: list[str]
    suggested_chips: list[str]
    show_visual_references: bool
```

**Retry signal**: a `ParseError` exception propagates to `servicer.py`, which injects a system-level retry message into the LLM call (not exposed to the user as a turn).

**Alternatives considered**:
- JSONSchema validation instead of Pydantic — rejected; Pydantic v2 gives better error messages and is the project standard.
- Always fail hard on parse error — rejected; graceful degradation (return last known state) prevents conversation termination from a single malformed response.

---

## D-006: Visual References

**Decision**: PostgreSQL table `visual_references (id UUID, image_url TEXT, tags TEXT[], description TEXT)`. Query: `WHERE tags @> ARRAY[...] LIMIT 5` (containment operator). Triggered when `CriteriaState.show_visual_references == True`. Returns list of `{id, image_url, description}` objects serialized as JSON within the `ChatResponse.chunk`.

**Tag extraction**: tags from `criteria.style` and `criteria.features` fields in `CriteriaState.criteria` dict. Lowercased and split on comma/space. Max 3 tags per query to avoid over-constraining.

**Alternatives considered**:
- Store images in MinIO, serve URLs from DB — accepted as-is (image_url IS the MinIO/CDN URL; the DB stores the pointer).
- Full-text search on description — rejected for v1; tag-based containment is simpler and sufficient.
- Trigger on keyword detection in raw user message — rejected; delegating detection to the LLM (via `show_visual_references` flag) is more accurate.

---

## D-007: Subscription Tier Enforcement

**Decision**: In-process enforcement in `subscription.py`. Daily conversation count stored in Redis sorted set `sub:{user_id}:convs:{YYYY-MM-DD}` (ZADD with session_id, ZCOUNT for limit check, TTL 25 h). Turn count read from `conv:{session_id}:turn_count` hash field.

**Tier limits**:
| Tier | Conv/day | Turns/conv |
|------|----------|------------|
| Free | 3 | 10 |
| Basic | 10 | 20 |
| Pro+ | ∞ | ∞ |

**Enforcement points**:
1. On `Chat` RPC call with `turn_count == 0` (new conversation): check daily conv count → abort with `RESOURCE_EXHAUSTED` gRPC status.
2. On each turn: check `turn_count >= tier_limit` → abort with `RESOURCE_EXHAUSTED` + graceful message.

**Subscription tier source**: `user_id` looked up via `SubscriptionTier` in `estategap_common.models.user`. In v1, tier is passed as metadata in the gRPC request (set by api-gateway after JWT validation) — no DB lookup in the AI service.

**Alternatives considered**:
- Enforce at api-gateway — deferred; api-gateway doesn't have visibility into per-conversation turn counts; enforcement closer to the resource is more accurate.
- PostgreSQL for daily counts — rejected; Redis is faster and already used for session state.

---

## D-008: Market Context Injection

**Decision**: `market_context.py` creates a gRPC channel to api-gateway on service startup (reused per-request). Calls a `GetZoneMarketData(zone_ids)` unary RPC. Timeout: 500 ms. On timeout or error: returns `None` and the servicer injects an empty `[MARKET DATA]` block (conversation proceeds without market context rather than failing).

**Injected as**: A `[MARKET DATA]` pseudo-message inserted immediately before the user's latest message in the LLM messages list (not stored in Redis history — ephemeral per turn).

**Alternatives considered**:
- Cache market context in Redis with short TTL — deferred to v2; cache invalidation complexity not justified for v1.
- Fetch market context in the system prompt — rejected; prompt is rendered once; market context is per-turn and must reflect the current zone.

---

## D-009: Finalization Flow

**Decision**: When `CriteriaState.status == "ready"` and the incoming user message confirms (detected via simple keyword match: "yes", "search", "go", "ok", "confirm", "trova"), `finalization.py` runs:

1. `criteria_to_search_params(criteria: dict) → ListingsSearchRequest` — maps dimension keys to proto fields.
2. gRPC call `api-gateway.SearchListings(request)` → returns listing IDs + summary.
3. gRPC call `api-gateway.CreateAlertRule(request)` — derived from same criteria.
4. Stream results back as final `ChatResponse` chunks (listing summaries + alert confirmation).

**Confirmation detection**: keyword-based for v1. LLM-based intent detection deferred to v2.

**Alternatives considered**:
- Ask LLM to confirm intent — adds latency and an extra LLM call; keyword match is sufficient for v1.
- Return finalization as a separate RPC — rejected; keeping it in the streaming Chat RPC is simpler and keeps the client state machine flat.

---

## D-010: Service Wiring Pattern

**Decision**: Follow `services/ml/estategap_ml/scorer/` exactly:
- `config.py`: `Config(BaseSettings)` with `SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")`.
- `__main__.py`: create asyncpg pool, Redis client, LLM providers; call `serve(config, db_pool, redis_client, llm_provider)`.
- `server.py`: `grpc.aio.server()`, register servicer, bind `[::]:{config.grpc_port}` (default 50053), start Prometheus HTTP server on `config.metrics_port` (default 9090), `await server.wait_for_termination()`.
- `servicer.py`: constructor takes `config, db_pool, redis_client, llm_provider`; each method is `async def`; errors use `await context.abort(grpc.StatusCode.X, msg)`.

**`pyproject.toml` dependency additions** over the existing stub:
```toml
"grpcio>=1.63",
"grpcio-tools>=1.63",
"anthropic>=0.25",
"openai>=1.30",
"jinja2>=3.1",
"asyncpg>=0.29",
"redis[asyncio]>=5.0",
"prometheus-client>=0.20",
"pydantic-settings>=2.2",
"structlog>=24.1",
```
Remove: `fastapi`, `uvicorn` (not needed; Prometheus HTTP server used for health/metrics).
