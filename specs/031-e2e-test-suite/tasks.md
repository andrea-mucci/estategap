# Tasks: E2E Test Suite

**Input**: Design documents from `specs/031-e2e-test-suite/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Directory scaffolding and project initialization across Python and TypeScript suites.

- [X] T001 Create directory tree `tests/e2e/{api,websocket,concurrency,helpers}/` and `frontend/tests/e2e/{fixtures,pages,specs,visual/baselines,utils}/` per plan.md structure
- [X] T002 Create `tests/e2e/pyproject.toml` with uv project declaring dependencies: `pytest>=7`, `pytest-asyncio>=0.23`, `pytest-xdist>=3`, `httpx>=0.27`, `websockets>=12`, `nats-py>=2.6`, `pydantic>=2`, `ruff`, `mypy`
- [X] T003 Create `tests/e2e/pytest.ini` with `asyncio_mode = auto`, markers `api`, `ws`, `concurrency`, `slow`, and `testpaths = api websocket concurrency`
- [X] T004 [P] Add `tests/e2e/helpers/__init__.py` empty module init file
- [X] T005 [P] Add `tests/e2e/api/__init__.py`, `tests/e2e/websocket/__init__.py`, `tests/e2e/concurrency/__init__.py` empty init files

**Checkpoint**: Directory structure and project config in place — uv sync should succeed.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared infrastructure that every user story phase depends on — helpers, fixtures, Playwright config, Makefile targets, and cluster config changes. All stories are blocked until this phase is complete.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 Create `tests/e2e/helpers/client.py` implementing `AsyncAPIClient`: wraps `httpx.AsyncClient` with `base_url`, tier-aware `Authorization` header, and `get/post/put/delete/patch` async methods as defined in data-model.md
- [X] T007 Create `tests/e2e/helpers/ws_client.py` implementing `WSTestClient` with `send_chat`, `send_image_feedback`, `send_criteria_confirm`, `collect_messages(until_type, timeout)`, `next_message(timeout)`, and `clear()` per data-model.md + contracts/ws-protocol.md
- [X] T008 Create `tests/e2e/helpers/assertions.py` implementing `assert_error_shape(response, status_code, error_code)`, `assert_pagination(response)`, `assert_rate_limit_headers(response)`, `assert_envelope_type(msg, expected_type)` helpers
- [X] T009 Create `tests/e2e/helpers/fixtures.py` implementing `resolve_listing_ids(client)` and `resolve_zone_ids(client)` that query `GET /api/v1/listings` and `GET /api/v1/zones` at session start and return `SeededIDs` per data-model.md
- [X] T010 Create `tests/e2e/helpers/nats_injector.py` implementing `publish_scored_listing(nats_url, event: ScoredListingEvent)` using `nats-py` JetStream to publish to `scored.listings` subject, with `ScoredListingEvent` Pydantic model per data-model.md + research.md Decision 6
- [X] T011 Create `tests/e2e/helpers/redis_reset.py` implementing `flush_test_run_keys(redis_url, run_id)` that scans and deletes all Redis keys matching `test-run:{run_id}:*`
- [X] T012 Create `tests/e2e/api/conftest.py` with session-scoped fixtures: `api_base_url` (from `API_BASE_URL` env, default `http://localhost:8080`), `test_run_id` (UUID4), `test_users` (loaded from `tests/fixtures/users.json` + resolved tokens via login), `seeded_ids` (via `helpers/fixtures.py`), `authed_client(tier)` parametrizable async fixture per plan.md
- [X] T013 Create `tests/e2e/websocket/conftest.py` with session-scoped fixtures: `ws_base_url` (from `WS_BASE_URL` env, default `ws://localhost:8081`), `ws_token(tier)` that returns the JWT from `test_users`, and a factory `ws_client(tier)` async context manager
- [X] T014 Create `tests/e2e/concurrency/conftest.py` re-exporting fixtures from `api/conftest.py` and `websocket/conftest.py` via `conftest.py` path resolution (use `sys.path` insert or `conftest` plugin approach)
- [X] T015 Create `tests/e2e/collect-artifacts.sh` that: (1) runs `kubectl logs` for all pods in `estategap-gateway`, `estategap-system`, `monitoring` namespaces, (2) runs `kubectl describe pod` for non-Running pods, (3) runs `pg_dump` via `localhost:5432`, (4) runs `nats stream info` for all streams, outputs to `$1` directory arg per plan.md
- [X] T016 [P] Create `frontend/tests/e2e/fixtures/users.ts` exporting `TIER_USERS` constant with `{ free, basic, pro, global, api, admin }` email/password pairs matching `tests/fixtures/users.json`
- [X] T017 [P] Create `frontend/tests/e2e/fixtures/auth.ts` exporting a `loginAs(page, tier)` helper and a Playwright `test.extend` fixture factory that loads `storageState` from `frontend/tests/e2e/auth/<tier>.json` when it exists
- [X] T018 Create `frontend/tests/e2e/playwright.config.ts` defining three projects: `chromium` (all specs), `firefox` (all specs, tagged `@nightly`), `webkit` (critical path only: `auth.spec.ts`, `search.spec.ts`, `listing-detail.spec.ts`); `globalSetup` for per-tier storageState generation; `use.baseURL = process.env.FRONTEND_URL ?? 'http://localhost:3000'`; `reporter = [['html'], ['junit', {outputFile: '../reports/e2e/playwright.xml'}]]`; `fullyParallel = true`; on failure: `screenshot: 'only-on-failure'`, `video: 'retain-on-failure'`, `trace: 'retain-on-failure'`
- [X] T019 [P] Create `frontend/tests/e2e/utils/mock-stripe.ts` implementing `mockStripeCheckout(page)` that intercepts the redirect to `checkout.stripe.com` and calls `POST /api/v1/subscriptions/webhook` with a test-mode `checkout.session.completed` event
- [X] T020 [P] Create `frontend/tests/e2e/utils/mock-google-oauth.ts` implementing `mockGoogleOAuth(page)` that intercepts the redirect to `accounts.google.com/o/oauth2/auth` and injects a fake `code` callback param back to `/auth/google/callback`
- [X] T021 [P] Create `frontend/tests/e2e/utils/mock-voice.ts` implementing `mockSpeechRecognition(page)` that injects a stub `window.SpeechRecognition` via `page.addInitScript` returning a predefined transcript
- [X] T022 Add `kind-test-api`, `kind-test-ws`, `kind-test-browser`, `kind-test-visual`, `kind-test-a11y`, and updated `kind-test` targets to `mk/kind.mk` per plan.md Makefile Integration section, replacing the existing stub `kind-test` target
- [X] T023 Add `wsServer.env.WS_IDLE_TIMEOUT_SECS: "30"` and `wsServer.env.WS_PING_INTERVAL_SECS: "10"` to `helm/estategap/values-test.yaml` to allow idle timeout and keepalive tests to complete in reasonable time per research.md Decision 4

