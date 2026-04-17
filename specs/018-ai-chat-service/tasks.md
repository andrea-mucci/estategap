# Tasks: AI Conversational Search Service

**Input**: Design documents from `specs/018-ai-chat-service/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/grpc.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US4)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Get the existing `services/ai-chat/` stub ready for implementation by updating dependencies, Dockerfile, and env configuration.

- [X] T001 Update `services/ai-chat/pyproject.toml`: remove `fastapi`, `uvicorn`; add `grpcio>=1.63`, `grpcio-tools>=1.63`, `anthropic>=0.25`, `openai>=1.30`, `jinja2>=3.1`, `asyncpg>=0.29`, `redis[asyncio]>=5.0`, `prometheus-client>=0.20`, `pydantic-settings>=2.2`, `structlog>=24.1`
- [X] T002 [P] Update `services/ai-chat/Dockerfile`: change `CMD` to `["python", "-m", "estategap_ai_chat"]`; ensure `libs/common` is copied before service dir in multi-stage build
- [X] T003 [P] Update `services/ai-chat/.env.example` with all required vars: `GRPC_PORT`, `METRICS_PORT`, `LLM_PROVIDER`, `FALLBACK_LLM_PROVIDER`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `LITELLM_MODEL`, `REDIS_URL`, `DATABASE_URL`, `API_GATEWAY_GRPC_ADDR`, `LOG_LEVEL`
- [X] T004 [P] Add `ruff` and `mypy` config to `services/ai-chat/pyproject.toml` (`[tool.ruff]`, `[tool.mypy]` strict sections matching `services/ml/` pattern)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core wiring that every user story depends on — config, gRPC server lifecycle, metrics, test fixtures.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Implement `services/ai-chat/estategap_ai_chat/config.py`: `class Config(BaseSettings)` with `SettingsConfigDict(env_file=".env", case_sensitive=False, extra="ignore")`; fields: `grpc_port=50053`, `metrics_port=9090`, `llm_provider`, `fallback_llm_provider`, `anthropic_api_key`, `openai_api_key`, `litellm_model`, `redis_url`, `database_url`, `api_gateway_grpc_addr`, `log_level`
- [X] T006 Implement `services/ai-chat/estategap_ai_chat/metrics.py`: define `Prometheus` counters and histograms: `ai_chat_conversations_total` (labels: tier), `ai_chat_turns_total` (labels: provider), `ai_chat_llm_latency_seconds` histogram (labels: provider), `ai_chat_criteria_parse_errors_total`, `ai_chat_fallback_activations_total`, `ai_chat_subscription_rejections_total`; expose `start_metrics_server(port)` using `prometheus_client.start_http_server`
- [X] T007 Implement `services/ai-chat/estategap_ai_chat/server.py`: `async def serve(config, db_pool, redis_client, llm_provider, fallback_provider)` — creates `grpc.aio.server()`, calls `add_AIChatServiceServicer_to_server`, binds `[::]:{config.grpc_port}`, starts metrics server, calls `await server.wait_for_termination()`
- [X] T008 Implement `services/ai-chat/estategap_ai_chat/__main__.py`: `async def main()` — configure structlog via `estategap_common.logging.configure_logging`, create asyncpg pool via `estategap_common.db.create_pool`, create `redis.asyncio.from_url` client, instantiate LLM providers from config, call `server.serve()`; wire `asyncio.run(main())` in `services/ai-chat/main.py`
- [X] T009 Implement `services/ai-chat/tests/conftest.py`: pytest fixtures for `redis_client` (fakeredis or testcontainers), `db_pool` (asyncpg testcontainers PostgreSQL), `config` (test Config with overrides), `fake_llm_provider` (returns fixed token stream)

**Checkpoint**: `python -m estategap_ai_chat` starts, binds port 50053, exposes metrics on 9090 — no RPCs implemented yet.

---

## Phase 3: User Story 1 — Progressive Property Search (Priority: P1) 🎯 MVP

**Goal**: Full conversation loop — user sends a message, LLM responds with streaming tokens and a criteria JSON block, state is persisted in Redis, market context is injected, and on confirmed criteria the service executes search + alert creation.

**Independent Test**: Run `tests/acceptance/test_conversation_flow.py` against a real Redis + fake LLM provider — a 3-turn conversation starting from a vague input produces a `CriteriaState` with ≥1 populated dimension and a non-empty `pending_dimensions` list.

### Implementation for User Story 1

- [X] T010 [P] [US1] Implement `services/ai-chat/estategap_ai_chat/providers/base.py`: `LLMMessage` dataclass (`role`, `content`); `BaseLLMProvider` ABC with `async def generate(messages: list[LLMMessage], system: str) -> AsyncIterator[str]`
- [X] T011 [P] [US1] Implement `services/ai-chat/estategap_ai_chat/prompts/system_prompt.jinja2`: Jinja2 template with sections for role definition, language instruction, available data JSON block (`countries`, `property_types`, `active_zones`), progressive refinement flow (10 dimensions, 1 question/turn), and required JSON output format block (`status`, `confidence`, `criteria`, `pending_dimensions`, `suggested_chips`, `show_visual_references`)
- [X] T012 [P] [US1] Implement `services/ai-chat/estategap_ai_chat/prompts/__init__.py`: `PromptContext` dataclass (`language`, `countries`, `property_types`, `active_zones`, `market_data`); `render_system_prompt(context: PromptContext) -> str` loading template via `importlib.resources`
- [X] T013 [US1] Implement `services/ai-chat/estategap_ai_chat/providers/claude.py`: `ClaudeProvider(BaseLLMProvider)` using `anthropic.AsyncAnthropic`; `model="claude-sonnet-4-20250514"`, `max_tokens=1000`, `stream=True`; iterate `async with client.messages.stream(...)` yielding text deltas (depends on T010)
- [X] T014 [US1] Implement `services/ai-chat/estategap_ai_chat/session.py`: `ConversationSession` class wrapping redis client; methods: `create(session_id, user_id, language, tier)` → HSET + EXPIRE; `get(session_id)` → HGETALL; `update_criteria(session_id, criteria_json)` → HSET + EXPIRE; `increment_turn(session_id)` → HINCRBY + EXPIRE; `append_message(session_id, role, content)` → RPUSH + LTRIM -40 -1 + EXPIRE; `get_messages(session_id)` → LRANGE 0 -1 returning `list[LLMMessage]`; `exists(session_id)` → EXISTS (depends on T005)
- [X] T015 [US1] Implement `services/ai-chat/estategap_ai_chat/parser.py`: `CriteriaState` Pydantic model (`status`, `confidence`, `criteria`, `pending_dimensions`, `suggested_chips`, `show_visual_references`); `extract_criteria(text: str) -> CriteriaState | None` using regex to find last ` ```json ... ``` ` block, parse with `json.loads`, validate with Pydantic; `ParseError` exception class (depends on T010)
- [X] T016 [US1] Implement `services/ai-chat/estategap_ai_chat/market_context.py`: `MarketContextClient` wrapping gRPC stub to `config.api_gateway_grpc_addr`; `async def fetch(zone_ids: list[str]) -> MarketData | None` with 500 ms deadline; returns `None` on `grpc.aio.AioRpcError` or `asyncio.TimeoutError` (depends on T005)
- [X] T017 [US1] Implement `services/ai-chat/estategap_ai_chat/finalization.py`: `CriteriaFinalizer`; `criteria_to_search_params(criteria: dict) -> dict` mapping dimension keys to listing search proto fields; `async def finalize(session_id, criteria, gateway_stub) -> tuple[list[str], str]` — calls `SearchListings`, then `CreateAlertRule`, returns `(listing_ids, alert_rule_id)` (depends on T015)
- [X] T018 [US1] Implement `services/ai-chat/estategap_ai_chat/servicer.py`: `AIChatServicer(AIChatServiceServicer)` constructor taking `config, db_pool, redis_client, llm_provider, fallback_provider`; implement `Chat` streaming RPC — read metadata (`x-user-id`, `x-subscription-tier`), load/create session via `ConversationSession`, fetch market context, render system prompt, build LLM message list, stream tokens from provider, on `is_final` extract criteria via parser (retry once on `ParseError`), update session state, check `show_visual_references` flag, check `status=="ready"` + confirmation for finalization; stream `ChatResponse` chunks throughout (depends on T010–T017)
- [X] T019 [US1] Implement `services/ai-chat/tests/unit/test_parser.py`: test `extract_criteria` with valid JSON block, malformed JSON, missing JSON block, JSON failing Pydantic validation, multiple JSON blocks (should use last)
- [X] T020 [US1] Implement `services/ai-chat/tests/integration/test_session.py`: test `ConversationSession` create/get/update/append/sliding-window using `redis_client` fixture from conftest; verify TTL is reset on update; verify list is trimmed to 40 entries
- [X] T021 [US1] Implement `services/ai-chat/tests/acceptance/test_conversation_flow.py`: 3-turn conversation using `fake_llm_provider` + real Redis; assert: session created in Redis, turn_count incremented, criteria_state updated each turn, final `is_final=True` chunk received per turn

**Checkpoint**: Full conversation loop works end-to-end. `grpcurl` can send a message and receive streaming tokens + criteria JSON. Session persists in Redis.

---

## Phase 4: User Story 2 — Visual Style Exploration (Priority: P2)

**Goal**: When the LLM sets `show_visual_references=true` in the criteria block, the service queries PostgreSQL for matching images and returns them in the same streaming response.

**Independent Test**: Send a message containing "modern loft" → `fake_llm_provider` returns criteria with `show_visual_references=true` and `criteria.style="modern loft"` → response includes a JSON chunk with 1–5 `VisualReference` objects.

### Implementation for User Story 2

- [X] T022 [P] [US2] Create Alembic migration `libs/common/alembic/versions/XXXX_add_visual_references_table.py`: `CREATE TABLE visual_references (id UUID PK, image_url TEXT NOT NULL, tags TEXT[] NOT NULL DEFAULT '{}', description TEXT, created_at TIMESTAMPTZ DEFAULT now()); CREATE INDEX idx_visual_references_tags ON visual_references USING GIN (tags)`
- [X] T023 [US2] Implement `services/ai-chat/estategap_ai_chat/visual_refs.py`: `VisualReference` Pydantic model (`id`, `image_url`, `description`); `async def query_by_tags(tags: list[str], pool) -> list[VisualReference]` — extracts up to 3 tags from input, runs `SELECT id, image_url, description FROM visual_references WHERE tags @> $1::text[] LIMIT 5`, returns empty list on no match or DB error (depends on T009)
- [X] T024 [US2] Update `services/ai-chat/estategap_ai_chat/servicer.py`: after criteria extraction, if `criteria_state.show_visual_references is True`, call `visual_refs.query_by_tags(tags, db_pool)`, serialize result to JSON and yield as a `ChatResponse` chunk before the `is_final=True` chunk (depends on T018, T023)
- [X] T025 [US2] Implement `services/ai-chat/tests/integration/test_visual_refs.py`: seed `visual_references` with 3 tagged rows; assert `query_by_tags(["modern"])` returns ≤5 rows; assert `query_by_tags(["nonexistent"])` returns empty list

**Checkpoint**: Conversations mentioning style keywords receive visual reference image chunks in the streaming response.

---

## Phase 5: User Story 3 — Subscription-Gated Usage Limits (Priority: P3)

**Goal**: Free-tier users are limited to 3 conversations/day and 10 turns/conversation; Basic 10/day and 20 turns; Pro+ is unlimited. Violations return `RESOURCE_EXHAUSTED` gRPC status.

**Independent Test**: Using `subscription.py` fixtures: simulate a Free-tier user making a 4th conversation attempt → `RESOURCE_EXHAUSTED`; simulate a Free-tier user on turn 11 → `RESOURCE_EXHAUSTED`. Pro+ user: unlimited calls succeed.

### Implementation for User Story 3

- [X] T026 [P] [US3] Implement `services/ai-chat/estategap_ai_chat/subscription.py`: `TIER_LIMITS = {free: (3,10), basic: (10,20), pro_plus: (None,None)}`; `async def check_conversation_limit(user_id, tier, redis_client) -> None` — ZADD + ZCOUNT on `sub:{user_id}:convs:{date}` key (TTL 90000 s); raises `LimitExceededError` if over daily cap; `async def check_turn_limit(turn_count, tier) -> None` — raises `LimitExceededError` if over per-conv cap (depends on T005)
- [X] T027 [US3] Update `services/ai-chat/estategap_ai_chat/servicer.py` `Chat` RPC: on new conversation (`turn_count == 0`) call `check_conversation_limit`; on every turn call `check_turn_limit`; catch `LimitExceededError` and `await context.abort(grpc.StatusCode.RESOURCE_EXHAUSTED, msg)` (depends on T018, T026)
- [X] T028 [US3] Implement `services/ai-chat/tests/unit/test_subscription.py`: test all tier limit combinations — Free at/over daily cap, Free at/over turn cap, Basic at/over limits, Pro+ never limited; use `redis_client` fixture

**Checkpoint**: Subscription enforcement works independently. Free-tier users hitting limits receive `RESOURCE_EXHAUSTED`. Pro+ users are never blocked.

---

## Phase 6: User Story 4 — Multi-Provider LLM Resilience (Priority: P4)

**Goal**: When the primary LLM provider raises a retryable error (timeout, rate limit, connection error), the service transparently retries using the configured fallback provider. Both primary and fallback failing returns a user-friendly `INTERNAL` error.

**Independent Test**: Inject `asyncio.TimeoutError` from `ClaudeProvider.generate()` → assert the response is served from `OpenAIProvider` (fallback) without error; inject errors in both providers → assert `INTERNAL` gRPC status with conversation state preserved.

### Implementation for User Story 4

- [X] T029 [P] [US4] Implement `services/ai-chat/estategap_ai_chat/providers/openai.py`: `OpenAIProvider(BaseLLMProvider)` using `openai.AsyncOpenAI`; `model="gpt-4o"`, `stream=True`; iterate `async for chunk in await client.chat.completions.create(stream=True, ...)` yielding `chunk.choices[0].delta.content` (depends on T010)
- [X] T030 [P] [US4] Implement `services/ai-chat/estategap_ai_chat/providers/litellm.py`: `LiteLLMProvider(BaseLLMProvider)` using `litellm.acompletion`; model from `config.litellm_model`; `stream=True`; iterate streaming chunks yielding `chunk.choices[0].delta.content` (depends on T010)
- [X] T031 [US4] Implement `services/ai-chat/estategap_ai_chat/providers/__init__.py`: `_REGISTRY = {"claude": ClaudeProvider, "openai": OpenAIProvider, "litellm": LiteLLMProvider}`; `get_provider(name, config) -> BaseLLMProvider`; `RETRYABLE_ERRORS = (asyncio.TimeoutError, openai.RateLimitError, openai.APIConnectionError, anthropic.RateLimitError, anthropic.APIConnectionError)` (depends on T013, T029, T030)
- [X] T032 [US4] Update `services/ai-chat/estategap_ai_chat/servicer.py` `Chat` RPC: wrap `llm_provider.generate()` in try/except for `RETRYABLE_ERRORS`; on catch, increment `ai_chat_fallback_activations_total`, retry with `fallback_provider.generate()`; if fallback also fails, `await context.abort(grpc.StatusCode.INTERNAL, "LLM unavailable")` — conversation state is NOT modified on failure (depends on T018, T031)
- [X] T033 [US4] Implement `services/ai-chat/tests/unit/test_providers.py`: test `get_provider()` factory for all three names; test fallback logic with `ErrorProvider` (raises `asyncio.TimeoutError`) as primary and `FakeLLMProvider` as fallback; test dual-failure path returns `INTERNAL`

**Checkpoint**: Primary provider failure is transparent to users. Both-provider failure surfaces a clean error. Conversation state is never corrupted by provider errors.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Secondary RPCs, observability completeness, Helm wiring, and final acceptance validation.

- [X] T034 [P] Implement `GetConversation` and `ListConversations` RPCs in `services/ai-chat/estategap_ai_chat/servicer.py`: `GetConversation` → `session.get()` + `session.get_messages()`; `ListConversations` → SCAN Redis keys `conv:{user_id}:*` with pagination (depends on T018)
- [X] T035 [P] Add `ai-chat` service block to `helm/estategap/values.yaml`: image, port 50053, env var references to Kubernetes Sealed Secrets for `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`; liveness probe on metrics port
- [X] T036 [P] Add `services/ai-chat` smoke test to CI: `uv run pytest services/ai-chat/tests/unit/ -v` in `.github/workflows/` or equivalent CI config
- [X] T037 Run `quickstart.md` validation end-to-end: start service with `LLM_PROVIDER=claude` (or mock), send `grpcurl` test conversation, confirm streaming tokens and criteria JSON block received; document any deviations in `quickstart.md`
- [X] T038 [P] Run `ruff check` and `mypy --strict` on `services/ai-chat/estategap_ai_chat/`; fix all reported issues

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately; T002–T004 run in parallel with T001
- **Foundational (Phase 2)**: Depends on Phase 1 completion — **blocks all user stories**
- **User Story phases (3–6)**: All depend on Phase 2 completion; can proceed in parallel if staffed
- **Polish (Phase 7)**: Depends on all desired user stories being complete

### User Story Dependencies

- **US1 (P1)**: Starts after Phase 2. No dependency on US2–US4. Delivers standalone value.
- **US2 (P2)**: Starts after Phase 2. Extends US1's servicer (T024 depends on T018); independently testable via `test_visual_refs.py`.
- **US3 (P3)**: Starts after Phase 2. Extends US1's servicer (T027 depends on T018); independently testable via `test_subscription.py`.
- **US4 (P4)**: Starts after Phase 2. Extends US1's servicer (T032 depends on T018); OpenAIProvider (T029) and LiteLLMProvider (T030) are parallel to each other.

### Within Each User Story

- Providers/base (T010) and prompt template (T011–T012) before servicer (T018)
- Session store (T014) before servicer (T018)
- Parser (T015) before servicer (T018) and finalization (T017)
- Market context (T016) before servicer (T018)

### Parallel Opportunities

Within Phase 3 (US1), these can run simultaneously:
- T010 (providers/base.py) + T011 (system_prompt.jinja2) + T012 (prompts/__init__.py)
- T013 (claude.py) — starts after T010
- T014 (session.py) + T015 (parser.py) + T016 (market_context.py) — all after T005, parallel to each other

Within Phase 6 (US4):
- T029 (openai.py) + T030 (litellm.py) — parallel, both depend on T010 only

---

## Parallel Example: User Story 1

```
# Round 1 — all in parallel (no dependencies):
T010: providers/base.py
T011: prompts/system_prompt.jinja2
T012: prompts/__init__.py

