# Data Model: E2E Test Suite (031-e2e-test-suite)

**Branch**: `031-e2e-test-suite` | **Date**: 2026-04-17

This document describes the data structures owned by the E2E test suite itself (fixtures, client helpers, test state). The suite does not add any new database tables. It reads from existing seeded data (`tests/fixtures/`) and manages ephemeral test-run state via naming conventions.

---

## Entities

### TestRunContext

An in-process session-scoped object created at the start of each pytest session. Passed to fixtures that need run-level isolation.

| Field | Type | Description |
|-------|------|-------------|
| `run_id` | `str` | UUID4 prefix used for all created resources, e.g. `test-run-a3f9b1c2` |
| `api_base_url` | `str` | `http://localhost:8080` (from env `API_BASE_URL`) |
| `ws_base_url` | `str` | `ws://localhost:8081` (from env `WS_BASE_URL`) |
| `frontend_url` | `str` | `http://localhost:3000` (from env `FRONTEND_URL`) |

---

### TestUser

Loaded from `tests/fixtures/users.json` at session start. One record per subscription tier.

| Field | Type | Description |
|-------|------|-------------|
| `tier` | `str` | `free`, `basic`, `pro`, `global`, `api`, `admin` |
| `email` | `str` | Seeded email, e.g. `free@test.estategap.com` |
| `password` | `str` | Plaintext password matching seeded bcrypt hash (`secret`) |
| `access_token` | `str \| None` | Resolved at session start via `POST /api/v1/auth/login` |
| `refresh_token` | `str \| None` | Resolved at session start |
| `allowed_countries` | `list[str]` | From seeded fixture (e.g. `["ES"]` for free) |

---

### SeededIDs

Session-scoped mapping resolved at test start by querying the deployed API. Used by API and WebSocket tests to reference real seeded entities without hardcoding IDs.

| Field | Type | Description |
|-------|------|-------------|
| `listing_ids_by_country` | `dict[str, list[str]]` | `{"ES": ["uuid1", ...], "IT": [...]}` |
| `zone_ids_by_country` | `dict[str, list[str]]` | `{"ES": ["uuid1", ...], "FR": [...]}` |
| `portal_ids` | `list[str]` | Available portal IDs from `/api/v1/portals` |
| `country_codes` | `list[str]` | Available country codes from `/api/v1/countries` |

---

### APIClientState

Managed by `tests/e2e/helpers/client.py` — per-tier async HTTP client wrapper.

| Field | Type | Description |
|-------|------|-------------|
| `base_url` | `str` | API Gateway base URL |
| `tier` | `str` | Subscription tier for this client |
| `headers` | `dict` | Default headers including `Authorization: Bearer <token>` |
| `_client` | `httpx.AsyncClient` | Underlying async client instance |

**Methods**:
- `get(path, **kwargs)` → `httpx.Response`
- `post(path, json=None, **kwargs)` → `httpx.Response`
- `put(path, json=None, **kwargs)` → `httpx.Response`
- `delete(path, **kwargs)` → `httpx.Response`
- `refresh_token()` → updates `access_token` in headers

---

### WSTestClient

Managed by `tests/e2e/helpers/ws_client.py` — async WebSocket test client.

| Field | Type | Description |
|-------|------|-------------|
| `url` | `str` | WS URL with token query param: `ws://localhost:8081/ws?token=<jwt>` |
| `ws` | `websockets.WebSocketClientProtocol \| None` | Active connection |
| `received` | `list[dict]` | All messages received since connection or last clear |
| `session_id` | `str \| None` | Session ID for reconnection tests |

**Methods**:
- `send_chat(text, session_id)` — send `chat_message` envelope
- `send_image_feedback(listing_id, action)` — send `image_feedback` envelope
- `send_criteria_confirm(confirmed, notes)` — send `criteria_confirm` envelope
- `collect_messages(until_type, timeout)` — collect until message of `until_type` arrives
- `next_message(timeout)` — receive exactly one message
- `clear()` — reset `received` list

---

### WireEnvelope

Mirrors `services/ws-server/internal/protocol/messages.go`. Used in test assertions.

| Field | Type | Description |
|-------|------|-------------|
| `type` | `str` | Message type: `text_chunk`, `criteria_summary`, `image_carousel`, `deal_alert`, `chips`, `search_results`, `error` |
| `session_id` | `str \| None` | Session ID echoed back from server |
| `payload` | `dict` | Type-specific payload (see WS protocol contract) |

---

### ScoredListingEvent

Used by `tests/e2e/helpers/nats_injector.py` to inject synthetic deal-alert triggers into the `scored.listings` NATS JetStream subject.

| Field | Type | Description |
|-------|------|-------------|
| `listing_id` | `str` | UUID of a seeded listing |
| `country_code` | `str` | Country code matching the seeded listing |
| `price_eur` | `float` | Price in EUR |
| `area_m2` | `float` | Area in m² |
| `deal_score` | `float` | Score 0.0–1.0; use `0.95` to guarantee tier-1 match |
| `deal_tier` | `int` | 1–4 where 1 is the best deal |
| `title` | `str` | Listing title for display in alert message |
| `address` | `str` | Full address string |
| `photo_url` | `str \| None` | Optional image URL |

---

### TestRunArtifact

Describes the directory structure created by `tests/e2e/collect-artifacts.sh` on failure.

```text
/tmp/e2e-artifacts/<run-id>/
├── logs/
│   ├── estategap-gateway/
│   │   ├── api-gateway.log
│   │   └── websocket-server.log
│   ├── estategap-system/
│   │   ├── postgres-rw.log
│   │   └── [other pods].log
│   └── monitoring/
│       └── prometheus.log
├── describe/
│   └── [failed-pod-name].txt
├── db/
│   └── dump.sql
├── nats/
│   └── stream-info.txt
└── playwright/           # managed by Playwright itself
    ├── screenshots/
    ├── videos/
    └── traces/
```

---

## State Transitions

### Test Resource Lifecycle

```
Session Start
  └─► resolve SeededIDs (via API)
  └─► load TestUsers (from users.json)
  └─► login all tiers (via API) → store access_tokens
  └─► generate TEST_RUN_ID

Test Execution
  └─► create resources (alert rules, portfolio entries) with run_id prefix
  └─► use SeededIDs to reference existing listings/zones
  └─► WebSocket connect/disconnect per test

Session Teardown
  └─► DELETE all resources matching TEST_RUN_ID prefix
  └─► flush Redis keys: SCAN/DELETE test-run:{run_id}:*
  └─► disconnect open WebSocket connections
```

---

## Validation Rules

- `TestUser.access_token` must be non-None before any authenticated API test runs; fail fast with a clear error if login fails during session setup.
- `SeededIDs.listing_ids_by_country` must have at least one entry per expected country (`ES`, `IT`, `FR`, `PT`, `GB`); fail fast if seeding is incomplete.
- `WireEnvelope.type` must be one of the known message types defined in the WS protocol; unknown types trigger an assertion failure with the raw payload logged.
- `ScoredListingEvent.listing_id` must reference a listing seeded in the cluster and visible to the test user's alert rule; use a `pro` or `global` tier user's listing to avoid country-restriction issues.