**Checkpoint**: Foundation ready — all helpers exist, Playwright is configured, Makefile targets are wired, cluster config supports short idle timeouts. User story implementation can now begin.

---

## Phase 3: User Story 1 — REST API Correctness (Priority: P1) 🎯 MVP

**Goal**: Validate every documented REST endpoint for happy-path correctness, authentication gates, rate limits, pagination, filters, currency conversion, tier gating, and error shapes.

**Independent Test**: `make kind-test-api` passes with all test files in `tests/e2e/api/`.

- [X] T024 [US1] Create `tests/e2e/api/test_auth.py` covering: `POST /auth/register` (happy path, duplicate → 409, invalid email → 400), `POST /auth/login` (valid, wrong password, unknown email), `POST /auth/refresh` (valid, expired), `POST /auth/logout`, `GET /auth/me` (valid token, expired → 401, invalid signature → 401, missing → 401), `PATCH /auth/me` (display_name, preferred_currency, invalid field → 400), `GET /auth/google` (redirect), `GET /auth/google/callback` (mocked code → token, invalid state → 400), `GET /me/export`, `DELETE /me`
- [X] T025 [P] [US1] Create `tests/e2e/api/fixtures/listing_ids.py` with a session-scoped fixture `listing_ids_by_country` that calls `seeded_ids` and extracts `listing_ids_by_country`; `fixtures/zone_ids.py` similarly
- [X] T026 [US1] Create `tests/e2e/api/test_listings.py` covering: `GET /listings` happy path (no filters), pagination (empty result, single page, exact boundary), each filter in isolation (country_code, city, min/max_price, min/max_area_m2, min/max_bedrooms, property_type, portal_id, sort_by), filter combinations (≥ 3 combos), `?currency=USD` returns prices in USD, free-tier 48h delay verified, `GET /listings/{id}` known ID, unknown → 404, basic-tier country restriction, `GET /listings/top-deals`
- [X] T027 [P] [US1] Create `tests/e2e/api/test_zones.py` covering: `GET /zones` with country filter + pagination, `POST /zones` (create custom zone with GeoJSON body, duplicate name → 409), `GET /zones/{id}` (known, unknown → 404), `GET /zones/{id}/stats`, `GET /zones/{id}/analytics`, `GET /zones/{id}/price-distribution`, `GET /zones/{id}/geometry`, `GET /zones/compare` (two IDs)
- [X] T028 [P] [US1] Create `tests/e2e/api/test_alerts.py` covering: `GET /alerts/rules`, `POST /alerts/rules` (create, free-tier limit enforcement → 403 when at limit), `PUT /alerts/rules/{id}` (own rule, other user's rule → 403), `DELETE /alerts/rules/{id}` (own, other user's → 403), `GET /alerts/history`
- [X] T029 [P] [US1] Create `tests/e2e/api/test_subscriptions.py` covering: `POST /subscriptions/checkout` returns URL, `POST /subscriptions/portal` returns URL, `GET /subscriptions/me` returns tier + renewal date, tier gating (free user cannot access pro-only listing → delayed response)
- [X] T030 [P] [US1] Create `tests/e2e/api/test_portfolio.py` covering: `GET /portfolio/properties` empty + populated states, `POST /portfolio/properties` (add listing), `PUT /portfolio/properties/{id}` (update CRM status: favorite, contacted, visited, offer_made, closed), `DELETE /portfolio/properties/{id}`
- [X] T031 [P] [US1] Create `tests/e2e/api/test_admin.py` covering: each admin endpoint returns 403 for non-admin user, each admin endpoint returns 200 for admin user: `GET /admin/scraping/stats`, `GET /admin/ml/models`, `POST /admin/ml/retrain`, `GET /admin/users` (pagination), `GET /admin/countries`, `PUT /admin/countries/{code}`, `GET /admin/system/health`
- [X] T032 [P] [US1] Create `tests/e2e/api/test_reference.py` covering: `GET /countries` (non-empty list, fields: `code`, `name`), `GET /portals` (non-empty list, fields: `id`, `name`, `country_code`)
- [X] T033 [P] [US1] Create `tests/e2e/api/test_ml.py` covering: `GET /model/estimate` with valid listing params → 200 with score + SHAP values, missing required param → 400
- [X] T034 [US1] Create `tests/e2e/api/test_rate_limiting.py` covering per-tier limits using async burst: for each tier (free=30, basic=120, pro=300, global=600, api=1200), send limit+5 requests to `GET /listings`, assert first N return 200 and limit+1 returns 429 with `Retry-After` header; run tier tests in parallel via `pytest-xdist -n 5` per research.md Decision 3
- [X] T035 [US1] Create `tests/e2e/api/test_errors.py` covering: 400 `VALIDATION_ERROR` shape with `details` array, 401 `UNAUTHORIZED`, 403 `FORBIDDEN`, 404 `NOT_FOUND`, 409 `CONFLICT`, 429 `RATE_LIMITED` + `Retry-After`, 500 `INTERNAL_ERROR` (no stack trace in response) per contracts/api-endpoints.md error shape section

