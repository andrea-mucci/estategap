# Feature Specification: Scrape Orchestrator & Proxy Manager

**Feature Branch**: `010-scrape-orchestrator-proxy`  
**Created**: 2026-04-17  
**Status**: Draft  

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Scheduled Scrape Job Dispatch (Priority: P1)

An operations engineer configures portals in the database. The system automatically discovers enabled portals on startup, creates a scheduler per portal using its configured frequency, and publishes scraping jobs to the correct NATS stream at the right intervals without manual intervention.

**Why this priority**: Core automation capability — without reliable scheduled dispatch, no scraping occurs.

**Independent Test**: Can be tested by inserting a portal row in DB, starting the service, and confirming NATS messages appear on `scraper.commands.{country}.{portal}` at the configured interval.

**Acceptance Scenarios**:

1. **Given** an enabled portal with `scrape_frequency=15min` is in the DB, **When** the orchestrator starts, **Then** a job is published to `scraper.commands.{country}.{portal}` within 15 minutes and repeats every 15 minutes.
2. **Given** a portal is disabled (`enabled=false`), **When** the orchestrator starts, **Then** no jobs are published for that portal.
3. **Given** the orchestrator is running and receives SIGHUP, **When** a new portal was added to the DB, **Then** the scheduler picks it up and begins publishing jobs.

---

### User Story 2 - Manual Job Trigger (Priority: P1)

An operations engineer or automated system needs to trigger an immediate scraping job outside of the regular schedule — for example, after a portal configuration change or to backfill missing data.

**Why this priority**: Critical for operational control and incident recovery.

**Independent Test**: Can be tested by calling `POST /jobs/trigger` and verifying a NATS message is published immediately and the job is trackable via `GET /jobs/{id}/status`.

**Acceptance Scenarios**:

1. **Given** the orchestrator is running, **When** `POST /jobs/trigger` is called with a valid portal and mode, **Then** a job message is immediately published to the correct NATS subject.
2. **Given** a manual trigger fires, **When** `GET /jobs/{id}/status` is called with the returned job ID, **Then** it returns the current status (pending/running/completed/failed) and timestamps.

---

### User Story 3 - Healthy Proxy Selection (Priority: P1)

A Python scraper worker requests a proxy for a specific country and portal. The proxy manager returns a healthy, non-blacklisted proxy within milliseconds, with optional sticky-session support for paginated crawls.

**Why this priority**: All scraping is blocked without functional proxy assignment.

**Independent Test**: Can be tested by calling `GetProxy(country, portal, "")` and verifying a proxy URL is returned from the pool, then calling `ReportResult` with a failure to verify health tracking updates.

**Acceptance Scenarios**:

1. **Given** a pool of proxies for country "IT", **When** `GetProxy("IT", "immobiliare", "")` is called, **Then** a healthy proxy is returned within 10ms.
2. **Given** a proxy has received 3 consecutive 429 responses, **When** `GetProxy` is called, **Then** the blacklisted proxy is not returned for 30 minutes.
3. **Given** a sticky session ID is provided, **When** `GetProxy("IT", "immobiliare", "session-123")` is called twice, **Then** the same proxy is returned both times.

---

### User Story 4 - Proxy Health Observability (Priority: P2)

A platform engineer monitors the proxy pool health via Prometheus metrics to detect degradation, blacklist spikes, or pool exhaustion before they impact scraping quality.

**Why this priority**: Essential for proactive operations; without metrics, failures are invisible until scraping stops entirely.

**Independent Test**: Can be tested by querying `/metrics` on the proxy manager and verifying gauges for pool size, healthy count, and block rate are present per country.

**Acceptance Scenarios**:

1. **Given** the proxy manager is running, **When** `/metrics` is scraped, **Then** `proxy_pool_size{country="IT"}`, `proxy_healthy_count{country="IT"}`, and `proxy_block_rate{country="IT"}` are present.
2. **Given** a proxy is blacklisted, **When** metrics are scraped, **Then** `proxy_healthy_count` decreases and `proxy_block_rate` increases.

---

### User Story 5 - Job Status Observability (Priority: P2)

An operations engineer queries current job statistics — how many jobs are pending, running, completed, or failed — to assess scraping pipeline throughput and detect stalls.

**Why this priority**: Operational visibility into the scraping pipeline.

**Independent Test**: Can be tested by triggering multiple jobs and calling `GET /jobs/stats` to verify counts reflect actual job states.

**Acceptance Scenarios**:

1. **Given** 5 completed and 2 failed jobs exist in Redis, **When** `GET /jobs/stats` is called, **Then** it returns `{completed: 5, failed: 2, pending: 0, running: 0}`.

