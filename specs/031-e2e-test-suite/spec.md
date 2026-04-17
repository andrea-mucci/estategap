# Feature Specification: E2E Test Suite

**Feature Branch**: `031-e2e-test-suite`  
**Created**: 2026-04-17  
**Status**: Draft  
**Input**: User description: "Build the end-to-end test suite that runs against a fully deployed EstateGap platform on the local kind cluster."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - REST API Correctness (Priority: P1)

A developer or QA engineer runs the API test suite against the kind cluster and verifies that every documented REST endpoint returns the correct responses under valid and invalid conditions, including authentication gates, subscription tier restrictions, pagination, filtering, and error shapes.

**Why this priority**: REST API correctness is the foundation of the platform — all other layers (UI, alerts, ML scoring) depend on a well-behaved HTTP API. This is the highest-value signal in the suite.

**Independent Test**: Can be fully tested by running `make test-e2e-api` against a seeded cluster and observing pytest pass/fail output; delivers confidence that all documented API contracts are honoured.

**Acceptance Scenarios**:

1. **Given** a seeded kind cluster with a Pro-tier user, **When** the API test suite is run, **Then** all happy-path tests for every endpoint pass with correct HTTP status codes and response shapes.
2. **Given** a request with an expired JWT, **When** any authenticated endpoint is called, **Then** the response is `401 Unauthorized` with a structured error body.
3. **Given** a Free-tier user requesting a listing delayed by 48 h, **When** the endpoint is called, **Then** the response reflects the tier delay rather than live data.
4. **Given** rapid requests from a single IP, **When** the per-tier rate limit is exceeded, **Then** the response is `429 Too Many Requests` with a valid `Retry-After` header.

---

### User Story 2 - WebSocket Chat Protocol (Priority: P1)

A developer verifies the full real-time chat lifecycle: connection authentication, streaming text chunks, receiving criteria summaries, image carousel interactions, deal-alert push messages, session reconnection, ping/pong keepalive, idle-timeout, and concurrent session isolation.

**Why this priority**: WebSocket chat is EstateGap's primary search UX. Any regression in the protocol silently breaks the user's main workflow.

**Independent Test**: Can be fully tested by running `make test-e2e-ws` against a seeded cluster with a running AI chat service and WS gateway; delivers confidence that all defined message types and lifecycle events behave correctly.

**Acceptance Scenarios**:

1. **Given** a valid JWT, **When** a WebSocket connection is established, **Then** the handshake succeeds and the client receives messages.
2. **Given** an invalid or missing JWT, **When** a WebSocket connection is attempted, **Then** the server closes the connection with close code `4001`.
3. **Given** a connected chat session, **When** a user message is sent, **Then** the client receives a sequence of `text_chunk` messages followed by exactly one `criteria_summary` message.
4. **Given** a mid-conversation disconnect, **When** the client reconnects with the same `session_id`, **Then** conversation history is intact and the session resumes correctly.
5. **Given** 100 simultaneous WebSocket sessions, **When** each sends distinct messages, **Then** all receive only their own responses with no cross-talk.

---

### User Story 3 - Browser UI End-to-End Flows (Priority: P2)

A QA engineer or CI pipeline runs the Playwright test suite and verifies that all critical user journeys in the browser — registration, login, chat search, listing detail, dashboard, alerts, subscriptions, and admin — work correctly in Chromium, Firefox, and WebKit.

**Why this priority**: Browser tests catch integration issues between the frontend and the API/WS layers. They validate the user-facing experience that unit and integration tests cannot.

**Independent Test**: Can be fully tested by running `make test-e2e-browser` against a deployed frontend pointing at the kind cluster; covers 10+ user flows across 3 browsers.

**Acceptance Scenarios**:

1. **Given** an anonymous user on the landing page, **When** the hero CTA is clicked, **Then** the user lands on `/register` and the page loads within 2 s.
2. **Given** a registered user, **When** login is completed, **Then** the user lands on the dashboard and sees their tier-appropriate data.
3. **Given** a logged-in user on the AI chat page, **When** a search query is typed and sent, **Then** streamed response chunks appear progressively and a criteria confirmation chip row is shown.
4. **Given** a Free-tier user, **When** the upgrade flow is triggered, **Then** Stripe Checkout (test mode) opens; after a simulated webhook, the UI reflects the new tier.
5. **Given** a non-admin user accessing the admin panel URL, **When** the page loads, **Then** a 403 / access-denied state is rendered.

---

### User Story 4 - Multi-User Concurrency (Priority: P2)

A performance engineer verifies that concurrent operations by multiple users — simultaneous zone searches, alert creation on the same listing, CRM status updates, and 100 parallel WebSocket chat sessions — produce correct, isolated results with no data corruption or cross-talk.

**Why this priority**: Concurrency bugs are silent and hard to reproduce; catching them in E2E prevents production incidents.

**Independent Test**: Can be fully tested by running `make test-e2e-concurrency`; passes when all concurrent assertions hold and no errors are reported.

**Acceptance Scenarios**:

1. **Given** two concurrent users querying the same zone, **When** both requests complete, **Then** both receive identical correct result sets.
2. **Given** two users creating alerts on the same listing simultaneously, **When** both alerts are triggered, **Then** each user receives only their own notification.
3. **Given** 100 concurrent WebSocket sessions each streaming a response, **When** all complete, **Then** all 100 received correct content and none received another session's content.

---

### User Story 5 - Visual Regression & Accessibility (Priority: P3)