**Checkpoint**: `make kind-test-api` passes. All documented REST endpoints covered at 100%.

---

## Phase 4: User Story 2 — WebSocket Chat Protocol (Priority: P1)

**Goal**: Validate full WebSocket lifecycle: auth, all message types, reconnection, keepalive, idle timeout, and 100-session concurrency.

**Independent Test**: `make kind-test-ws` (websocket sub-suite only) passes.

- [X] T036 [US2] Create `tests/e2e/websocket/test_connection.py` covering: valid JWT → successful handshake and `ws.open`, invalid JWT → close with code `4001`, expired JWT → close with code `4001`, missing token → close with code `4001`
- [X] T037 [US2] Create `tests/e2e/websocket/test_chat_protocol.py` covering: send `chat_message` → collect `text_chunk` messages until `is_final: true` → assert at least one `text_chunk` received → assert exactly one `criteria_summary` follows → assert `criteria_summary.payload.ready_to_search` is boolean; also test optional `chips` message type is a valid envelope when present
- [X] T038 [US2] Create `tests/e2e/websocket/test_image_carousel.py` covering: send `chat_message` with preference text → receive `image_carousel` message with `listings` array (each item has `listing_id`, `title`, `price_eur`, `photo_urls`) → send `image_feedback` with `action: "like"` → receive updated `criteria_summary` reflecting preference; assert `session_id` is echoed consistently
- [X] T039 [US2] Create `tests/e2e/websocket/test_deal_alert.py` covering: create alert rule for pro-tier user via API, connect WebSocket, use `nats_injector.publish_scored_listing()` with a listing matching the rule, assert `deal_alert` message received within 5 s, assert payload fields: `listing_id`, `deal_score`, `deal_tier`, `rule_name`, `triggered_at` per contracts/ws-protocol.md
- [X] T040 [US2] Create `tests/e2e/websocket/test_reconnection.py` covering: connect with `session_id=None` (new session), exchange one `chat_message` / `criteria_summary` pair, record `session_id` from response, close connection, reconnect using same `session_id` in the first `chat_message`, assert the server acknowledges the session (no re-introduction required, conversation history available)
- [X] T041 [US2] Create `tests/e2e/websocket/test_keepalive.py` covering: connect with valid JWT, verify that within `WS_PING_INTERVAL_SECS + 2` seconds (12 s in test env), the client receives a WebSocket ping frame; verify that the server closes with code `1001` after `WS_IDLE_TIMEOUT_SECS + 1` seconds (31 s in test env) of client silence; mark this test `@pytest.mark.slow` as it intentionally waits ~31 s

