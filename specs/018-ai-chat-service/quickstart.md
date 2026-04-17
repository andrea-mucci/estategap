# Quickstart: AI Conversational Search Service

**Feature**: 018-ai-chat-service | **Date**: 2026-04-17

---

## Prerequisites

- Python 3.12 + `uv` installed
- Docker + Docker Compose (for Redis and PostgreSQL)
- `buf` CLI (for proto regeneration if proto changes)
- Running instances (or stubs) of api-gateway on port 50051

---

## 1. Environment Setup

```bash
cd services/ai-chat
cp .env.example .env
```

Edit `.env`:
```dotenv
# gRPC
GRPC_PORT=50053
METRICS_PORT=9090

# LLM Provider: "claude" | "openai" | "litellm"
LLM_PROVIDER=claude
FALLBACK_LLM_PROVIDER=openai

# Claude
ANTHROPIC_API_KEY=sk-ant-...

# OpenAI (fallback)
OPENAI_API_KEY=sk-...

# LiteLLM (optional, for self-hosted)
LITELLM_MODEL=ollama/llama3

# Redis
REDIS_URL=redis://localhost:6379/0

# PostgreSQL (for visual_references read-only)
DATABASE_URL=postgresql://estategap:password@localhost:5432/estategap

# api-gateway gRPC address
API_GATEWAY_GRPC_ADDR=localhost:50051

# Logging
LOG_LEVEL=INFO
```

---

## 2. Install Dependencies

```bash
cd services/ai-chat
uv sync
```

---

## 3. Start Dependencies (Redis + PostgreSQL)

```bash
# From repo root
docker compose up -d redis postgres
```

---

## 4. Run the Service

```bash
cd services/ai-chat
python -m estategap_ai_chat
```

Expected output:
```
{"level":"info","service":"ai-chat","event":"gRPC server started","port":50053}
{"level":"info","service":"ai-chat","event":"metrics server started","port":9090}
```

---

## 5. Test a Conversation (grpcurl)

```bash
# Install grpcurl if not available: brew install grpcurl

# Start a new conversation
grpcurl -plaintext \
  -d '{"conversation_id":"","user_message":"Ciao, cerco un appartamento a Milano","country_code":"IT"}' \
  -rpc-header 'x-user-id: 00000000-0000-0000-0000-000000000001' \
  -rpc-header 'x-subscription-tier: pro_plus' \
  localhost:50053 estategap.v1.AIChatService/Chat
```

Expected: streaming token responses ending with a JSON criteria block.

If `grpcurl` is unavailable, or if you want a deterministic mock validation without live LLM credentials, run the quickstart smoke test instead:

```bash
cd services/ai-chat
uv run pytest tests/acceptance/test_quickstart_smoke.py -v
```

This exercises the servicer with proto `ChatRequest` messages, in-memory Redis, and a fake LLM provider, then verifies that the streaming response includes token chunks plus the final criteria JSON block. It does not exercise live Redis, PostgreSQL, api-gateway, external LLM APIs, or a real network listener.

---

## 6. Run Tests

```bash
cd services/ai-chat

# Unit tests only (no external deps)
uv run pytest tests/unit/ -v

# Integration tests (requires Redis + PostgreSQL via testcontainers)
uv run pytest tests/integration/ -v

# Acceptance test (requires all deps including LLM provider or mock)
LLM_PROVIDER=fake uv run pytest tests/acceptance/ -v
```

---

## 7. Switch LLM Provider

Change `LLM_PROVIDER` in `.env`:
```dotenv
LLM_PROVIDER=openai           # GPT-4o
LLM_PROVIDER=litellm          # Self-hosted (set LITELLM_MODEL=ollama/llama3)
LLM_PROVIDER=claude           # Anthropic Claude (default)
```

Restart the service. No code changes required.

---

## 8. Build Docker Image

```bash
cd services/ai-chat
docker build -t estategap/ai-chat:dev .

docker run --env-file .env \
  -p 50053:50053 -p 9090:9090 \
  estategap/ai-chat:dev
```

---

## Key Configuration Reference

| Env Var | Default | Description |
|---------|---------|-------------|
| `LLM_PROVIDER` | `claude` | Primary LLM provider |
| `FALLBACK_LLM_PROVIDER` | `openai` | Fallback on primary error |
| `ANTHROPIC_API_KEY` | — | Required when `LLM_PROVIDER=claude` |
| `OPENAI_API_KEY` | — | Required when `LLM_PROVIDER=openai` or fallback |
| `LITELLM_MODEL` | — | Required when `LLM_PROVIDER=litellm` |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection string |
| `DATABASE_URL` | — | PostgreSQL DSN (read-only) |
| `API_GATEWAY_GRPC_ADDR` | `localhost:50051` | api-gateway gRPC address |
| `GRPC_PORT` | `50053` | Service gRPC port |
| `METRICS_PORT` | `9090` | Prometheus metrics HTTP port |
| `LOG_LEVEL` | `INFO` | structlog level |

---

## Prometheus Metrics

Available at `http://localhost:9090/metrics`:

| Metric | Type | Description |
|--------|------|-------------|
| `ai_chat_conversations_total` | Counter | New conversations started, by tier |
| `ai_chat_turns_total` | Counter | Completed turns, by provider |
| `ai_chat_llm_latency_seconds` | Histogram | Time to first token per provider |
| `ai_chat_criteria_parse_errors_total` | Counter | JSON parse failures |
| `ai_chat_fallback_activations_total` | Counter | Times fallback provider was used |
| `ai_chat_subscription_rejections_total` | Counter | Requests rejected by tier limits |
