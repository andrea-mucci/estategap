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

---

---

# User Journey Tests — Implementation Tasks

**Branch**: `032-e2e-user-journeys`
**Extends**: Tasks above (031-e2e-test-suite) which are complete
**Scope**: 15 user journey tests in `tests/usecase/`

---

## Phase 9: User Journey Infrastructure (UJ Scaffold + Helpers)

**Purpose**: Create the `tests/usecase/` project and all shared helpers that every journey test depends on.

**⚠️ CRITICAL**: All phases 10–13 are blocked until this phase is complete.

- [ ] T076 Create `tests/usecase/` directory and `tests/usecase/pyproject.toml` as a standalone uv project with dependencies: `playwright>=1.43`, `asyncpg>=0.29`, `kubernetes>=29.0`, `httpx>=0.27`, `nats-py>=2.6`, `websockets>=12.0`, `redis>=5.0`, `pydantic>=2.8`, `pytest>=8.2`, `pytest-asyncio>=0.23`, `ruff>=0.6`, `mypy>=1.11`; set `[tool.uv] package = false`; copy ruff/mypy config from `tests/e2e/pyproject.toml`

- [ ] T077 Create `tests/usecase/pytest.ini` with: `asyncio_mode = auto`, markers `usecase`, `browser`, `slow`, `api`, `testpaths = .`, `python_files = uj*_test.py`, `python_classes = TestUJ*`, `python_functions = test_*`, `timeout = 300`, `log_cli = true`, `log_cli_level = INFO`

- [ ] T078 Create `tests/usecase/conftest.py` with: (1) `sys.path` insert for `REPO_ROOT` and `tests/e2e/` so `tests/e2e/helpers/` is importable; (2) session-scoped `cluster` async fixture that instantiates `ClusterHelper` from `helpers/cluster.py`, calls `assert helper.is_ready()` and `assert helper.fixtures_loaded()`; (3) function-scoped `test_context` async fixture that creates `TestContext(cluster=cluster, test_name=request.node.name, run_id=uuid4().hex[:8])`, yields it, calls `await context.cleanup()` in teardown, and calls `await context.collect_failure_artifacts()` if `request.node.rep_call.failed` (use `pytest_runtest_makereport` hook to set `rep_call`); (4) `env_url` session fixture reading `GATEWAY_URL` (default `http://localhost:8080`), `WS_URL` (default `ws://localhost:8081`), `FRONTEND_URL` (default `http://localhost:3000`), `NATS_URL` (default `nats://localhost:4222`), `REDIS_URL` (default `redis://localhost:6379`), `GATEWAY_DB_DSN`

- [ ] T079 [P] Create `tests/usecase/helpers/__init__.py` (empty); create `tests/usecase/helpers/api.py` implementing `ApiClient` with: `classmethod login(base_url, email, password) -> ApiClient` (calls `POST /api/v1/auth/login`, stores `access_token`, exposes `user: dict`); methods `create_alert_rule(payload) -> dict`, `delete_alert_rule(rule_id)`, `create_portfolio_item(payload) -> dict`, `delete_portfolio_item(item_id)`, `set_language_preference(lang: str)`, `set_currency_preference(currency: str)`, `get_listings(params: dict) -> dict`, `get_listing(id) -> dict`, `simulate_stripe_webhook(event_type: str, user_id: str, tier: str)`, `export_user_data() -> bytes`, `delete_account()`, `get_alert_rules() -> list`; wraps `AsyncAPIClient` from `tests/e2e/helpers/client.py`

- [ ] T080 [P] Create `tests/usecase/helpers/ws.py` that re-exports `WSTestClient` from `tests/e2e/helpers/ws_client`; adds `collect_until_type(ws, msg_type, timeout=30) -> list[dict]` helper that reads messages until `msg["type"] == msg_type` and returns all collected messages; adds `collect_deal_alerts(ws, timeout=30) -> list[dict]` that collects until a `deal_alert` type arrives or timeout

