# Implementation Plan: E2E Test Suite

**Branch**: `031-e2e-test-suite` | **Date**: 2026-04-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `specs/031-e2e-test-suite/spec.md`

## Summary

Build a complete end-to-end test suite that validates the fully deployed EstateGap platform on a local kind cluster. The suite comprises three layers: Python pytest tests for the REST API and WebSocket protocol, TypeScript Playwright tests for browser UI flows, and Python concurrency stress tests. Orchestration is via Makefile targets (`make kind-test`) with bash artifact collection on failure.

## Technical Context

**Language/Version**: Python 3.12 (API + WebSocket + concurrency tests), TypeScript 5.5 / Node.js 22 (Playwright browser tests)
**Primary Dependencies**:
- Python: `pytest`, `pytest-asyncio`, `httpx`, `websockets`, `pytest-xdist` (parallel sharding)
- TypeScript: `@playwright/test`, `axe-playwright` (accessibility), `@axe-core/playwright`
**Storage**: No direct DB writes from tests. PostgreSQL seeded via existing `tests/fixtures/load.py`; Redis flushed per-run via helper script
**Testing**: pytest 7+ (Python), Playwright test runner (TypeScript)
**Target Platform**: kind cluster (`CLUSTER_NAME=estategap`), services exposed on localhost via port-forward (`tests/kind/port-forward.sh`):
- API Gateway → `http://localhost:8080`
- WebSocket server → `ws://localhost:8081`
- Frontend → `http://localhost:3000`
**Project Type**: Test infrastructure layer (not a deployable service)
**Performance Goals**: Full suite < 20 min on CI runner; concurrency test: 100 concurrent WS sessions complete without errors
**Constraints**: Tests MUST NOT import service-internal packages; cluster must already be deployed (`make kind-deploy`); test users seeded by existing `tests/fixtures/users.json`
**Scale/Scope**: ~200 Python test cases, ~100 Playwright specs across 3 browsers, 4 CI shard runners

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Polyglot Service Architecture | ✅ PASS | Tests are external to `services/`; language choices (Python API tests, TS Playwright) match workload profiles. No cross-service imports. |
| II. Event-Driven Communication | ✅ PASS | Tests interact only via public HTTP/WS surface. NATS JetStream injected for deal-alert scenario via a helper that publishes to existing streams. |
| III. Country-First Data Sovereignty | ✅ PASS | Test fixtures include multi-country data (ES, IT, FR, PT, GB). API tests exercise country-scoped filters. |
| IV. ML-Powered Intelligence | ✅ PASS | ML estimate endpoint tested; SHAP chart render tested in Playwright listing detail spec. |
| V. Code Quality Discipline | ✅ PASS | Python tests use `pytest` + `pytest-asyncio` per constitution. TypeScript tests use Playwright (separate from Vitest unit tests). `ruff` + `mypy` linting on Python test code. |
| VI. Security & Ethical Scraping | ✅ PASS | Auth tests cover JWT expiry, invalid signatures, rate limiting per tier. No scraping ethics concerns in tests. |
| VII. Kubernetes-Native Deployment | ✅ PASS | Tests target the kind cluster. No direct host DB access — uses port-forwarded services. `make kind-test` integrates cleanly with existing `mk/kind.mk` targets. |

**Violations**: None. No Complexity Tracking table required.

## Project Structure

### Documentation (this feature)

```text
specs/031-e2e-test-suite/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks command)
```

### Source Code (repository root)