A release engineer runs visual regression snapshots and accessibility checks on key pages, comparing against approved baselines with a ≤ 0.1 % pixel-difference tolerance, and verifying WCAG AA conformance.

**Why this priority**: Visual regressions and accessibility failures are often undetected by functional tests; catching them before release RC prevents surprise rollbacks and compliance issues.

**Independent Test**: Can be tested by running `make test-e2e-visual` and `make test-e2e-a11y`; delivers a diff report and axe-core violation summary.

**Acceptance Scenarios**:

1. **Given** a release candidate build, **When** visual regression tests run, **Then** pixel-difference versus approved baseline is ≤ 0.1 % for all five covered pages.
2. **Given** any primary page in Chromium, **When** full keyboard navigation is exercised, **Then** all interactive elements are reachable via Tab and have visible focus indicators.
3. **Given** any interactive element, **When** inspected by an accessibility checker, **Then** no WCAG AA contrast or label violations are reported.

---

### Edge Cases

- What happens when the kind cluster is not running when tests start?
- How does the suite handle flaky tests (network timeouts, async race conditions)?
- What happens when test fixture data is missing or partially loaded?
- How does the suite behave when Stripe test webhooks are delayed?
- What if a WebSocket `deal_alert` never arrives within the 5 s window?
- What happens when visual baseline snapshots don't yet exist (first run)?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The suite MUST provide a single `make kind-test` target that executes all E2E sub-suites against a deployed kind cluster in under 20 minutes.
- **FR-002**: REST API tests MUST cover every endpoint documented in the OpenAPI spec, including authentication, pagination, filtering, error responses, currency conversion, and tier gating.
- **FR-003**: The suite MUST verify per-tier rate-limit thresholds (Free 30/min, Basic 120/min, Pro 300/min, Global 600/min, API 1200/min) and the presence of a valid `Retry-After` header on `429` responses.
- **FR-004**: WebSocket tests MUST validate all defined message types (`text_chunk`, `criteria_summary`, `image_carousel`, `deal_alert`) and lifecycle events (auth rejection `4001`, reconnection, ping/pong, idle timeout).
- **FR-005**: Playwright tests MUST cover at minimum 10 user flows across Chromium (all tests), Firefox (full suite nightly), and WebKit (critical path: auth, search, listing detail).
- **FR-006**: The suite MUST include concurrency tests demonstrating 100 simultaneous WebSocket sessions and 2-user concurrent zone search/alert scenarios without errors or cross-talk.
- **FR-007**: Visual regression tests MUST compare key pages against approved baselines with a ≤ 0.1 % pixel-difference tolerance using `toHaveScreenshot()`.
- **FR-008**: The suite MUST support test parallelism via namespace/prefix isolation (e.g., `test-run-abc123-*`) to enable sharding across 4 CI runners.
- **FR-009**: Each test MUST start from a known cluster state: fixtures loaded, Redis flushed, and relevant caches cleared via global setup/teardown hooks.
- **FR-010**: On any test failure, the suite MUST automatically collect: pod logs, failed-pod descriptions, screenshots (UI tests), HAR files, video recordings, and a database snapshot; retained as CI artefacts for 30 days.
- **FR-011**: Accessibility tests MUST verify keyboard navigation, screen-reader labels, and WCAG AA colour contrast on all primary pages.
- **FR-012**: The suite MUST track and report flaky test rate; target < 1 % flaky rate over a rolling 50-run window.

### Key Entities

- **Test Run**: A single invocation of the suite with a unique prefix, a set of participating test files, and collected artefacts.
- **Test User**: A pre-seeded database user per subscription tier (Free, Basic, Pro, Admin) used as fixtures across all sub-suites.
- **Test Fixture**: Seeded database records (listings, zones, alert rules, portfolio properties) that establish a known cluster state before each test.
- **Visual Baseline**: Approved reference screenshot for a key page, stored in `frontend/tests/e2e/visual/baselines/`, used for pixel-diff comparison.
- **Artefact Bundle**: Per-test failure package: pod logs, screenshot, HAR, video, DB snapshot.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: `make kind-test` completes the full E2E suite in under 20 minutes on a standard CI runner.
- **SC-002**: REST API tests achieve 100 % endpoint coverage against the OpenAPI spec.
- **SC-003**: WebSocket tests cover all defined message types and lifecycle edge cases (≥ 9 distinct scenarios).
- **SC-004**: Playwright tests cover 10 or more distinct user flows across 3 browsers.
- **SC-005**: Concurrency tests demonstrate 100 simultaneous WebSocket users with zero cross-talk errors.
- **SC-006**: Visual regression tests produce fewer than 1 % false positives over 10 consecutive runs.
- **SC-007**: Every failed test produces a complete artefact bundle retrievable from CI within 30 days.
- **SC-008**: The full suite can shard across 4 CI runners with near-linear speedup.
- **SC-009**: Flaky test rate is below 1 % over any rolling 50-run window.

## Assumptions

- The kind cluster is already running and the platform is deployed before tests execute (`make kind-deploy` is a prerequisite).
- Test fixture data (users per tier, listings, zones, alert rules) is seeded by `make kind-seed` prior to each run.
- A test-mode Stripe environment and Google OAuth mock server are available during Playwright subscription and auth tests.
- The AI chat and WS gateway services are deployed and reachable within the cluster for WebSocket tests.
- Playwright visual baselines are committed to the repository; first-run baseline generation is a separate one-time step.
- The CI environment has access to a Docker daemon and sufficient memory (≥ 8 GB) to run a kind cluster with all services.
- Firefox and WebKit browser binaries are available in the Playwright installation used by CI.