- [ ] T081 [P] Create `tests/usecase/helpers/cluster.py` implementing `ClusterHelper` with `__init__(namespace="estategap-system")`; `is_ready() -> bool`: runs `kubectl get pods -n {namespace} --field-selector=status.phase!=Running -o name` and returns True if output is empty; `fixtures_loaded() -> bool`: calls `kubectl exec -n {namespace} deploy/api-gateway -- wget -qO- http://localhost:8080/api/v1/listings?limit=1` and checks `total_count > 0` in JSON; `pod_logs(deployment: str, lines: int = 200) -> str`: runs `kubectl logs -n {namespace} deploy/{deployment} --tail={lines}`; `job_status(job_name: str) -> str`: parses `kubectl get job {job_name} -n {namespace} -o json` and returns `"succeeded"` / `"failed"` / `"running"`; `wait_for_job(job_name, timeout_seconds=300) -> bool`: polls `job_status()` every 10s until `succeeded` or `failed` or timeout; `exec_in_pod(deployment: str, cmd: list[str]) -> str`: runs `kubectl exec -n {namespace} deploy/{deployment} -- {cmd}`; all subprocess calls use `subprocess.run(..., capture_output=True, text=True, timeout=60)`

- [ ] T082 [P] Create `tests/usecase/helpers/db.py` implementing `DbClient` as an async context manager; `__init__(dsn: str)` reads from `GATEWAY_DB_DSN` env; `async connect()` creates `asyncpg.create_pool(dsn, min_size=1, max_size=5)`; `async fetch(sql, *args) -> list[asyncpg.Record]`; `async fetchrow(sql, *args) -> asyncpg.Record`; `async execute(sql, *args)`; `async cleanup_by_run_id(run_id: str)`: deletes `listings` WHERE `source_id LIKE 'uj%-{run_id}-%'`, deletes `alert_rules` WHERE `name LIKE '%-{run_id}%'`, deletes `portfolio_properties` WHERE `name LIKE '{run_id}%'`; `async close()`: closes pool; class-level `@classmethod async def connect_from_env() -> DbClient`

- [ ] T083 [P] Create `tests/usecase/helpers/fixtures.py` implementing: `async publish_raw_listing(nats_url: str, listing: dict) -> None` that connects `nats.aio.client.Client`, publishes `json.dumps(listing).encode()` to `raw.listings.{listing["country"].lower()}`, flushes and drains; `async inject_price_update(nats_url: str, listing_id: str, new_price_eur: float) -> None` that publishes a price-change event to `price.changes` subject with `{"listing_id": ..., "old_price_eur": ..., "new_price_eur": ..., "change_pct": ...}`; `def make_test_listing(run_id: str, seq: int, *, country="ES", city="Madrid", zone_id: str, asking_price: int = 450000, bedrooms: int = 2, property_type: str = "flat") -> dict`: returns a full raw listing dict with `source_id = f"uj-{run_id}-{seq:03d}"`, `source = "test-fixture"`, `published_at = datetime.now(UTC).isoformat()`

- [ ] T084 [P] Create `tests/usecase/helpers/spies.py` implementing `EmailSpy` and `TelegramSpy`; both take `redis_url: str` in `__init__` and lazy-connect via `redis.asyncio.from_url(redis_url)`; `EmailSpy.received_for(email: str) -> bool`: checks `LLEN spy:email:{urllib.parse.quote(email, safe="")} > 0`; `EmailSpy.get_messages(email: str) -> list[dict]`: `LRANGE` all entries, JSON-decode each; `EmailSpy.clear(email: str)`: `DEL spy:email:{email}`; same pattern for `TelegramSpy` with key `spy:telegram:{chat_id}`; add `async def wait_for_spy(spy_fn, timeout=30, poll_interval=1) -> bool` helper that polls `spy_fn()` until True or timeout

- [ ] T085 [P] Create `tests/usecase/helpers/time_travel.py` implementing `TimeTravel` with `configmap = "estategap-runtime"`, `namespace = "estategap-system"`, `affected_deployments = ["api-gateway", "alert-engine"]`; `async set_time(timestamp: datetime)`: runs `kubectl patch configmap {configmap} -n {namespace} --type merge -p '{json.dumps({"data":{"NOW_OVERRIDE": timestamp.isoformat()}})}'`; then for each deployment: `kubectl rollout restart deployment/{d} -n {namespace}` and `kubectl rollout status deployment/{d} -n {namespace} --timeout=3m`; `async advance_hours(n: int)`: calls `get_time()` + `timedelta(hours=n)` then `set_time()`; `async get_time() -> datetime`: runs `kubectl get configmap {configmap} -n {namespace} -o jsonpath='{.data.NOW_OVERRIDE}'` and parses ISO datetime; `async reset()`: removes `NOW_OVERRIDE` key with `kubectl patch configmap ... -p '{"data":{"NOW_OVERRIDE":null}}'` and restarts affected deployments