# Round 2 — after T010:
T013: providers/claude.py

# Round 3 — after T005 (Phase 2):
T014: session.py
T015: parser.py
T016: market_context.py
T017: finalization.py   (after T015)

# Round 4 — after T010–T017:
T018: servicer.py (Chat RPC)

# Round 5 — after T018:
T019: tests/unit/test_parser.py
T020: tests/integration/test_session.py
T021: tests/acceptance/test_conversation_flow.py
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (**CRITICAL** — blocks all stories)
3. Complete Phase 3: User Story 1 (T010–T021)
4. **STOP and VALIDATE**: `grpcurl` test conversation works; acceptance test passes
5. Deploy/demo MVP

### Incremental Delivery

1. Phase 1 + 2 → Foundation ready
2. Phase 3 (US1) → Conversational search MVP — **demo-able**
3. Phase 4 (US2) → Add visual references — test independently
4. Phase 5 (US3) → Add subscription limits — test independently
5. Phase 6 (US4) → Add provider resilience — test independently
6. Phase 7 → Polish and CI wiring

### Parallel Team Strategy

With 2+ developers (after Phase 2 completes):

- **Dev A**: Phase 3 (US1 core) — T010 → T018 → T019–T021
- **Dev B**: Phase 6 (US4 providers) — T029–T030 independently; merge T031–T033 after Dev A completes T018
- Both US2 (T022–T025) and US3 (T026–T028) can be taken by either dev once T018 is merged

---

## Notes

- `[P]` tasks touch different files — safe to run in parallel without coordination
- Each user story phase ends with a checkpoint that can be demo'd or deployed independently
- `services/ai-chat/estategap_ai_chat/servicer.py` is the integration point — implement US1 version first, then extend incrementally for US2–US4 rather than rewriting
- Proto files (`ai_chat.proto`, generated stubs) are **already complete** — T001–T038 contain zero proto changes
- `estategap_common.models.ConversationState` and `ChatMessage` exist but are **not used directly** in Redis (raw dict serialization is used per D-002); they can be used as validation helpers
- Commit after each phase checkpoint for clean rollback points
