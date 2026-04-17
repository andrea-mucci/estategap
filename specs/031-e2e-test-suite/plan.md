# Implementation Plan: E2E User Journey Tests

**Branch**: `032-e2e-user-journeys` | **Date**: 2026-04-17 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/031-e2e-test-suite/spec.md`

## Summary

Implement 15 end-to-end user journey tests (`tests/usecase/`) that exercise the fully-deployed EstateGap platform on a kind cluster. Each journey validates a complete, business-critical user flow across multiple services (api-gateway, ws-server, ai-chat, ml-scorer, alert-engine, notification-dispatcher, pipeline). The test suite uses Python/pytest as the orchestrator with Playwright for browser-based interactions, reusing helpers from the existing `tests/e2e/` suite and adding new helpers for K8s, DB verification, time travel, and notification spying.

## Technical Context

**Language/Version**: Python 3.12
**Primary Dependencies**: pytest 8.2+, pytest-asyncio 0.23+, playwright 1.43+ (Python), asyncpg 0.29+, nats-py 2.6+, redis 5.x, websockets 12+, httpx 0.27+, kubernetes 29.0+
**Storage**: PostgreSQL 16 (read-only verification via asyncpg), Redis 7 (notification spy reads + Redis reset), no schema changes
**Testing**: pytest + pytest-asyncio (asyncio_mode = auto), Playwright async API
**Target Platform**: kind cluster (localhost) running full EstateGap platform
**Project Type**: external test suite (no production code changes)
**Performance Goals**: each journey < 5 minutes; full suite < 30 minutes
**Constraints**: requires `make kind-deploy` + `make kind-seed` as prerequisites; time-travel tests restart pods (+30s overhead) and are marked `@pytest.mark.slow`
**Scale/Scope**: 15 journey tests, 8 shared helpers, ~2000 LOC

## Constitution Check

| Principle | Check | Status |
|-----------|-------|--------|
| I. Polyglot Architecture | Python for test orchestration matches data/ML workload profile. No Go test code. Test helpers never import production service internals. | ✅ Pass |
| II. Event-Driven Communication | Tests publish to NATS (raw listings), observe NATS-driven effects (alerts), never call services peer-to-peer. API access goes through api-gateway only. | ✅ Pass |
| III. Country-First Data Sovereignty | Journey tests cover ES, IT, FR explicitly (UJ-09). Injected listings always include `country_code`. | ✅ Pass |
| IV. ML-Powered Intelligence | UJ-02 validates SHAP on detail page; UJ-07 validates model retrain + hot-reload; UJ-11 validates re-scoring on price change. | ✅ Pass |
| V. Code Quality Discipline | pytest + ruff + mypy strict in `pyproject.toml`. All helpers typed with Pydantic v2 models where applicable. `asyncio_mode = auto`. | ✅ Pass |
| VI. Security & Ethical Scraping | Test users use seeded credentials, not production. No scraping patterns; test spiders are minimal fixture triggers only. | ✅ Pass |
| VII. Kubernetes-Native Deployment | Tests run against kind cluster, use `kubectl` for K8s operations, clean up via DB queries not kubectl delete. | ✅ Pass |

**Verdict**: No violations. No Complexity Tracking entry needed.

## Project Structure

### Documentation (this feature)

```text
specs/031-e2e-test-suite/
├── plan.md              # This file
├── research.md          # Phase 0: Stack and pattern decisions
├── data-model.md        # Phase 1: Test infrastructure entities
├── quickstart.md        # Phase 1: How to run and extend
├── contracts/           # Phase 1: pytest.ini spec, make targets
│   ├── pytest-ini.md    # pytest markers and config spec
│   └── make-targets.md  # Makefile target definitions
└── tasks.md             # Phase 2: implementation tasks
```

### Source Code Layout

```text
tests/usecase/
├── conftest.py                    # Cluster fixture, test_context fixture, run_id
├── pyproject.toml                 # uv project: playwright, asyncpg, kubernetes +
│                                  #   inherited: httpx, nats-py, websockets, redis
├── pytest.ini                     # asyncio_mode=auto, markers, testpaths
├── helpers/
│   ├── __init__.py
│   ├── api.py                     # ApiClient: thin wrapper around AsyncAPIClient
│   │                              #   + login() classmethod, create_alert_rule(), etc.
│   ├── ws.py                      # re-exports WSTestClient from tests/e2e/helpers/
│   ├── browser.py                 # BrowserHelper: async_playwright wrapper,
│   │                              #   login(), goto(), screenshot(), close()
│   ├── cluster.py                 # ClusterHelper: is_ready(), fixtures_loaded(),
│   │                              #   pod_logs(), job_status(), wait_for_job()
│   ├── db.py                      # DbClient: asyncpg pool, fetch/fetchrow/execute,
│   │                              #   cleanup_by_run_id()
│   ├── fixtures.py                # publish_raw_listing(), inject_price_update()
│   │                              #   builds NATS payloads for the pipeline
│   ├── spies.py                   # EmailSpy, TelegramSpy: poll Redis spy:* keys
│   ├── time_travel.py             # TimeTravel: ConfigMap patch + rollout restart
│   └── assertions.py             # assert_within_baseline(), assert_deal_tier(),
│                                  #   assert_gdpr_anonymized(), BASELINES dict
├── uj01_onboarding_test.py        # browser + API
├── uj02_find_deal_test.py         # browser + API (latency: < 5s)
├── uj03_alert_notification_test.py# API + NATS + spies (latency: < 30s)
├── uj04_ai_chat_to_alert_test.py  # WS + API (latency: < 60s)
├── uj05_subscription_upgrade_test.py # browser + API + Stripe webhook
├── uj06_portfolio_multi_currency_test.py # browser + API
├── uj07_admin_retrain_ml_test.py  # browser + K8s Job (latency: < 5 min)
├── uj08_free_tier_delay_test.py   # API + TimeTravel (slow)
├── uj09_multi_country_search_test.py # API only
├── uj10_gdpr_export_delete_test.py # browser + API + DB
├── uj11_price_drop_engagement_test.py # API + NATS + spies + DB
├── uj12_scraping_recovery_test.py # API + K8s + proxy stub
├── uj13_language_switch_test.py   # browser only
├── uj14_websocket_reconnect_test.py # WS + browser
└── uj15_scrape_to_alert_latency_test.py # NATS + API + spies (latency: < 2 min)
```

**Structure Decision**: Separate `tests/usecase/` sibling directory (not a subdirectory of `tests/e2e/`) to enable independent `pytest.ini` scoping, independent `make` targets, and a separate `pyproject.toml` with Playwright + asyncpg dependencies not present in the API/WS test suite. Helpers in `tests/usecase/helpers/` import from `tests/e2e/helpers/` via `sys.path` manipulation in `conftest.py` (same pattern as `tests/e2e/conftest.py`).

## Phase 0 Research Summary

See [research.md](research.md) for full decision log. Key choices:

1. **Python pytest** orchestrates all 15 journeys; Playwright called inline for browser flows.
2. **Notification spies** read from Redis: services write `spy:email:{email}` lists in `TEST_MODE=true`.
3. **Time travel** patches `estategap-runtime` ConfigMap + `kubectl rollout restart`.
4. **Test isolation** cleans up by `source_id` prefix per test, never full table truncate.
5. **Stripe (UJ-05)**: browser drives to Checkout redirect; webhook fired programmatically.
6. **Performance baselines** hardcoded in `helpers/assertions.py`; 20% regression threshold.

## Phase 1 Design Summary

See [data-model.md](data-model.md) for entity definitions. Core test infrastructure:

- `TestContext`: per-test lifecycle, run_id namespacing, artifact collection on failure.
- `ClusterHelper`: session-scoped, wraps `kubectl` calls, checks pod readiness.
- `DbClient`: asyncpg pool for verification reads and cleanup queries.
- `EmailSpy` / `TelegramSpy`: Redis-backed notification verification.
- `TimeTravel`: ConfigMap patch + rollout restart + rollout status wait.
- `BrowserHelper`: Playwright page factory with screenshot-on-failure.
- `BASELINES`: dict of latency reference values with 20% regression threshold.

## Implementation Phases

### Phase A: Infrastructure (Tasks 1–3)

Lay the shared foundation that all 15 journey tests build on.

**Task 1: Project scaffold**
- `tests/usecase/pyproject.toml` with all dependencies
- `tests/usecase/pytest.ini` with markers and asyncio config
- `tests/usecase/conftest.py` with `cluster`, `test_context` fixtures
- `tests/usecase/helpers/__init__.py`

**Task 2: Core helpers**
- `helpers/api.py`: `ApiClient` wrapper (login, create_alert_rule, create_portfolio_item, trigger_stripe_webhook, set_language_preference)
- `helpers/ws.py`: re-export `WSTestClient`; add `collect_until_type()` convenience
- `helpers/cluster.py`: `ClusterHelper` (is_ready, fixtures_loaded, pod_logs, job_status, wait_for_job)
- `helpers/db.py`: `DbClient` (asyncpg pool, fetch, cleanup_by_run_id)
- `helpers/fixtures.py`: `publish_raw_listing()`, `inject_price_update()`

**Task 3: Advanced helpers**
- `helpers/browser.py`: `BrowserHelper` (async_playwright, login, goto, screenshot, close)
- `helpers/spies.py`: `EmailSpy`, `TelegramSpy`
- `helpers/time_travel.py`: `TimeTravel` (set_time, advance_hours, reset)
- `helpers/assertions.py`: `assert_within_baseline()`, `assert_deal_tier()`, `assert_gdpr_anonymized()`, `BASELINES`

### Phase B: Core Journey Tests (Tasks 4–9)

Implement the highest-value, most-complex journeys first.

**Task 4: UJ-03 Alert Notification** (multi-service, validates spy pattern)
**Task 5: UJ-15 Scrape-to-Alert Latency** (full pipeline, latency assertion)
**Task 6: UJ-11 Price Drop Engagement** (re-scoring, email tracking)
**Task 7: UJ-04 AI Chat to Alert** (WebSocket + LLM + alert auto-creation)
**Task 8: UJ-08 Free Tier Delay** (time travel)
**Task 9: UJ-05 Subscription Upgrade** (Stripe webhook simulation)

### Phase C: Browser Journey Tests (Tasks 10–14)

Tests requiring Playwright browser automation.

**Task 10: UJ-01 Onboarding** (registration flow)
**Task 11: UJ-02 Find Deal** (search + detail, SHAP, comparables, latency)
**Task 12: UJ-06 Portfolio Multi-Currency** (CRUD + ML valuation + currency)
**Task 13: UJ-07 Admin Retrain** (K8s Job, MLflow, model hot-reload)
**Task 14: UJ-10 GDPR Export & Delete** (data export, anonymization, login failure)

### Phase D: Remaining Journey Tests (Tasks 15–17)

**Task 15: UJ-09, UJ-13 (API-only and i18n)**
- UJ-09: Multi-country search + currency reconversion
- UJ-13: Language switch preserves URL state

**Task 16: UJ-12, UJ-14 (recovery and reconnection)**
- UJ-12: Scraping failure + proxy rotation + re-scrape
- UJ-14: WebSocket reconnection + session persistence

**Task 17: Documentation and CI**
- `docs/test-scenarios.md`: Given/When/Then for all 15 journeys, run instructions, debug guide
- `Makefile`: `test-usecase`, `test-usecase-fast`, `test-usecase-browser`, `test-usecase-api` targets
- GitHub Actions: nightly workflow, PR trigger for critical-path changes

## Key Risks

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Spy pattern requires TEST_MODE in services | Medium | Verify TEST_MODE flag exists in notification-dispatcher; add if missing |
| TimeTravel pod restart flakiness | Medium | Add `kubectl rollout status --timeout=3m`; retry once |
| UJ-07 retrain exceeds 2-minute budget | Low | Use minimal fixture dataset (50 listings); mark `@pytest.mark.slow` |
| Stripe Checkout iframe interaction | High | Test only up to redirect; fire webhook programmatically |
| WS reconnect timing in UJ-14 | Medium | Use server-side close via kubectl exec; add 5s tolerance |
| UJ-12 proxy stub setup complexity | Medium | Use a simple httptest server stub in `cluster.py`; container injection |