```text
tests/e2e/
├── api/
│   ├── conftest.py               # session-scoped fixtures: api_base_url, test_users, authed_client
│   ├── test_auth.py              # register, login, refresh, logout, /me, /me PATCH, Google OAuth callback
│   ├── test_listings.py          # /listings, /listings/{id}, /listings/top-deals, filters, pagination, currency
│   ├── test_zones.py             # /zones CRUD, /zones/{id}/stats, /zones/{id}/analytics, compare, geometry
│   ├── test_alerts.py            # /alerts/rules CRUD, /alerts/history
│   ├── test_subscriptions.py     # /subscriptions/checkout, /subscriptions/portal, /subscriptions/me, tier gating
│   ├── test_admin.py             # admin/* endpoints, role enforcement
│   ├── test_reference.py         # /countries, /portals
│   ├── test_ml.py                # /model/estimate
│   ├── test_portfolio.py         # /portfolio/properties CRUD
│   ├── test_rate_limiting.py     # per-tier rate limits, Retry-After header, 429 shape
│   ├── test_errors.py            # 400/403/404/409/500 response shapes
│   └── fixtures/
│       ├── listing_ids.py        # resolved at session start from seeded data
│       └── zone_ids.py
│
├── websocket/
│   ├── conftest.py               # ws_base_url, ws_token fixtures
│   ├── test_connection.py        # valid JWT connects; invalid JWT → 4001; concurrent 100 sessions
│   ├── test_chat_protocol.py     # chat_message → text_chunk stream → criteria_summary
│   ├── test_image_carousel.py    # image_carousel receive, image_feedback send, criteria update
│   ├── test_deal_alert.py        # inject NATS event → deal_alert received within 5 s
│   ├── test_reconnection.py      # disconnect mid-stream, reconnect with same session_id → history intact
│   └── test_keepalive.py         # ping/pong at 30 s interval; idle close after 30 min (time-skipped)
│
├── concurrency/
│   ├── conftest.py
│   ├── test_concurrent_search.py # 2 users same zone simultaneously
│   ├── test_concurrent_alerts.py # 2 users create alerts on same listing; notifications isolated
│   ├── test_concurrent_crm.py    # CRM status update under concurrent read
│   └── test_concurrent_chat.py   # 100 WS sessions, no cross-talk
│
├── helpers/
│   ├── __init__.py
│   ├── client.py                 # AsyncAPIClient: login, token refresh, tier helpers
│   ├── ws_client.py              # WSTestClient class from spec
│   ├── fixtures.py               # resolve_listing_id(), resolve_zone_id() from seeded DB
│   ├── assertions.py             # assert_error_shape(), assert_pagination(), assert_rate_limit_headers()
│   ├── nats_injector.py          # publish deal alert event to NATS JetStream for test injection
│   └── redis_reset.py            # flush test-run Redis key namespace
│
├── pytest.ini                    # asyncio_mode=auto, markers: api ws concurrency slow
└── pyproject.toml                # uv project: httpx, websockets, pytest-asyncio, pytest-xdist, nats-py

frontend/tests/e2e/
├── playwright.config.ts          # 3 projects: chromium, firefox, webkit (critical only)
├── fixtures/
│   ├── users.ts                  # tier-aware user fixtures with stored auth state
│   └── auth.ts                   # storageState login helper
├── pages/                        # Page Object Model
│   ├── LandingPage.ts
│   ├── LoginPage.ts
│   ├── RegisterPage.ts
│   ├── ChatPage.ts
│   ├── SearchPage.ts
│   ├── ListingDetailPage.ts
│   ├── DashboardPage.ts
│   ├── AlertsPage.ts
│   ├── SubscriptionPage.ts
│   └── AdminPage.ts
├── specs/
│   ├── auth.spec.ts              # register, login, logout, Google OAuth (mocked)
│   ├── ai-chat.spec.ts           # query → stream → chips → confirm → results → alert created
│   ├── search.spec.ts            # filters, URL params, sort, grid/list toggle, saved search CRUD
│   ├── listing-detail.spec.ts    # all sections render, gallery swipe, translate, CRM actions
│   ├── dashboard.spec.ts         # cards, charts, country tab switching
│   ├── map.spec.ts               # zoom, marker popup, draw zone, marker re-fetch on pan
│   ├── alerts.spec.ts            # create/edit/delete rule, alert history
│   ├── subscription.spec.ts      # upgrade prompt, Stripe Checkout (mocked), webhook → tier update
│   ├── admin.spec.ts             # access denied for non-admin; stats, retrain, user list
│   ├── responsive.spec.ts        # 375×667 mobile, 768×1024 tablet viewports
│   └── accessibility.spec.ts     # keyboard nav, axe-core WCAG AA scan all pages
├── visual/
│   ├── baselines/                # committed PNG baselines per browser
│   └── visual-regression.spec.ts # 5 pages × toHaveScreenshot(), 0.1% threshold
└── utils/
    ├── mock-stripe.ts            # intercept Stripe redirect, simulate webhook call to API
    ├── mock-google-oauth.ts      # intercept Google OAuth redirect, inject fake callback params
    └── mock-voice.ts             # stub SpeechRecognition Web API via page.addInitScript

tests/e2e/collect-artifacts.sh    # kubectl logs, describe, pg_dump, NATS stream state → /tmp/e2e-artifacts/
```