**Checkpoint**: `make kind-test-ws` (websocket/ subtree only) passes. All 7 WS scenarios covered.

---

## Phase 5: User Story 3 — Browser UI End-to-End Flows (Priority: P2)

**Goal**: Validate 10+ critical user flows in Chromium across auth, AI chat, search, listing detail, dashboard, map, alerts, subscriptions, and admin using Playwright Page Object Model.

**Independent Test**: `cd frontend && pnpm playwright test --project=chromium` passes all specs in `frontend/tests/e2e/specs/`.

### Page Objects (implement before specs that use them)

- [X] T042 [US3] Create `frontend/tests/e2e/pages/LandingPage.ts` with methods: `goto()`, `clickHeroCTA()`, `getPricingTiers()`, `getLoadTime()` (using `page.evaluate(() => performance.timing)`)
- [X] T043 [P] [US3] Create `frontend/tests/e2e/pages/LoginPage.ts` with `goto()`, `fillEmail(email)`, `fillPassword(pwd)`, `submit()`, `clickGoogleLogin()`, `getErrorMessage()`
- [X] T044 [P] [US3] Create `frontend/tests/e2e/pages/RegisterPage.ts` with `goto()`, `fillEmail()`, `fillPassword()`, `fillDisplayName()`, `submit()`, `getErrorMessage()`
- [X] T045 [P] [US3] Create `frontend/tests/e2e/pages/ChatPage.ts` with `goto()`, `sendMessage(text)`, `waitForAssistantResponse()`, `clickChip(label)`, `confirmCriteria()`, `getResultCount()`, `getStreamedText()` per plan.md Page Object Model example
- [X] T046 [P] [US3] Create `frontend/tests/e2e/pages/SearchPage.ts` with `goto()`, `setFilter(name, value)`, `getURLSearchParams()`, `getResultCount()`, `setSortOrder(field)`, `toggleGridView()`, `toggleListView()`, `saveSearch(name)`, `deleteSavedSearch(name)`
- [X] T047 [P] [US3] Create `frontend/tests/e2e/pages/ListingDetailPage.ts` with `goto(id)`, `isPhotoGalleryVisible()`, `isStatsVisible()`, `isSHAPChartVisible()`, `isPriceHistoryVisible()`, `isComparablesVisible()`, `isMapVisible()`, `clickTranslate()`, `setCRMStatus(status)`, `getCRMStatus()`
- [X] T048 [P] [US3] Create `frontend/tests/e2e/pages/DashboardPage.ts` with `goto()`, `getCardValue(label)`, `areChartsRendered()`, `switchCountryTab(countryCode)`
- [X] T049 [P] [US3] Create `frontend/tests/e2e/pages/AlertsPage.ts` with `goto()`, `createRule(params)`, `editRule(index, params)`, `deleteRule(index)`, `getHistoryEntries()`
- [X] T050 [P] [US3] Create `frontend/tests/e2e/pages/SubscriptionPage.ts` with `goto()`, `isUpgradePromptVisible()`, `clickUpgrade(tier)`, `waitForStripeRedirect()`
- [X] T051 [P] [US3] Create `frontend/tests/e2e/pages/AdminPage.ts` with `goto()`, `isAccessDenied()`, `getScrapingStats()`, `clickRetrain()`, `getUserListRows()`