- [ ] T086 [P] Create `tests/usecase/helpers/browser.py` implementing `BrowserHelper` using `playwright.async_api.async_playwright`; `__init__(base_url: str, headless: bool = True)`; `async start() -> BrowserHelper`: launches `chromium.launch(headless=headless)`, creates context with `viewport={"width":1280,"height":800}`; `async stop()`; use as async context manager; `async goto(path: str)`: `page.goto(f"{base_url}{path}", wait_until="networkidle")`; `async login(email: str, password: str)`: fills `[data-testid="email-input"]`, `[data-testid="password-input"]`, clicks `[data-testid="login-submit"]`, waits for URL to contain `/dashboard`; `async screenshot(name: str, artifacts_dir: Path) -> Path`: saves to `artifacts_dir / f"{name}.png"`; `@property page -> Page`; `PLAYWRIGHT_HEADLESS` env var overrides `headless` default

- [ ] T087 [P] Create `tests/usecase/helpers/assertions.py` with: `BASELINES: dict[str, float] = {"uj02_search_to_detail": 3.0, "uj03_alert_latency": 15.0, "uj04_ai_to_alert": 30.0, "uj07_retrain_active": 180.0, "uj15_scrape_to_alert": 90.0}`; `REGRESSION_THRESHOLD = 1.20`; `def assert_within_baseline(test_name: str, actual: float) -> None`: if `actual > BASELINES[test_name] * REGRESSION_THRESHOLD` call `pytest.fail(...)`, elif `actual > BASELINES[test_name]` call `warnings.warn(...)`; `def assert_deal_tier(listing: dict, expected_tier: int)`: asserts `listing["deal_tier"] == expected_tier`; `def assert_gdpr_anonymized(user_row: asyncpg.Record)`: asserts `user_row["email"].startswith("deleted-")` and `user_row["email"].endswith("@estategap.test")` and `user_row["display_name"] is None`; `def assert_search_results_contain_countries(results: list[dict], expected_countries: list[str])`: checks each country appears at least once

**Checkpoint**: `cd tests/usecase && uv sync && uv run pytest --collect-only` succeeds with no import errors.

---

## Phase 10: Core Multi-Service Journey Tests

**Purpose**: Implement the six journey tests that exercise the full backend pipeline, multi-channel notifications, and time-sensitive business rules. These are API/NATS-only (no browser).

**Goal**: `pytest -m "usecase and api and not slow"` passes for UJ-03, UJ-09, UJ-11, UJ-15; `pytest -m "usecase and slow"` passes for UJ-08.

- [ ] T088 [US1] Create `tests/usecase/uj03_alert_notification_test.py` implementing `TestUJ03AlertNotification` with `@pytest.mark.usecase @pytest.mark.api`; `test_alert_multi_channel(test_context, env_url)`: (Given) `ApiClient.login(pro_user)`, `create_alert_rule({country=ES, zone_id=chamberí_zone_id, property_type=flat, max_price=600000, min_deal_tier=2, channels=[email,telegram,websocket], frequency=instant})`; (When) connect `WSTestClient`, start `asyncio.Task` collecting WS messages, instantiate `EmailSpy` and `TelegramSpy`, call `publish_raw_listing(nats_url, make_test_listing(run_id, zone_id=chamberí_zone_id))`; (Then) poll all three spies with 60s deadline using `asyncio.sleep(1)` loop; assert all three received; assert `latency < 60`; call `assert_within_baseline("uj03_alert_latency", latency)`; verify `alert_log` rows via `DbClient.fetch("SELECT channel FROM alert_log WHERE rule_id=$1", rule_id)` shows all three channels; resolve `chamberí_zone_id` at test start via `GET /api/v1/zones?country=ES&name=Chamberí`

- [ ] T089 [US1] Create `tests/usecase/uj15_scrape_to_alert_latency_test.py` implementing `TestUJ15ScrapeToAlertLatency` with `@pytest.mark.usecase @pytest.mark.api`; `test_end_to_end_latency(test_context, env_url)`: (Given) create alert rule for pro user (ES, any zone, flat, max 800k, min_tier=1), connect WS spy task; (When) `start = time.monotonic()`, publish raw listing to NATS `raw.listings.es` and wait for `deal_alert` WS message via `collect_deal_alerts(ws, timeout=120)`; (Then) `latency = time.monotonic() - start`; assert `ws_hit` received; `assert_within_baseline("uj15_scrape_to_alert", latency)`; assert listing now exists in DB via `fetchrow("SELECT deal_tier FROM listings WHERE source_id=$1", source_id)` with tier 1 or 2; assert `alert_log` row exists