---

### Edge Cases

- What happens when all proxies for a country are blacklisted? (Return error, not hang)
- What happens when the DB is unreachable at startup? (Fail fast with clear error)
- What happens when NATS is unreachable during job publish? (Retry with backoff, mark job failed after N retries)
- What happens when a portal's `scrape_frequency` is updated in DB? (Picked up on next reload cycle)
- What happens when `GetProxy` is called for a country with no configured proxies? (Return NOT_FOUND gRPC error)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The orchestrator MUST load all enabled portals from PostgreSQL on startup and create one scheduler ticker per portal at its configured `scrape_frequency`.
- **FR-002**: The orchestrator MUST publish job messages to `scraper.commands.{country}.{portal}` NATS subjects on each ticker fire.
- **FR-003**: Job messages MUST contain: `job_id`, `portal`, `country`, `mode` (full/incremental), `zone_filter`, `search_url`, `created_at`.
- **FR-004**: The orchestrator MUST track job state (`pending`, `running`, `completed`, `failed`) in Redis with a 24-hour TTL.
- **FR-005**: The orchestrator MUST expose `POST /jobs/trigger`, `GET /jobs/{id}/status`, and `GET /jobs/stats` on port 8082.
- **FR-006**: The orchestrator MUST reload portal configurations on SIGHUP signal or every 5 minutes, adding new tickers and stopping removed ones.
- **FR-007**: Full sweep mode MUST run every 6 hours; incremental mode MUST run every 15 minutes for priority zones.
- **FR-008**: The proxy manager MUST implement a gRPC `ProxyService` with `GetProxy` and `ReportResult` RPCs.
- **FR-009**: The proxy pool MUST be organized by country and loaded from environment configuration at startup.
- **FR-010**: `GetProxy` MUST return a healthy, non-blacklisted proxy using round-robin selection weighted by health score.
- **FR-011**: Proxies receiving 403 or 429 status codes MUST be blacklisted for 30 minutes.
- **FR-012**: Sticky sessions MUST return the same proxy for a given `session_id` within a 10-minute window.
- **FR-013**: Health scores MUST be computed from a sliding window of the last 100 results; proxies with score < 0.5 are unhealthy.
- **FR-014**: The proxy manager MUST support Bright Data, SmartProxy, and Oxylabs via an adapter pattern.
- **FR-015**: The proxy manager MUST expose Prometheus metrics: `proxy_pool_size`, `proxy_healthy_count`, `proxy_block_rate` per country.

### Key Entities

- **Portal**: A scraping target with name, country, enabled flag, scrape frequency, and a set of search URLs.
- **ScrapeJob**: A unit of work with ID, portal reference, country, mode, zone filter, search URL, status, and lifecycle timestamps.
- **Proxy**: A residential IP endpoint with provider, country, address, health score, and blacklist state.
- **StickySession**: A binding between a session identifier and a specific proxy, with a TTL.
- **ProxyHealthWindow**: A rolling log of the last 100 request results (success/failure) for a given proxy.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Scraping jobs for all enabled portals are published on schedule with zero missed ticks under normal operating conditions.
- **SC-002**: A manually triggered job appears in the NATS stream within 1 second of the API call.
- **SC-003**: Job status is queryable at any point during its lifecycle with accurate state and timestamps.
- **SC-004**: A healthy proxy is returned within 10ms of a `GetProxy` request under normal pool conditions.
- **SC-005**: A blacklisted proxy is never returned within 30 minutes of receiving a 403 or 429 response.
- **SC-006**: Sticky session requests for the same session ID always return the same proxy within the 10-minute session window.
- **SC-007**: Prometheus metrics accurately reflect pool health state within one scrape interval.
- **SC-008**: Portal configuration changes are picked up within 5 minutes without service restart.

## Assumptions

- The `portals` table already exists in PostgreSQL with columns: `name`, `country`, `enabled`, `scrape_frequency` (interval), `search_urls` (text array).
- NATS JetStream streams for `scraper.commands.*` subjects are pre-created by infrastructure; the orchestrator only publishes.
- Proxy credentials are provided via environment variables at deployment time; no UI for proxy management is required.
- The proxy provider adapter only needs to construct the correct proxy URL format for each provider; actual HTTP routing through the proxy is handled by the scraper workers.
- A single Redis instance (shared with API Gateway) is available; key namespacing prevents collisions.
- The gRPC `ProxyService` proto definition will be added to the shared `proto/` directory.
- IPv6 proxies are out of scope; only IPv4 residential proxies are supported.
