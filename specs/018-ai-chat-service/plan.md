# Implementation Plan: AI Conversational Search Service

**Branch**: `018-ai-chat-service` | **Date**: 2026-04-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/018-ai-chat-service/spec.md`

## Summary

Build a Python gRPC streaming service (`services/ai-chat/`) that implements `AIChatService` (proto already defined in `proto/estategap/v1/ai_chat.proto`). The service manages multi-turn property-search conversations via Redis, routes each turn through a pluggable LLM provider (Claude → OpenAI → LiteLLM), injects live market context from api-gateway, parses structured criteria JSON from every LLM response, triggers visual references from PostgreSQL, and — when criteria are complete — executes a listing search and creates an alert rule via gRPC. Subscription tier enforcement gates conversation starts and turn counts.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: grpcio 1.63+, grpcio-tools 1.63+, anthropic (AsyncAnthropic), openai (AsyncOpenAI), litellm 1.35+, redis[asyncio] 5.x, asyncpg 0.29+, pydantic-settings 2.2+, pydantic v2, jinja2 3.x, structlog 24.x, prometheus-client 0.20+, estategap-common (path dep)
**Storage**: Redis 7 (conversation state + message history — primary); PostgreSQL 16 + PostGIS 3.4 (visual_references table — read-only at runtime)
**Testing**: pytest + pytest-asyncio; unit (providers, parser, subscription logic); integration (Redis session store, DB queries); acceptance (full conversation flow end-to-end)
**Target Platform**: Linux (Kubernetes pod, amd64/arm64)
**Project Type**: gRPC microservice (bidirectional streaming)
**Performance Goals**: First streaming token delivered within 2 seconds of request receipt; market context gRPC call timeout 500 ms
**Constraints**: Redis TTL 24 h per session; max 40 messages per session (sliding window); LLM response max_tokens 1000; fallback provider retry on timeout/rate-limit only (not on auth errors)
**Scale/Scope**: Per-tenant streaming sessions; subscription-tier enforcement enforced in-process; single service replica initially, scale via Kubernetes HPA

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Polyglot Service Architecture — Python for AI/ML workloads | ✅ PASS | `services/ai-chat/` is a Python service; AI conversational search is explicitly assigned to Python in the constitution |
| II. Event-Driven Communication — gRPC for sync calls, NATS for async | ✅ PASS | Client↔service uses gRPC bidirectional streaming; service→api-gateway uses gRPC unary; no REST/HTTP between services |
| II. No inter-service HTTP | ✅ PASS | Market context and finalization both call api-gateway via gRPC |
| II. Protobuf contracts in `proto/` | ✅ PASS | `ai_chat.proto` already exists and is linted via buf |
| III. Country-First Data Sovereignty | ✅ PASS | `country_code` is a field on `ChatRequest`; criteria JSON includes country dimension; visual_references is a lookup table (not property data — country partitioning not required) |
| IV. ML-Powered Intelligence — provider-agnostic LLM abstraction | ✅ PASS | `BaseLLMProvider` + Claude/OpenAI/LiteLLM implementations with env-var selection exactly satisfies constitution principle IV |
| V. Code Quality — Pydantic v2, asyncio, ruff+mypy strict, structlog, uv | ✅ PASS | All tooling aligns with constitution mandates |
| VI. Security — no secrets in code, rate limiting per tier | ✅ PASS | API keys via env vars / Kubernetes Sealed Secrets; subscription tier enforcement in-process |
| VII. Kubernetes-Native — Dockerfile + Helm | ✅ PASS | Dockerfile present in stub; Helm chart values extended with new service block |

**No constitution violations. Gate cleared.**

## Project Structure

### Documentation (this feature)

```
specs/018-ai-chat-service/
├── plan.md              ← this file
├── research.md          ← Phase 0
├── data-model.md        ← Phase 1
├── quickstart.md        ← Phase 1
├── contracts/
│   └── grpc.md          ← Phase 1 (annotated proto contract)
└── tasks.md             ← Phase 2 (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```
proto/estategap/v1/
└── ai_chat.proto              ← ALREADY EXISTS — no changes needed

libs/common/
├── estategap_common/
│   └── models/
│       ├── conversation.py    ← ALREADY EXISTS (ConversationState, ChatMessage)
│       └── user.py            ← ALREADY EXISTS (User, Subscription, SubscriptionTier)
└── proto/estategap/v1/
    ├── ai_chat_pb2.py         ← ALREADY EXISTS (generated)
    └── ai_chat_pb2_grpc.py    ← ALREADY EXISTS (generated)

services/ai-chat/
├── Dockerfile                 ← UPDATE: CMD → python -m estategap_ai_chat
├── .env.example               ← UPDATE: add all required env vars
├── main.py                    ← UPDATE: implement asyncio.run(__main__.main()) two-liner
├── pyproject.toml             ← UPDATE: add grpcio, asyncpg, redis, prometheus-client,
│                                         pydantic-settings, jinja2, anthropic, openai
└── estategap_ai_chat/
    ├── __init__.py            ← EXISTS (stub — no changes)
    ├── __main__.py            ← NEW — async main: wire Redis + asyncpg pool + call serve()
    ├── py.typed               ← EXISTS
    ├── config.py              ← NEW — pydantic-settings Config (all env vars)
    ├── metrics.py             ← NEW — prometheus counters/histograms + HTTP metrics server
    ├── server.py              ← NEW — grpc.aio.server lifecycle, port 50053
    ├── servicer.py            ← NEW — AIChatServiceServicer (Chat, GetConversation, ListConversations)
    ├── session.py             ← NEW — Redis hash + list ops, TTL management, sliding window
    ├── parser.py              ← NEW — CriteriaState model, regex JSON extraction, retry logic
    ├── finalization.py        ← NEW — criteria→search params, gRPC listings + alert calls
    ├── market_context.py      ← NEW — gRPC stub to api-gateway (500 ms timeout, graceful fallback)
    ├── visual_refs.py         ← NEW — asyncpg query: visual_references WHERE tags @> ARRAY[...]
    ├── subscription.py        ← NEW — tier enforcement: daily conv count + per-turn turn gates
    ├── providers/
    │   ├── __init__.py        ← NEW
    │   ├── base.py            ← NEW — BaseLLMProvider ABC, Message dataclass
    │   ├── claude.py          ← NEW — AsyncAnthropic, model claude-sonnet-4-20250514
    │   ├── openai.py          ← NEW — AsyncOpenAI, model gpt-4o, stream=True
    │   └── litellm.py         ← NEW — litellm.acompletion, model from LITELLM_MODEL env
    └── prompts/
        ├── __init__.py        ← NEW — render_system_prompt(context) helper
        └── system_prompt.jinja2  ← NEW — Jinja2 template (role, language, data, output format)

services/ai-chat/tests/
├── __init__.py
├── conftest.py                ← NEW — Redis + asyncpg fixtures, FakeLLMProvider
├── unit/
│   ├── test_parser.py         ← CriteriaState extraction, retry, malformed JSON
│   ├── test_providers.py      ← provider selection, fallback, streaming iteration
│   └── test_subscription.py  ← Free/Basic/Pro+ daily and per-turn limit gates
├── integration/
│   ├── test_session.py        ← Redis hash/list ops, TTL extension, sliding window
│   └── test_servicer.py       ← gRPC servicer with real Redis (testcontainers)
└── acceptance/
    └── test_conversation_flow.py  ← full 10-turn conv: vague input → confirmed search + alert

helm/estategap/
└── values.yaml                ← UPDATE: add ai-chat service block (image, port 50053, env refs)
```

**Structure Decision**: Single Python service package (`estategap_ai_chat`) following `services/ml/estategap_ml/scorer/` exactly — same `config.py`, `server.py`, `servicer.py`, `__main__.py` pattern. Providers isolated in their own subpackage for independent testing and swapping without touching servicer logic. Prompts as a subpackage to allow Jinja2 template loading via `importlib.resources`.

## Complexity Tracking

*No constitution violations — this section is not required.*