- [ ] T090 [US1] Create `tests/usecase/uj11_price_drop_engagement_test.py` implementing `TestUJ11PriceDropEngagement` with `@pytest.mark.usecase @pytest.mark.api`; `test_price_drop_triggers_alert(test_context, env_url)`: (Given) pro user with alert rule (min_tier=1, channels=[email,websocket]); seed a test listing with `deal_tier=2`, `asking_price=550000` by publishing a raw listing and waiting for it to appear in `GET /listings`; (When) connect WS, `inject_price_update(nats_url, listing_id, new_price_eur=520000)` which triggers re-scoring and re-dispatch; poll `EmailSpy` and WS messages for up to 60s; (Then) assert email received with payload containing `listing_id`; assert WS `deal_alert` received; verify `deal_tier` in DB updated to 1; assert email payload has `tracking_url` field; simulate click by calling `GET {tracking_url}` and assert 200; verify CRM status can be set to `contacted` via `PUT /api/v1/portfolio/properties/{prop_id}` returning 200

- [ ] T091 [US2] Create `tests/usecase/uj04_ai_chat_to_alert_test.py` implementing `TestUJ04AIChatToAlert` with `@pytest.mark.usecase @pytest.mark.api`; `test_conversational_search_creates_alert(test_context, env_url)`: (Given) `ApiClient.login(pro_user)`; (When) connect `WSTestClient(ws_url, token=api.access_token)`, send `chat_message` with text `"I'm looking for a 2-bedroom apartment in Madrid, under 500k, renovated"`; collect messages until `criteria_summary` received (`collect_messages(until_type="criteria_summary", timeout=30)`); send chip confirmation for zone `Chamberí` via `send_criteria_confirm(confirmed=True)` with notes `"zone: Chamberí, timing: this_year"`; collect next `criteria_summary`; (Then) assert `criteria_summary.payload.ready_to_search == True`; call `GET /api/v1/listings` with criteria params from summary, assert `total >= 5`; assert `GET /api/v1/alerts/rules` returns at least one rule matching the chat criteria; `assert latency < 60`; `assert_within_baseline("uj04_ai_to_alert", latency)` where latency measures from first `send_chat` to alert rule visible in API

- [ ] T092 [US1] Create `tests/usecase/uj08_free_tier_delay_test.py` implementing `TestUJ08FreeTierDelay` with `@pytest.mark.usecase @pytest.mark.api @pytest.mark.slow`; `test_free_tier_delay(test_context, env_url)`: (Given) free user, `TimeTravel` instance; publish raw listing with `published_at = now()` and wait for pipeline to process it (poll `GET /listings?country=ES` until source_id appears for pro user, up to 60s); (When) free user calls `GET /api/v1/listings?country=ES` — assert the just-published listing does NOT appear (its `published_at` is < 48h ago); `TimeTravel.advance_hours(49)`, wait for pods to restart; free user retries `GET /api/v1/listings?country=ES` — assert listing NOW appears; (Then) assert `advance_hours` added exactly ~49h; call `TimeTravel.reset()` in teardown to restore real time; mark test as `slow` since pod restarts add ~60s

- [ ] T093 [US3] Create `tests/usecase/uj05_subscription_upgrade_test.py` implementing `TestUJ05SubscriptionUpgrade` with `@pytest.mark.usecase @pytest.mark.api`; `test_basic_to_pro_upgrade(test_context, env_url)`: (Given) `ApiClient.login(basic_user)`; create 3 alert rules (loop); assert each succeeds with 201; (When) attempt 4th rule — assert response is 403 with body containing `"upgrade"` or `"Pro"` or `"limit"`; call `api.simulate_stripe_webhook(event_type="checkout.session.completed", user_id=api.user["id"], tier="pro")`; (Then) poll `GET /api/v1/subscriptions/me` until `tier == "pro"` or 10s; retry 4th alert rule creation — assert 201; total alert rules now 4; clean up all rules in teardown via `test_context`; note: webhook simulation calls `POST /api/v1/subscriptions/webhook` with pre-signed test payload defined in `helpers/api.py::simulate_stripe_webhook`

**Checkpoint**: `pytest tests/usecase -m "usecase and api" -v` passes for UJ-03, UJ-05, UJ-09, UJ-11, UJ-15; `pytest -m slow` passes for UJ-08 (may take 3–4 minutes due to pod restarts).

---

## Phase 11: Browser-Based Journey Tests

**Purpose**: Implement the five journey tests that require Playwright browser automation for user-facing flows.

**Goal**: `pytest -m "usecase and browser" -v` passes for UJ-01, UJ-02, UJ-06, UJ-07, UJ-10.