### Spec Files

- [X] T052 [US3] Create `frontend/tests/e2e/specs/auth.spec.ts` covering: landing page loads in < 2 s (Performance API), hero CTA → `/register`, email/password registration → login redirect, email/password login → dashboard, Google OAuth (mocked via `mock-google-oauth.ts`) → token issued, logout → redirects to landing, all three browser projects
- [X] T053 [P] [US3] Create `frontend/tests/e2e/specs/ai-chat.spec.ts` covering: type query → see streamed `text_chunk` tokens appear progressively in DOM, voice input button triggers mocked recognition (via `mock-voice.ts`) and populates input, click chip → criteria updates, confirm criteria → search runs → `[data-testid="listing-card"]` count > 0, alert auto-created → navigating to alerts page shows new rule
- [X] T054 [P] [US3] Create `frontend/tests/e2e/specs/search.spec.ts` covering: set filter → URL search params update, results re-fetch on filter change (use `waitForResponse`), sort change → first result changes, grid view toggle → `.grid-layout` visible, list view toggle → `.list-layout` visible, save search → appears in saved searches, delete saved search → removed
- [X] T055 [P] [US3] Create `frontend/tests/e2e/specs/listing-detail.spec.ts` covering: all six sections render (`photo-gallery`, `stats-panel`, `shap-chart`, `price-history`, `comparables`, `map-embed`), photo gallery is swipeable on mobile viewport (375×667), translate button renders translated description, CRM status actions (favorite, contacted, visited) persist after page reload
- [X] T056 [P] [US3] Create `frontend/tests/e2e/specs/dashboard.spec.ts` covering: stat cards render with numeric values, Recharts `<svg>` elements present (charts rendered), switching country tab fires API request with `country_code` param and updates card values
- [X] T057 [P] [US3] Create `frontend/tests/e2e/specs/map.spec.ts` covering: zoom in/out via controls → `map-zoom-level` changes, click marker → popup with `[data-testid="mini-listing-card"]` appears, draw custom zone → `POST /api/v1/zones` called and new zone appears in list, pan map → new `GET /api/v1/listings` request fired
- [X] T058 [P] [US3] Create `frontend/tests/e2e/specs/alerts.spec.ts` covering: create alert rule form → rule appears in list, edit rule → persisted after reload, delete rule → confirmation dialog → rule removed, alert history tab shows past trigger rows
- [X] T059 [P] [US3] Create `frontend/tests/e2e/specs/subscription.spec.ts` covering: free-user sees upgrade prompts on pro-restricted content, click upgrade → Stripe Checkout page (mocked via `mock-stripe.ts`), simulated `checkout.session.completed` webhook → API tier updated → UI reflects new tier without page reload
- [X] T060 [P] [US3] Create `frontend/tests/e2e/specs/admin.spec.ts` covering: non-admin user navigating to `/admin` sees 403/access-denied state, admin user sees scraping stats table, admin user clicks retrain → success toast, admin user sees paginated user list (page 2 loads different rows)
- [X] T061 [P] [US3] Create `frontend/tests/e2e/specs/responsive.spec.ts` covering: at 375×667 (mobile) sidebar collapses and nav hamburger is visible + functional, at 768×1024 (tablet) layout adapts (sidebar visible but compressed), both viewports run on Chromium only