**Structure Decision**: Multi-language layout: Python under `tests/e2e/` (API, WS, concurrency), TypeScript under `frontend/tests/e2e/` (browser). Shares `tests/fixtures/` (existing seeded data). `collect-artifacts.sh` at `tests/e2e/` root, callable from Makefile trap.

## Makefile Integration

New targets added to `mk/kind.mk` (or a new `mk/e2e.mk` included by root Makefile):

```makefile
E2E_REPORT_DIR := reports/e2e
UV_E2E_CMD     := uv run --project tests/e2e

kind-test: kind-test-api kind-test-ws kind-test-browser
	@echo "All E2E tests passed"

kind-test-api:
	@mkdir -p $(E2E_REPORT_DIR)
	@$(UV_E2E_CMD) pytest tests/e2e/api/ -v \
		--junitxml=$(E2E_REPORT_DIR)/api.xml \
		-n auto 2>&1 | tee $(E2E_REPORT_DIR)/api.log \
		|| (bash tests/e2e/collect-artifacts.sh $(E2E_REPORT_DIR) && exit 1)

kind-test-ws:
	@mkdir -p $(E2E_REPORT_DIR)
	@$(UV_E2E_CMD) pytest tests/e2e/websocket/ tests/e2e/concurrency/ -v \
		--junitxml=$(E2E_REPORT_DIR)/ws.xml 2>&1 | tee $(E2E_REPORT_DIR)/ws.log \
		|| (bash tests/e2e/collect-artifacts.sh $(E2E_REPORT_DIR) && exit 1)

kind-test-browser:
	@mkdir -p $(E2E_REPORT_DIR)
	@(cd frontend && pnpm playwright test \
		--reporter=junit,html \
		--output-dir=../$(E2E_REPORT_DIR)/playwright 2>&1 | tee ../$(E2E_REPORT_DIR)/browser.log) \
		|| (bash tests/e2e/collect-artifacts.sh $(E2E_REPORT_DIR) && exit 1)

kind-test-visual:
	@(cd frontend && pnpm playwright test visual/ --reporter=html)

kind-test-a11y:
	@(cd frontend && pnpm playwright test --grep "@a11y" --reporter=html)
```

`kind-test` target replaces the existing stub in `mk/kind.mk` (currently only runs helm tests).

## Artifact Collection

`tests/e2e/collect-artifacts.sh <output-dir>` collects on failure:
1. `kubectl logs` all pods in `estategap-gateway`, `estategap-system`, `monitoring` namespaces
2. `kubectl describe pod` for non-Running pods
3. `pg_dump` via port-forwarded `localhost:5432`
4. NATS stream state via `nats stream info` (all streams)
5. Playwright auto-generates screenshot, video, trace (configured in `playwright.config.ts`)

## Test Isolation Strategy

- Each test run generates a UUID prefix (`TEST_RUN_ID`), used as a Redis key namespace prefix and as a label on created resources (alert rules, portfolio entries) to isolate parallel shards.
- Global `conftest.py` `session`-scoped setup: verify cluster health via `GET /health`, load `TEST_RUN_ID`, resolve seeded listing/zone IDs.
- Global teardown: delete test-run-prefixed resources via API; flush Redis keys matching `test-run-{TEST_RUN_ID}:*`.
- Playwright: each spec file uses `storageState` for auth (pre-authenticated browser sessions); no shared state between spec files.

## Complexity Tracking

> No constitution violations — table not required.