- [ ] T094 [US3] Create `tests/usecase/uj01_onboarding_test.py` implementing `TestUJ01Onboarding` with `@pytest.mark.usecase @pytest.mark.browser`; `test_new_user_registration_to_dashboard(test_context, env_url)`: (Given) `BrowserHelper(base_url=FRONTEND_URL)` started; generate unique email `f"uj01-{test_context.run_id}@estategap.test"`; (When) `browser.goto("/register")`; fill `[data-testid="email-input"]`, `[data-testid="password-input"]`, `[data-testid="display-name-input"]`; click `[data-testid="register-submit"]`; wait for URL to contain `/onboarding`; click through onboarding tour (next buttons, up to 5 steps); wait for URL to contain `/dashboard`; (Then) assert `page.url` contains `/dashboard`; assert `[data-testid="dashboard-welcome"]` visible; verify user exists in DB via `DbClient.fetchrow("SELECT id FROM users WHERE email=$1", email)`; call `browser.screenshot("dashboard_reached", artifacts_dir)` for evidence; cleanup: `DELETE /api/v1/me` using new user's token

- [ ] T095 [US3] Create `tests/usecase/uj02_find_deal_test.py` implementing `TestUJ02FindDeal` with `@pytest.mark.usecase @pytest.mark.browser`; `test_search_tier1_deal_to_detail(test_context, env_url)`: (Given) `ApiClient.login(pro_user)`, `BrowserHelper` with pro user session injected via `browser.page.set_extra_http_headers({"Authorization": f"Bearer {api.access_token}"})`; `start = time.monotonic()`; (When) `browser.goto("/search")`; set filter `country=ES`, `city=Madrid`, `deal_tier=1`; wait for `[data-testid="listing-card"]` elements to appear; click first card; wait for URL to match `/listings/`; assert detail page loads: `[data-testid="price-display"]` visible, `[data-testid="estimated-value"]` visible, `[data-testid="confidence-range"]` visible, `[data-testid="shap-chart"]` visible (contains ≥ 5 factor rows), `[data-testid="comparable-card"]` elements count ≥ 5; `latency = time.monotonic() - start`; (Then) `assert latency < 5`; `assert_within_baseline("uj02_search_to_detail", latency)` — note: latency for UJ-02 covers the full browser flow from filter to detail page loaded

- [ ] T096 [US3] Create `tests/usecase/uj06_portfolio_multi_currency_test.py` implementing `TestUJ06PortfolioMultiCurrency` with `@pytest.mark.usecase @pytest.mark.browser`; `test_portfolio_tracking_currency_switch(test_context, env_url)`: (Given) `ApiClient.login(pro_user)`, `BrowserHelper`; (When) `browser.goto("/portfolio")`; add 3 owned properties via API: `Madrid €450000 purchased 2020`, `London £350000 purchased 2022`, `Paris €600000 purchased 2023` (using `POST /api/v1/portfolio/properties`); reload portfolio page; assert all 3 cards visible, each has `[data-testid="ml-estimated-value"]` showing a value > 0, `[data-testid="gain-loss"]` showing ±% figure; assert `[data-testid="total-portfolio-value"]` visible with non-zero EUR amount; (Then) call `api.set_currency_preference("USD")`, reload page; assert prices now display `$` symbol; verify total value is reconverted (> 0, different numeric than EUR)

- [ ] T097 [US3] Create `tests/usecase/uj07_admin_retrain_ml_test.py` implementing `TestUJ07AdminRetrain` with `@pytest.mark.usecase @pytest.mark.browser @pytest.mark.slow`; `test_manual_model_retrain(test_context, env_url)`: (Given) `ApiClient.login(admin_user)`, `BrowserHelper`, `ClusterHelper()`; (When) `browser.goto("/admin")`; click "ML Models" tab; assert `[data-testid="current-model-mape"]` visible; click `[data-testid="retrain-now-btn"]`; assert toast/status shows "Retraining started"; wait up to 3 minutes for `[data-testid="model-status"]` to show "active" for a new version (poll with `page.wait_for_selector` every 10s); (Then) verify K8s Job completed via `cluster.job_status("ml-retrain-job")` returns `"succeeded"`; call `GET /api/v1/model/estimate` with valid params and assert response uses new `model_version` field value; `assert_within_baseline("uj07_retrain_active", elapsed)` where elapsed = time from retrain click to model active