**Checkpoint**: `cd frontend && pnpm playwright test --project=chromium` passes all 10 spec files. 10+ user flows verified.

---

## Phase 6: User Story 4 — Multi-User Concurrency (Priority: P2)

**Goal**: Demonstrate 100 simultaneous WebSocket sessions and multi-user concurrent API operations without errors or cross-talk.

**Independent Test**: `make kind-test-ws` (concurrency sub-suite) passes all 4 concurrency test files.

- [X] T062 [US4] Create `tests/e2e/concurrency/test_concurrent_search.py` covering: two pro-tier users (different `authed_client` instances) concurrently send `GET /listings?country_code=ES` via `asyncio.gather`; assert both receive identical `total_count` and non-empty `listings` lists; no 500 or 429 errors
- [X] T063 [US4] Create `tests/e2e/concurrency/test_concurrent_alerts.py` covering: two pro-tier users (distinct UUIDs) concurrently `POST /alerts/rules` for the same listing criteria; inject a scored listing via `nats_injector`; assert each user's WebSocket receives only their own `deal_alert` message (correct `user_id` in payload, no cross-delivery)
- [X] T064 [US4] Create `tests/e2e/concurrency/test_concurrent_crm.py` covering: user A calls `PUT /portfolio/properties/{id}` (CRM status update) while user B calls `GET /listings/{id}` concurrently; assert both complete with 200; assert user A's CRM status change is reflected in a subsequent `GET /portfolio/properties` without corruption
- [X] T065 [US4] Create `tests/e2e/concurrency/test_concurrent_chat.py` covering: spawn 100 `WSTestClient` instances concurrently (using `asyncio.gather`), each connecting with the `pro` tier JWT; send a distinct `chat_message` from each (e.g. include client index in the message text); collect each client's `criteria_summary`; assert all 100 received exactly one `criteria_summary`; assert no client received another client's `session_id` in the response (no cross-talk); assert zero connection errors

**Checkpoint**: `make kind-test-ws` (including concurrency/) passes. 100-session concurrency verified.

---

## Phase 7: User Story 5 — Visual Regression & Accessibility (Priority: P3)

**Goal**: Capture approved visual baselines for 5 key pages and verify WCAG AA accessibility on all primary pages.

**Independent Test**: `make kind-test-visual` and `make kind-test-a11y` pass. Baseline PNGs committed to repo.

