# Feature: E2E Test Suite (API + Playwright)

## /specify prompt

```
Build the end-to-end test suite that runs against a fully deployed EstateGap platform on the local kind cluster. Tests cover the REST API, WebSocket protocol, and the browser UI via Playwright.

## What

### 1. REST API test suite

Location: `tests/e2e/api/`

Coverage:
- Happy path for every documented REST endpoint
- Authentication: valid tokens, expired tokens, invalid signatures, missing tokens
- Token refresh flow
- Google OAuth callback handling (with mocked Google responses)
- Rate limiting verification: send requests until 429 triggered; verify Retry-After header; verify per-tier thresholds (Free 30/min, Basic 120/min, Pro 300/min, Global 600/min, API 1200/min)
- Pagination: cursor-based pagination edge cases (empty results, single page, exact page boundary)
- Each filter in the listings search tested in isolation and in combinations
- Error responses: 400 validation with correct error format, 404 not found, 403 forbidden, 409 conflict, 500 handled gracefully
- Currency conversion via `?currency=USD` param
- Subscription tier gating (free user delayed 48h, basic country restrictions, admin-only endpoints)

### 2. WebSocket test suite

Location: `tests/e2e/websocket/`

Coverage:
- Connection with valid JWT succeeds
- Connection with invalid JWT rejected with 4001 close code
- Chat protocol: send user message → receive streamed `text_chunk` messages → receive final `criteria_summary`
- Image carousel message: user sends preference text → receive `image_carousel` with curated images → send image feedback → criteria updated
- Real-time deal alert: inject scored listing matching user rule → receive `deal_alert` message within 5s
- Reconnection: disconnect mid-conversation → reconnect with same session_id → conversation history intact
- Ping/pong keepalive (30s interval) verified
- Connection closes gracefully after 30min idle
- Concurrent connections: 100 simultaneous WebSocket clients, all receive their own messages correctly

### 3. Playwright browser tests

Location: `frontend/tests/e2e/`

Coverage:
- **Landing page:** loads within 2s, hero CTA links to /register, pricing table accurate
- **Registration + login:** email/password registration, Google OAuth (mocked), login, logout
- **AI chat flow:**
  - Type query → see streamed response
  - Voice input button triggers recognition (mocked in tests)
  - Select chips → criteria updates
  - Confirm criteria → search runs → results shown
  - Alert auto-created → appears in alerts page
- **Search page:**
  - Filters update URL search params
  - Results re-fetch on filter change
  - Sort changes result order
  - Grid/list view toggle works
  - Saved search CRUD
- **Listing detail page:**
  - All sections render (photo gallery, stats, SHAP chart, price history, comparables, map)
  - Photo gallery swipeable on mobile
  - Translate button translates description
  - CRM status actions (favorite, contacted, etc.) persist
- **Dashboard:**
  - Cards show correct counts
  - Charts render without errors
  - Country tab switching updates data
- **Map interactions:**
  - Zoom in/out works
  - Click marker shows popup with mini listing card
  - Draw custom zone saves new zone
  - Markers re-fetch on pan
- **Alerts page:**
  - Create rule form works
  - Edit rule persists changes
  - Delete rule with confirmation
  - Alert history shows past triggers
- **Subscription flow:**
  - Free user sees upgrade prompts
  - Click upgrade → Stripe Checkout (test mode)
  - Simulated webhook completes → tier updated → UI reflects new tier
- **Admin panel (admin-only):**
  - Access denied for non-admin
  - Scraping stats display correctly
  - Manual ML retrain triggers Job
  - User list paginates correctly
- **Responsive tests:**
  - Mobile viewport (375×667): sidebar collapses, navigation works
  - Tablet viewport (768×1024): layout adapts
- **Accessibility:**
  - Keyboard navigation works on all pages
  - Screen reader labels present on interactive elements
  - Color contrast meets WCAG AA

### 4. Multi-user concurrency tests

Location: `tests/e2e/concurrency/`

Scenarios:
- Two users search the same zone simultaneously — both receive correct results
- Two users create alerts on the same listing — both receive their own notifications
- One user updates a listing's CRM status while another views it — no conflict
- 100 concurrent WebSocket chat sessions — all stream correctly, no cross-talk

### 5. Test data reset

- Each E2E test starts from a known state (fixture loaded, cache cleared, Redis flushed)
- Parallelism achieved via namespace/prefix isolation per test run (e.g., `test-run-abc123-*`)
- Global setup/teardown hooks handle cluster state

### 6. Browser coverage

- **Chromium:** primary, all tests
- **Firefox:** run full suite nightly
- **WebKit (Safari):** run critical path tests only (auth, search, listing detail)

### 7. Visual regression tests

- Key pages captured as screenshots on every release candidate
- Compared pixel-by-pixel with tolerance threshold (0.1% difference allowed)
- Uses Playwright's `toHaveScreenshot()` assertion
- Pages covered: home (logged out), home (logged in), dashboard, listing detail (Tier 1), AI chat mid-conversation

### 8. Artifacts on failure

For every failed E2E test:
- All pod logs (from relevant namespaces)
- Screenshot (for UI tests)
- HAR file (network activity)
- Video recording of test execution
- Database snapshot at failure moment
- Available as GitHub Actions artifacts with 30-day retention

## Why

E2E tests catch integration issues that unit and integration tests miss. They verify the entire stack works together in a production-like environment. Running on kind means these tests can catch Kubernetes-specific issues (probes, networking, resource limits) before production.

## Acceptance Criteria

- E2E test suite runs on kind cluster: `make kind-test` completes in < 20 minutes
- REST API tests cover every endpoint in the OpenAPI spec (100%)
- WebSocket tests verify all message types and edge cases
- Playwright tests cover 10+ user flows across 3 browsers
- Concurrency tests demonstrate 100 simultaneous users without errors
- Visual regression tests have < 1% false positive rate
- Failed tests produce complete diagnostic artifacts
- All tests parallelizable: full suite can shard across 4 CI runners
- Flaky test rate < 1% (tracked over 50 runs)
```