- [ ] T098 [US3] Create `tests/usecase/uj10_gdpr_export_delete_test.py` implementing `TestUJ10GDPRExportDelete` with `@pytest.mark.usecase @pytest.mark.browser`; `test_gdpr_export_then_delete(test_context, env_url)`: (Given) create a fresh user `uj10-{run_id}@estategap.test` via register API; login; create 1 alert rule, 1 portfolio item, send 1 WS chat message to create conversation history; (When) `browser.goto("/settings")`, click `[data-testid="export-data-btn"]`, wait for download event using `page.expect_download()`, save to temp file; assert downloaded JSON contains keys `profile`, `conversations`, `alert_rules`, `portfolio`, `alert_history`; assert download completed within 30s; click `[data-testid="delete-account-btn"]`, click `[data-testid="confirm-delete-btn"]` in dialog; wait for redirect to `/` (logged out); (Then) attempt login with original credentials via API — assert 401; verify DB via `DbClient.fetchrow("SELECT email FROM users WHERE email LIKE 'uj10-%'")` — assert email starts with `deleted-` and ends with `@estategap.test` (PII anonymized via `assert_gdpr_anonymized`)

**Checkpoint**: `pytest tests/usecase -m "usecase and browser" -v` passes for UJ-01, UJ-02, UJ-06, UJ-07, UJ-10 (UJ-07 and UJ-10 may take 2–3 minutes).

---

## Phase 12: Remaining Journey Tests

**Purpose**: Implement the final six journey tests covering multi-country search, i18n, scraping recovery, WebSocket reconnection, and portfolio features. These can be implemented in parallel.

- [ ] T099 [P] [US1] Create `tests/usecase/uj09_multi_country_search_test.py` implementing `TestUJ09MultiCountrySearch` with `@pytest.mark.usecase @pytest.mark.api`; `test_search_across_countries_with_currency_switch(test_context, env_url)`: (Given) `ApiClient.login(pro_user)` where pro_user has `allowed_countries=["ES","IT","FR"]`; (When) call `GET /api/v1/listings` with no country filter; (Then) assert response `data` contains listings with `country_code` values including `ES`, `IT`, `FR` (at least one each — use seeded data); assert all prices have `currency` field; call `api.set_currency_preference("EUR")`, re-fetch — assert prices display in EUR; call `api.set_currency_preference("GBP")`, re-fetch — assert `currency == "GBP"` in response and numeric values differ from EUR amounts; assert listing `prices.gbp` field is present and > 0

- [ ] T100 [P] [US3] Create `tests/usecase/uj13_language_switch_test.py` implementing `TestUJ13LanguageSwitch` with `@pytest.mark.usecase @pytest.mark.browser`; `test_language_switch_preserves_url_state(test_context, env_url)`: (Given) `ApiClient.login(pro_user)`, `BrowserHelper`; (When) `browser.goto("/search?country=ES&city=Madrid&min_price=200000&max_price=500000")`; wait for results; assert URL has all 4 params; click language switcher (e.g. `[data-testid="lang-switcher"]`) and select `EN`; (Then) assert URL still contains `country=ES`, `city=Madrid`, `min_price=200000`, `max_price=500000` after locale change; assert at least one UI text element (e.g. the search input placeholder or filter label) is in English (not Spanish); assert `[data-testid="listing-card"]` count is same as before language switch (re-fetch did not break filters)

- [ ] T101 [P] [US3] Create `tests/usecase/uj12_scraping_recovery_test.py` implementing `TestUJ12ScrapingRecovery` with `@pytest.mark.usecase @pytest.mark.browser @pytest.mark.slow`; `test_scraping_failure_and_recovery(test_context, env_url)`: (Given) `ApiClient.login(admin_user)`, `BrowserHelper`, `ClusterHelper()`; count listings before via `GET /api/v1/listings?country=ES` → `before_count`; (When) trigger a scraping job for Idealista via admin API `POST /admin/scraping/trigger` with proxy configured to fail (use test env var `PROXY_MODE=fail_403`); wait up to 60s for job status to show `failed`; verify admin received failure notification via `EmailSpy`; `browser.goto("/admin")`; assert `[data-testid="scraping-job-row"]` shows `failed` status; click `[data-testid="rotate-proxy-btn"]` to simulate proxy rotation; click `[data-testid="retrigger-scrape-btn"]`; wait for next job status `succeeded` (up to 90s); (Then) `after_count = GET /api/v1/listings?country=ES → total_count`; assert `after_count >= before_count` (zero listings lost); mark `@pytest.mark.slow` due to retry wait times