- [X] T066 [US5] Create `frontend/tests/e2e/specs/accessibility.spec.ts` using `axe-playwright` (add to `package.json` devDependencies): scan each primary page (landing, login, chat, search, listing detail, dashboard, alerts, subscription, admin-denied) with `checkA11y(page, undefined, { runOnly: ['wcag2a', 'wcag2aa'] })`; assert zero violations; also verify keyboard navigation (Tab through all interactive elements, Enter activates focused element) on landing, login, and chat pages; mark each test `@a11y`
- [X] T067 [US5] Create `frontend/tests/e2e/visual/visual-regression.spec.ts` using `toHaveScreenshot()` at 0.1% threshold for five pages on Chromium only: (1) home page logged-out, (2) home page logged-in (pro-tier user), (3) dashboard, (4) listing detail (first seeded ES listing), (5) AI chat mid-conversation (after one exchange); use `page.waitForLoadState('networkidle')` before each snapshot
- [ ] T068 [US5] Add `axe-playwright` and `@axe-core/playwright` to `frontend/package.json` devDependencies and run `pnpm install` to update lockfile
- [ ] T069 [US5] Generate initial visual baselines by running `cd frontend && pnpm playwright test visual/ --project=chromium --update-snapshots` and commit the resulting PNG files in `frontend/tests/e2e/visual/baselines/chromium/` (5 files, one per page)
- [ ] T070 [US5] Verify visual regression tests pass (baseline comparison, not update) by running `cd frontend && pnpm playwright test visual/ --project=chromium` and confirming all 5 `toHaveScreenshot()` assertions pass against the committed baselines

**Checkpoint**: `make kind-test-visual` and `make kind-test-a11y` both pass. Baseline PNGs committed.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: CI sharding, GitHub Actions integration, and final validation of the complete suite within the 20-minute budget.

- [X] T071 Create `.github/workflows/e2e.yml` defining a matrix job with `shard: [1, 2, 3, 4]`; Python E2E tests sharded with `pytest-xdist -n auto --dist=loadscope`; Playwright tests sharded with `--shard=${{ matrix.shard }}/4`; artifact upload step for `reports/e2e/` and `frontend/playwright-report/` with 30-day retention; trigger on PR and push to main; requires `kind-up`, `kind-build`, `kind-load`, `kind-deploy`, `kind-seed` steps before running tests
- [X] T072 Add `reports/e2e/` to `.gitignore` (generated artifacts) and add `frontend/tests/e2e/auth/*.json` to `.gitignore` (per-run storageState files); add `frontend/tests/e2e/visual/baselines/` to `.gitignore` negation so baselines **are** tracked: `!frontend/tests/e2e/visual/baselines/**/*.png`
- [ ] T073 [P] Run `make kind-test` end-to-end timing measurement; confirm the full suite completes in < 20 minutes on the local machine; document any slow tests with `@pytest.mark.slow` marker in Python and `test.slow()` annotation in Playwright
- [ ] T074 [P] Run `cd tests/e2e && uv run ruff check . && uv run mypy --strict helpers/` to verify Python test code passes linting and type checks; fix any violations found
- [X] T075 Update `specs/030-test-coverage-infrastructure/plan.md` to note that the E2E test suite is now in `031-e2e-test-suite` and that `make kind-test` now invokes the full E2E sub-suite rather than only helm tests

**Checkpoint**: Full `make kind-test` completes in < 20 min. CI workflow configured. Lint passes.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Requires Phase 1 — **BLOCKS all user story phases**
- **US1 REST API (Phase 3)**: Requires Phase 2 — can run in parallel with US2
- **US2 WebSocket (Phase 4)**: Requires Phase 2 — can run in parallel with US1
- **US3 Browser UI (Phase 5)**: Requires Phase 2 — can run in parallel with US1/US2; Page objects (T042–T051) must precede their specs
- **US4 Concurrency (Phase 6)**: Requires Phase 2 + Phase 4 (shares `nats_injector` and `WSTestClient`)
- **US5 Visual/A11y (Phase 7)**: Requires Phase 5 (visual spec shares pages; a11y spec adds new assertions)
- **Polish (Phase 8)**: Requires all prior phases complete

### User Story Dependencies

