# Functional Requirements — Addendum v2.2

**Project:** EstateGap  
**Version:** 2.2 (addendum to v2.0 + v2.1)  
**Date:** April 2026  
**Status:** Draft  
**Scope:** This addendum adds a new section covering the complete testing strategy:

1. **§13 NEW** — Testing & Quality Assurance (local kind environment, Helm validation, E2E, use case tests)

---

## 13. Testing & Quality Assurance

### 13.1 Testing Strategy Overview

EstateGap follows a standard testing pyramid with emphasis on **realistic, reproducible local testing** using [kind](https://kind.sigs.k8s.io/) (Kubernetes in Docker). Every developer must be able to spin up a complete, working copy of the platform on their laptop in under 5 minutes.

```
              ┌──────────────────┐
              │  Use Case Tests  │  ← Slow, high-value (10-20 journeys)
              │  (user journeys) │
              ├──────────────────┤
              │    E2E Tests     │  ← API + WebSocket + Playwright
              ├──────────────────┤
              │ Contract Tests   │  ← gRPC / Protobuf / OpenAPI
              ├──────────────────┤
              │ Integration Tests│  ← testcontainers (DB, NATS, Redis)
              ├──────────────────┤
              │   Unit Tests     │  ← Fast, isolated (thousands)
              └──────────────────┘
```

**Coverage targets:**
- Unit tests: **≥ 80%** for Go and Python services
- Unit tests: **≥ 70%** for frontend code
- Critical user journeys: **100%** covered by E2E + use case tests
- Helm templates: **100%** render successfully across all values profiles

**Environments:**
- **Local (kind):** every developer laptop. Used for day-to-day development and debugging.
- **CI:** GitHub Actions. Runs on every PR. Includes a kind cluster for E2E tests.
- **Staging:** permanent K8s environment. Continuous deployment from `main`.
- **Production:** continuous deployment from `release/*` branches after manual approval.

### 13.2 Local Development Environment (kind)

- **FR-TEST-001** — **Kind cluster configuration file** at `tests/kind/cluster.yaml` defining: K8s version (1.30+), 3 nodes (1 control-plane + 2 workers), port mappings (80, 443, 8080, 8081), feature gates, extra mounts for local volumes.
- **FR-TEST-002** — **Makefile targets** at repository root:
  - `make kind-up` — creates the local cluster
  - `make kind-down` — tears down the cluster
  - `make kind-build` — builds all Docker images with `-dev` tag
  - `make kind-load` — loads images into the kind cluster
  - `make kind-deploy` — installs the Helm chart
  - `make kind-seed` — loads fixture data
  - `make kind-test` — runs the full E2E test suite
  - `make kind-logs` — tails logs from all pods
  - `make kind-shell SERVICE=api-gateway` — opens a shell in a service pod
  - `make kind-reset` — full teardown + rebuild + redeploy + seed
- **FR-TEST-003** — **Image loading script** that detects image changes and only reloads modified images (via digest comparison).
- **FR-TEST-004** — **Port forwarding** automatic on deploy:
  - `localhost:8080` → api-gateway
  - `localhost:8081` → ws-server
  - `localhost:3000` → frontend
  - `localhost:3001` → Grafana
  - `localhost:9090` → Prometheus
  - `localhost:5432` → PostgreSQL (read-only for debugging)
  - `localhost:6379` → Redis
  - `localhost:4222` → NATS
- **FR-TEST-005** — **Seed data fixture library** at `tests/fixtures/` containing:
  - 5 test users (one per subscription tier)
  - 1,000 sample listings across 5 countries (realistic synthetic data)
  - Zone polygons for major cities in each country
  - Pre-trained minimal ML model artifacts for testing
  - 10 active alert rules
  - Sample AI conversations
- **FR-TEST-006** — **Test mode flag** (`ESTATEGAP_TEST_MODE=true`) that: disables real scraping (uses fixture data), mocks Stripe webhooks, uses fake LLM provider with deterministic responses, accelerates cron schedules (scraping every 30s instead of 6h).
- **FR-TEST-007** — **Cluster provisioning time** must be **< 5 minutes** from `make kind-up` to all pods Running (excluding image build time on first run).

### 13.3 Helm Chart Validation

- **FR-TEST-010** — **`helm lint`** must pass with zero errors and zero warnings for all values profiles.
- **FR-TEST-011** — **`helm template`** must successfully render all templates for: `values.yaml`, `values-staging.yaml`, `values-production.yaml`, `values-test.yaml`. Output must be valid Kubernetes YAML.
- **FR-TEST-012** — **JSON Schema validation** via `values.schema.json` at chart root. Every top-level value must have a schema entry with type, description, and optional default/enum.
- **FR-TEST-013** — **Installation test on kind cluster.** After `helm install`: all Deployments reach ReadyReplicas = spec.replicas within 3 minutes. No CrashLoopBackOff or ImagePullBackOff.
- **FR-TEST-014** — **Readiness probe verification.** Every pod must respond to its `/readyz` endpoint within 60 seconds of startup. Liveness probes must not cause pod restarts in the first 10 minutes.
- **FR-TEST-015** — **Upgrade/rollback tests.** Install v0.1.0 → upgrade to v0.2.0 → verify no data loss → rollback to v0.1.0 → verify state restored. Must succeed without downtime (rolling update strategy).
- **FR-TEST-016** — **`helm-unittest`** suite at `helm/estategap/tests/` with unit tests for template logic (conditional resources, values substitution, feature toggles).
- **FR-TEST-017** — **Chart conformance checks.** All resources have: namespace, labels (app.kubernetes.io/*), resource requests + limits, securityContext, liveness + readiness probes. No `latest` image tags.
- **FR-TEST-018** — **Namespace isolation tests.** NetworkPolicies enforced: cross-namespace traffic only via allowed paths (gateway → all; scraping/pipeline/intelligence/notifications → system only).
- **FR-TEST-019** — **Secrets handling test.** All secrets deployed as SealedSecrets. No plain-text credentials in ConfigMaps or Deployment specs.

### 13.4 Unit Tests

- **FR-TEST-020** — **Go services:** `go test ./...` with `-race -cover`. Coverage reported per package. `golangci-lint run` must pass (rules: errcheck, gosec, govet, revive, staticcheck, unused).
- **FR-TEST-021** — **Python services:** `pytest` with `--cov=<service>` flag. Coverage reported per module. `ruff check` + `mypy --strict` must pass.
- **FR-TEST-022** — **Frontend:** `vitest run --coverage`. React Testing Library for components. `eslint` + `tsc --noEmit` must pass.
- **FR-TEST-023** — **Coverage thresholds** enforced in CI:
  - Go services: 80% statement coverage
  - Python services: 80% statement + branch coverage
  - Frontend: 70% statement coverage
  - Falling below threshold fails the CI build.
- **FR-TEST-024** — **Test patterns:**
  - Go: table-driven tests with `testify/assert`
  - Python: parametrized tests with `pytest.mark.parametrize`
  - Frontend: AAA pattern (Arrange-Act-Assert)
- **FR-TEST-025** — **Mocking guidelines:**
  - Go: interfaces + hand-written fakes (avoid `gomock` unless necessary)
  - Python: `pytest-mock` with explicit assertions on call args
  - Frontend: `msw` (Mock Service Worker) for API mocks
- **FR-TEST-026** — **Pydantic model validation tests.** Every Pydantic model has tests for: valid construction, invalid data rejection, JSON serialization round-trip, edge cases (None, empty, boundaries).
- **FR-TEST-027** — **SQL query tests.** Critical queries (listing search, rule matching, zone aggregation) tested against a real PostgreSQL instance with known fixture data.

### 13.5 Integration Tests

- **FR-TEST-030** — **Testcontainers** used to spin up real dependencies for integration tests: PostgreSQL 16 + PostGIS, Redis 7, NATS with JetStream, MinIO. Fresh instance per test suite.
- **FR-TEST-031** — **Database migration tests:**
  - All migrations apply successfully on empty DB
  - All migrations rollback successfully (`alembic downgrade -1`)
  - Migrations are idempotent (re-running from head produces no diff)
  - No migration causes data loss on existing data
- **FR-TEST-032** — **gRPC service tests.** Each gRPC service has tests that: start a real gRPC server in-process, make client calls via the generated stubs, verify responses match expected schemas.
- **FR-TEST-033** — **NATS pub/sub tests.** Each NATS consumer has tests that: publish test messages to the stream, wait for consumer to process, verify side effects (DB writes, downstream events).
- **FR-TEST-034** — **Data pipeline integration tests:**
  - Inject raw listing → verify it flows through normalizer → deduplicator → enricher → scorer → DB
  - Pipeline latency assertion: < 30s per listing
  - Failure recovery: kill a pipeline component mid-flight, restart, verify no message loss
- **FR-TEST-035** — **Cross-service integration.** Key interaction paths have dedicated tests:
  - api-gateway → ml-scorer (gRPC)
  - api-gateway → ai-chat (gRPC streaming)
  - ws-server → ai-chat (gRPC bidirectional)
  - alert-engine → alert-dispatcher (NATS)

### 13.6 Contract Tests

- **FR-TEST-040** — **Protobuf contract tests.** Every RPC defined in `proto/*.proto` has contract tests that verify: client and server implementations agree on message format, backward compatibility (new fields are optional or have defaults).
- **FR-TEST-041** — **Buf breaking change detection.** CI runs `buf breaking --against '.git#branch=main'` on every PR. Breaking changes must be explicit (new proto version or major bump).
- **FR-TEST-042** — **OpenAPI contract tests.** Frontend types generated from OpenAPI spec via `openapi-typescript-codegen`. API responses validated against OpenAPI schema in E2E tests (using `openapi-response-validator`).
- **FR-TEST-043** — **Consumer-driven contracts** for critical paths: frontend expectations of API responses are codified as fixtures; API returns fixtures in test mode.

### 13.7 E2E Tests (on Kind Cluster)

- **FR-TEST-050** — **Full stack deployment** on kind with realistic fixture data. All services running, all probes green. Tests execute against the deployed cluster.
- **FR-TEST-051** — **REST API test suite** covering every documented endpoint:
  - Happy path for all GET, POST, PUT, DELETE endpoints
  - Auth: token expiration, refresh, invalid token, missing token
  - Rate limiting: verify 429 triggered at the right threshold per tier
  - Pagination: cursor behavior, edge cases (empty result, single page)
  - Filters: each filter in isolation + combinations
  - Error responses: 400 validation, 404 not found, 403 forbidden, 500 handled gracefully
- **FR-TEST-052** — **WebSocket test suite:**
  - Connection with valid JWT succeeds
  - Connection with invalid JWT rejected with 401 close code
  - Chat protocol: send message → receive streamed response
  - Image carousel message type works
  - Real-time deal notification received when listing scored
  - Reconnection after network drop resumes conversation
  - Ping/pong keepalive works (30s interval)
- **FR-TEST-053** — **Playwright browser tests** covering:
  - Landing page loads and CTAs work
  - Registration + login flow
  - AI chat input, voice input (mocked), full conversation flow
  - Search page filters update URL and results
  - Listing detail page renders all sections
  - Map interactions (zoom, click marker, popup)
  - Dashboard loads and renders charts
  - Alert rule CRUD
  - Responsive (mobile viewport tests)
- **FR-TEST-054** — **Multi-user concurrency tests.** Simultaneous actions by different users don't interfere: two users search same zone, both create alerts on same listing, both receive their own notifications.
- **FR-TEST-055** — **Test data reset between scenarios.** Each E2E test starts from a known state: fixture loaded, cache cleared, Redis flushed. Parallelism achieved via namespace isolation per test run.
- **FR-TEST-056** — **Browser coverage:** Chromium (primary), Firefox (secondary), WebKit (smoke test only).
- **FR-TEST-057** — **Visual regression tests** for key pages (home, dashboard, listing detail). Screenshots compared pixel-by-pixel with tolerance threshold.

### 13.8 Use Case / User Journey Tests

The most valuable tests: realistic end-to-end journeys that exercise multiple services together and validate business-critical flows.

- **FR-TEST-060** — **UJ-01: New user onboarding.** Sign up → verify email → complete onboarding tour → reach dashboard. Validates: registration, email sending (mocked), session management, onboarding state tracking.
- **FR-TEST-061** — **UJ-02: Find a Tier 1 deal via search.** Login → navigate to search → apply filters (country=ES, city=Madrid, tier=1) → see results sorted by deal_score → click top result → view detail page with SHAP explanation and comparables.
- **FR-TEST-062** — **UJ-03: Create alert rule and receive notification.** Login → create alert (country=ES, zone=Chamberí, tier<=2, max_price=600k) → simulate new matching listing injection → verify alert triggered → verify notification received on all configured channels (email, Telegram, WebSocket).
- **FR-TEST-063** — **UJ-04: AI conversational search → alert creation.** Login → open AI chat → send "apartment in Madrid under 500k, 2 bedrooms" → assistant asks clarifying questions → user responds with chips → criteria finalized → results shown → alert auto-created → alert rule visible in `/alerts` page.
- **FR-TEST-064** — **UJ-05: Subscription upgrade unlocks features.** Free user tries to create 4th alert rule → blocked with upgrade prompt → click upgrade → Stripe Checkout (test mode) → webhook simulates payment completion → user tier updated → retry alert creation succeeds.
- **FR-TEST-065** — **UJ-06: Portfolio tracking.** Login as Pro user → add 3 owned properties → see current estimated values from ML model → see unrealized gain/loss → change currency preference → values re-display in new currency.
- **FR-TEST-066** — **UJ-07: Admin retrains ML model.** Login as admin → navigate to `/admin` → ML tab → click "Retrain Now" for Spain model → K8s Job created → wait for completion → new model version visible → scorer hot-reloads → verify new predictions use new model.
- **FR-TEST-067** — **UJ-08: Free tier delay.** Free user searches → new listing (published 10 minutes ago) does NOT appear in results → same listing appears after fixture time advanced by 48 hours.
- **FR-TEST-068** — **UJ-09: Multi-country search.** Pro user with `countries=[ES, IT, FR]` permission → search with no country filter → results include listings from all 3 countries → prices correctly converted to user's preferred currency.
- **FR-TEST-069** — **UJ-10: GDPR data export & deletion.** Login → Settings → request data export → receive JSON with all user data (profile, conversations, alerts, portfolio) → request account deletion → confirm → account anonymized immediately → 30 days later hard-deleted.
- **FR-TEST-070** — **UJ-11: Price drop notification → engagement.** System detects €30k price drop on an existing listing (Tier 2 → Tier 1) → alert fires to users with matching rules → user receives email → clicks tracking link → redirected to listing detail page → "contacted" CRM status set.
- **FR-TEST-071** — **UJ-12: Scraping failure recovery.** Idealista spider blocked (all proxies return 403) → orchestrator detects failure → alert to admin → admin rotates proxy credentials → next scrape cycle succeeds → no listings lost.
- **FR-TEST-072** — **UJ-13: Language switching preserves state.** User with active search and filters switches UI language from ES to EN → URL filters preserved → search results re-fetched and still correct → no data loss.
- **FR-TEST-073** — **UJ-14: WebSocket reconnection.** User in middle of AI chat → network disconnects for 10s → client auto-reconnects → conversation state restored → user continues chat without restart.
- **FR-TEST-074** — **UJ-15: Scrape-to-alert latency.** New listing published on Idealista → scraped within 15min → normalized, enriched, scored within 30s → matching alerts dispatched within 10s → end-to-end latency from publication to user notification: **< 20 minutes**.

**Use case test structure:** each journey is implemented as a separate test file with:
- Setup: required fixtures, user accounts, cluster state
- Given/When/Then structure matching the requirement
- Cleanup: restore cluster state
- Artifacts on failure: logs, screenshots, DB dumps, NATS queue state

### 13.9 Data Quality Tests

- **FR-TEST-080** — **Synthetic data generators** per portal that produce realistic HTML/JSON responses matching the portal's structure. Used to test spiders without hitting real portals.
- **FR-TEST-081** — **Spider correctness tests.** For each spider: feed a captured HTML fixture → spider produces NormalizedListing → compare with expected output (golden file). Any change to spider logic requires updating the golden file.
- **FR-TEST-082** — **Deduplication accuracy tests.** Fixed test set of 1,000 listing pairs (500 duplicates, 500 non-duplicates, manually labeled). Target: recall ≥ 95%, precision ≥ 95%.
- **FR-TEST-083** — **ML model validation tests.** Holdout test set of 500 listings with known prices per country. MAPE computed → must be below threshold (12% for Spain, 14% for new countries). Regression test fails if new model worsens MAPE.
- **FR-TEST-084** — **Data completeness metrics.** Per portal, track % of listings with: GPS coordinates (target ≥ 95%), photos (≥ 90%), price (100%), area (≥ 95%), rooms (≥ 90%), construction year (≥ 60%). Alert if drops below threshold.
- **FR-TEST-085** — **Change detection tests.** Inject price change event → verify price_history row created → verify old price preserved → verify change percentage calculated correctly.

### 13.10 Test Data Management

- **FR-TEST-090** — **Fixture library** versioned in git at `tests/fixtures/`:
  - `users.json` — test accounts
  - `listings/es.json`, `listings/it.json`, etc. — synthetic listings per country
  - `zones/` — zone polygons
  - `ml-models/` — minimal pre-trained ONNX models
  - `conversations/` — AI chat samples
  - `alerts.json` — alert rule examples
  - `html-samples/<portal>/` — captured HTML pages for spider tests
- **FR-TEST-091** — **Database snapshot & restore.** Tool to snapshot fixture DB state → restore between tests in < 2s. Uses pg_dump/pg_restore or PostgreSQL template databases.
- **FR-TEST-092** — **Anonymized production sample.** Nightly job exports a GDPR-safe sample (1% of listings, no user PII) to `test-data` bucket. Used for performance testing.
- **FR-TEST-093** — **Preset test accounts** with tier, history, alerts, conversations pre-loaded. Identified by email pattern: `test-{tier}@estategap.test`.
- **FR-TEST-094** — **Deterministic LLM fixtures.** AI chat tests use a `FakeLLMProvider` that returns predetermined responses for known input prompts. No real API calls in tests.
- **FR-TEST-095** — **Deterministic time source.** All services accept a `NOW_OVERRIDE` env var for tests (used in UJ-07 to advance time).

### 13.11 CI/CD Integration

- **FR-TEST-100** — **GitHub Actions workflows** per test level:
  - `ci-unit.yml` — unit tests for Go, Python, frontend (parallel matrix)
  - `ci-integration.yml` — integration tests with testcontainers
  - `ci-contracts.yml` — Protobuf and OpenAPI contract tests
  - `ci-helm.yml` — helm lint, template, unittest
  - `ci-e2e.yml` — spin up kind, deploy, run E2E + use case tests
- **FR-TEST-101** — **Parallel execution:** matrix across Go / Python / frontend runs in parallel. E2E tests sharded by test file (run on 4 parallel runners).
- **FR-TEST-102** — **Kind in CI.** Uses `kind-action` GitHub Action. Cluster created in ~30s. Images loaded from GitHub Container Registry cache.
- **FR-TEST-103** — **Coverage reports** uploaded to Codecov (or similar). PR comments show coverage diff.
- **FR-TEST-104** — **Merge blocking.** PR cannot merge unless all CI jobs pass + coverage thresholds met + no contract breaking changes.
- **FR-TEST-105** — **Artifacts on failure.** For every failed E2E test: logs from all pods, screenshot (if UI test), HAR file (if network test), DB dump. Available as GitHub Actions artifacts.
- **FR-TEST-106** — **Flaky test detection.** Tests that fail intermittently are auto-flagged. Build does not fail on single flake; 3 consecutive flakes quarantine the test.
- **FR-TEST-107** — **Nightly full suite.** Complete test run (unit + integration + contract + E2E + use cases + load tests) runs nightly against `main`. Report emailed to engineering.

### 13.12 Observability in Tests

- **FR-TEST-110** — **Structured test logs** in JSON, correlated by `test_id`.
- **FR-TEST-111** — **E2E test telemetry.** Prometheus scrapes metrics during test run. Tempo captures traces. Loki stores logs. All available via Grafana post-test.
- **FR-TEST-112** — **Test result reporting.** JUnit XML output for all test suites. Aggregated into a single report per CI run. Rendered in GitHub Actions summary.
- **FR-TEST-113** — **Performance regression tracking.** Each E2E test records: duration, API latencies (p50/p95), DB query count. Historical data stored; > 20% regression triggers warning.

### 13.13 Security Tests

- **FR-TEST-120** — **Dependency scanning:** `govulncheck` for Go, `pip-audit` for Python, `npm audit` for frontend. Run on every PR. High/Critical severity blocks merge.
- **FR-TEST-121** — **Static analysis:** `gosec` for Go, `bandit` for Python, `eslint-plugin-security` for frontend.
- **FR-TEST-122** — **Container scanning:** `trivy` scans all built images. High/Critical CVEs block deployment.
- **FR-TEST-123** — **OWASP ZAP baseline scan** in CI on staging deployment. Verifies no high-risk findings on public endpoints.
- **FR-TEST-124** — **Secret detection:** `gitleaks` pre-commit hook + CI check. Prevents accidental secret commits.
- **FR-TEST-125** — **JWT security tests:** expired token rejected, tampered token rejected, signature algorithm confusion rejected, missing claims rejected.
- **FR-TEST-126** — **SQL injection tests:** injection attempts on all query params verified blocked (parameterized queries).
- **FR-TEST-127** — **Rate limit bypass tests:** attempts to bypass rate limits via IP spoofing, multiple tokens, concurrent requests all blocked.

---

## Summary of Required Test Artifacts

Each service in the monorepo must include:

**For Go services (`services/<name>/`):**
- `internal/**/*_test.go` — unit tests
- `tests/integration/*_test.go` — integration tests with testcontainers
- `tests/contract/*_test.go` — gRPC contract tests (where applicable)

**For Python services (`services/<name>/`):**
- `tests/unit/` — unit tests
- `tests/integration/` — integration tests with testcontainers
- `tests/fixtures/` — test data

**For frontend (`frontend/`):**
- `src/**/__tests__/` — component tests (Vitest + RTL)
- `tests/e2e/` — Playwright tests
- `tests/fixtures/` — MSW handlers

**At repository root:**
- `tests/kind/` — kind cluster config and helpers
- `tests/fixtures/` — shared cross-service fixtures
- `tests/e2e/` — API + WebSocket E2E tests
- `tests/usecase/` — user journey tests (UJ-01 through UJ-15)
- `tests/load/` — K6 load test scripts (already in epic 10)
- `helm/estategap/tests/` — helm-unittest suite

---

## Proposed New Epic and Features

A new **Epic 11: Testing & Quality Assurance** is added to the development backlog with the following features:

| Feature | Scope |
|---|---|
| 11.1 — Kind environment & Helm validation | kind cluster config, Makefile targets, image loading, seed data, helm lint/template/install/upgrade tests, helm-unittest suite |
| 11.2 — Unit, integration & contract tests | Test framework per service (Go, Python, frontend), testcontainers setup, Protobuf/OpenAPI contract tests, mock libraries |
| 11.3 — E2E test suite (API + UI) | REST/WebSocket API tests against deployed kind cluster, Playwright browser tests, visual regression tests |
| 11.4 — Use case / user journey tests | 15 realistic end-to-end user journeys (UJ-01 through UJ-15) covering critical business flows |