- [ ] T102 [P] [US2] Create `tests/usecase/uj14_websocket_reconnect_test.py` implementing `TestUJ14WebSocketReconnect` with `@pytest.mark.usecase @pytest.mark.browser`; `test_ws_reconnection_preserves_session(test_context, env_url)`: (Given) `ApiClient.login(pro_user)`, `BrowserHelper`; (When) `browser.goto("/chat")`; send 3 messages via UI `[data-testid="chat-input"]` + `[data-testid="send-btn"]` and wait for each response (`[data-testid="assistant-message"]` count increases); record `session_id` from DOM `[data-testid="session-id"]` attribute; simulate network disconnect by calling `ClusterHelper().exec_in_pod("websocket-server", ["pkill", "-TERM", "-f", "connection_handler"])` (or equivalent to close existing WS connections); (Then) assert `[data-testid="reconnecting-indicator"]` appears within 3s; assert indicator disappears and chat is usable again within 10s; assert `[data-testid="session-id"]` attribute matches original `session_id`; assert previous 3 assistant messages still visible in DOM; send a 4th message and assert response received

**Checkpoint**: `pytest tests/usecase -v` passes all 15 user journey tests (UJ-01 through UJ-15). Total elapsed < 30 minutes.

---

## Phase 13: Documentation & CI Integration

**Purpose**: Document all 15 journey test scenarios with Given/When/Then, wire Makefile targets, and configure nightly CI.

- [ ] T103 Create `docs/test-scenarios.md` with: (1) Introduction — purpose of user journey tests, when they run, how they differ from unit/integration tests; (2) for each UJ-01 through UJ-15: a section with ID, name, description, **Given/When/Then** steps (verbatim from plan.md user journey descriptions), services exercised, subscription tier required, performance target (if any), and make target to run it; (3) "Running Locally" section with prerequisites and commands; (4) "Debugging Failures" section covering artifact collection paths, how to run with `PLAYWRIGHT_HEADLESS=false`, how to read Redis spy output, how to tail pod logs; (5) "Adding a New Journey Test" section with 5-step checklist

- [ ] T104 Add to root `Makefile` (or `mk/kind.mk`): `test-usecase` target: `cd tests/usecase && uv run pytest -v --tb=short -m usecase`; `test-usecase-fast` target: `cd tests/usecase && uv run pytest -v --tb=short -m "usecase and not slow"`; `test-usecase-browser` target: `cd tests/usecase && uv run pytest -v --tb=short -m "usecase and browser"`; `test-usecase-api` target: `cd tests/usecase && uv run pytest -v --tb=short -m "usecase and api"`; each target depends on `kind-port-forward-bg` (or equivalent background port-forward target)

- [ ] T105 Create `.github/workflows/user-journeys.yml` defining: (1) nightly cron trigger `"0 2 * * *"` running against staging; (2) PR trigger on `paths: ["services/**", "helm/**", "tests/usecase/**", "frontend/src/**"]` running fast subset (`make test-usecase-fast`); (3) jobs: `setup-cluster` (kind create, helm install, kind-seed), `run-journeys` (depends on setup-cluster, runs `make test-usecase`), `collect-artifacts` (always runs after run-journeys, uploads `tests/usecase/artifacts/` and pod logs with 30-day retention); (4) `on.workflow_dispatch` with optional `journey_id` input to run a single test (e.g. `pytest uj03_*`)

- [ ] T106 [P] Run `cd tests/usecase && uv run pytest --collect-only -q` to verify all 15 test files are collected and no import errors; run `uv run ruff check .` and `uv run mypy --strict helpers/` to verify zero linting/type errors; fix any issues found before marking complete

- [ ] T107 [P] Run the fast usecase subset `pytest -m "usecase and api and not slow"` against a running kind cluster and verify UJ-03, UJ-05, UJ-09, UJ-11, UJ-15 all pass; document any timing or environment issues discovered; update `BASELINES` values in `helpers/assertions.py` if observed runtimes differ significantly from initial estimates

**Checkpoint**: `docs/test-scenarios.md` committed; `make test-usecase-fast` green; `make test-usecase` completes < 30 minutes; GitHub Actions workflow validates on next PR.

---

## User Journey Dependencies & Execution Order

### Phase Dependencies

| Phase | Depends On | Can Parallelize With |
|-------|-----------|---------------------|
| Phase 9 (Infrastructure) | Phases 1–8 complete | — (must be complete before 10–13) |
| Phase 10 (Core API Journeys) | Phase 9 | Phase 10 tasks are parallel to each other |
| Phase 11 (Browser Journeys) | Phase 9 | Phase 11 tasks, Phase 10 tasks |
| Phase 12 (Remaining Journeys) | Phase 9 | Phase 10, 11, 12 tasks all parallel |
| Phase 13 (Docs + CI) | Phases 10–12 | T106, T107 parallel |