| Story | Depends On | Can Parallelize With |
|-------|-----------|---------------------|
| US1 REST API | Phase 2 complete | US2, US3 |
| US2 WebSocket | Phase 2 complete | US1, US3 |
| US3 Browser UI | Phase 2 complete (page objects first) | US1, US2 |
| US4 Concurrency | Phase 2 + US2 (WSTestClient patterns) | US3, after US2 |
| US5 Visual/A11y | US3 complete (pages reused) | — |

### Within Each User Story

- Foundational helpers before test files that use them
- `conftest.py` before test files in the same directory
- Page objects before spec files that import them
- Spec files within a story can be written in parallel (`[P]` marked)

---

## Parallel Execution Examples

### Phase 2 (Foundational) — parallel group

```
Task: T006  helpers/client.py
Task: T007  helpers/ws_client.py
Task: T008  helpers/assertions.py
Task: T009  helpers/fixtures.py
Task: T010  helpers/nats_injector.py
Task: T011  helpers/redis_reset.py
Task: T016  fixtures/users.ts
Task: T017  fixtures/auth.ts
Task: T019  utils/mock-stripe.ts
Task: T020  utils/mock-google-oauth.ts
Task: T021  utils/mock-voice.ts
# Then sequentially: T012, T013, T014, T015, T018, T022, T023
```

### Phase 3 (US1) — parallel group after T024 (test_auth.py)

```
Task: T026  test_listings.py
Task: T027  test_zones.py
Task: T028  test_alerts.py
Task: T029  test_subscriptions.py
Task: T030  test_portfolio.py
Task: T031  test_admin.py
Task: T032  test_reference.py
Task: T033  test_ml.py
# Then T034 (rate limiting) and T035 (errors) after conftest confirmed working
```

### Phase 5 (US3) — parallel group after T042–T051 (page objects)

```
Task: T053  ai-chat.spec.ts
Task: T054  search.spec.ts
Task: T055  listing-detail.spec.ts
Task: T056  dashboard.spec.ts
Task: T057  map.spec.ts
Task: T058  alerts.spec.ts
Task: T059  subscription.spec.ts
Task: T060  admin.spec.ts
Task: T061  responsive.spec.ts
```

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1 REST API tests
4. Complete Phase 4: US2 WebSocket tests
5. **STOP and VALIDATE**: `make kind-test-api && make kind-test-ws` both pass
6. API and WS confidence established — deploy to team

### Incremental Delivery

1. Phase 1 + 2 → Infrastructure ready
2. Phase 3 (US1) → REST API validated → `make kind-test-api` green ✓
3. Phase 4 (US2) → WebSocket validated → `make kind-test-ws` green ✓
4. Phase 5 (US3) → Browser UI validated → `cd frontend && pnpm playwright test` green ✓
5. Phase 6 (US4) → Concurrency validated → `make kind-test` green ✓
6. Phase 7 (US5) → Visual + a11y validated → baselines committed ✓
7. Phase 8 → CI configured, timing verified < 20 min ✓

### Parallel Team Strategy

With three developers after Phase 2 completes:

- **Dev A**: US1 REST API (Phase 3) — pure Python, httpx-based
- **Dev B**: US2 WebSocket (Phase 4) + US4 Concurrency (Phase 6)
- **Dev C**: US3 Browser UI (Phase 5) page objects then specs
- All three merge → Dev C + polish continues with US5

---

## Notes

- `[P]` tasks involve different files with no blocking dependencies — safe to implement concurrently
- `[US1]–[US5]` labels map to user stories in `spec.md` for traceability
- Tests live outside `services/` and MUST NOT import service-internal packages
- `WS_IDLE_TIMEOUT_SECS=30` in `values-test.yaml` must be applied via `make kind-deploy` before running T041
- Visual baselines (T069) must be generated on a stable build then committed — never auto-regenerated in CI
- `@pytest.mark.slow` marks the keepalive/idle test (T041, ~31 s); exclude from fast feedback loop with `-m "not slow"`
- Rate limit tests (T034) use `pytest-xdist -n 5` parallelism; ensure `TEST_RUN_ID` isolation prevents token-sharing between tier tests