### Journey → User Story Mapping

| Journey | User Story | Services Exercised |
|---------|-----------|-------------------|
| UJ-01 Onboarding | US3 Browser | api-gateway, frontend |
| UJ-02 Find Deal | US1 + US3 | api-gateway, ml-scorer, frontend |
| UJ-03 Alert Notification | US1 | api-gateway, pipeline, alert-engine, notification-dispatcher |
| UJ-04 AI Chat to Alert | US2 | ws-server, ai-chat, api-gateway |
| UJ-05 Subscription Upgrade | US1 + US3 | api-gateway, frontend |
| UJ-06 Portfolio Multi-Currency | US3 | api-gateway, ml-scorer, frontend |
| UJ-07 Admin Retrain | US3 | api-gateway, ml-trainer, ml-scorer, frontend |
| UJ-08 Free Tier Delay | US1 | api-gateway |
| UJ-09 Multi-Country Search | US1 | api-gateway |
| UJ-10 GDPR Export & Delete | US3 | api-gateway, frontend |
| UJ-11 Price Drop Engagement | US1 | pipeline, alert-engine, notification-dispatcher, api-gateway |
| UJ-12 Scraping Recovery | US3 | spider-workers, api-gateway, frontend |
| UJ-13 Language Switch | US3 | frontend |
| UJ-14 WS Reconnection | US2 | ws-server, frontend |
| UJ-15 Scrape-to-Alert | US1 | pipeline, ml-scorer, alert-engine, notification-dispatcher |

### Parallel Execution Example — Phase 10

```
# All Phase 10 tests can be implemented in parallel (different files):
Task: T088  uj03_alert_notification_test.py
Task: T089  uj15_scrape_to_alert_latency_test.py
Task: T090  uj11_price_drop_engagement_test.py
Task: T091  uj04_ai_chat_to_alert_test.py
Task: T092  uj08_free_tier_delay_test.py  (mark slow)
Task: T093  uj05_subscription_upgrade_test.py
```

### Parallel Execution Example — Phase 9 Helpers

```
# After T076-T078 (scaffold + conftest), helpers are all independent:
Task: T079  helpers/api.py
Task: T080  helpers/ws.py
Task: T081  helpers/cluster.py
Task: T082  helpers/db.py
Task: T083  helpers/fixtures.py
Task: T084  helpers/spies.py
Task: T085  helpers/time_travel.py
Task: T086  helpers/browser.py
Task: T087  helpers/assertions.py
```

---

## User Journey Implementation Strategy

### MVP First (Core Backend Journeys)

1. Complete Phase 9: Infrastructure
2. Implement T088 (UJ-03 — validates spy pattern, most complex)
3. Implement T089 (UJ-15 — validates full pipeline latency)
4. **STOP and VALIDATE**: two hardest tests passing proves the infrastructure works
5. Continue with remaining Phase 10–12 tests

### Fast-to-Value Order (Recommended)

1. Phase 9 (infrastructure) → `--collect-only` succeeds
2. T088 (UJ-03) → spy pattern confirmed
3. T099 (UJ-09) → simplest API test, quick win
4. T091 (UJ-04) → WS + LLM integration confirmed
5. T094 (UJ-01) → browser login flow confirmed
6. Then parallelise remaining Phase 10–12

---

## User Journey Notes

- `[P]` within phases 10–12 means tests can be written in parallel (independent files)
- `@pytest.mark.slow` on UJ-07, UJ-08, UJ-12: involve pod restarts or K8s job waits — exclude from fast CI with `-m "not slow"`
- UJ-08 (`time_travel`) modifies cluster state: ensure `TimeTravel.reset()` runs in teardown even on failure (use `try/finally` in test or `test_context` cleanup)
- UJ-12 (`scraping_recovery`) requires `PROXY_MODE=fail_403` env var to be supported by the spider-worker test configuration — verify this is set in `values-test.yaml`
- UJ-14 (`ws_reconnect`) may need `pkill` permission in the `websocket-server` container — verify it's available or use an alternative close mechanism (e.g. a test-mode HTTP endpoint `POST /internal/close-all-sessions`)
- `chamberí_zone_id` needed by UJ-03, UJ-04: resolve dynamically via `GET /api/v1/zones?country=ES&name=Cham` at test start, don't hardcode UUID
