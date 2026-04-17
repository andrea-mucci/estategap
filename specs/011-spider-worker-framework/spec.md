# Feature Specification: Spider Worker Framework & Portal Spiders

**Feature Branch**: `011-spider-worker-framework`  
**Created**: 2026-04-17  
**Status**: Draft  
**Input**: User description: "Build the Python spider worker framework and implement the first two portal spiders (Idealista and Fotocasa for Spain)."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Framework Dynamically Loads Any Spider (Priority: P1)

A platform engineer adds support for a new real-estate portal (e.g., Pisos.com) by creating a single Python file in the spiders directory. The worker service picks it up automatically without any configuration changes or service restarts.

**Why this priority**: Extensibility is the core value of the framework. Without it every new portal requires invasive code changes and a full deployment cycle.

**Independent Test**: Deploy the framework with only the base classes and a single stub spider; confirm the NATS command routes to the stub and returns data.

**Acceptance Scenarios**:

1. **Given** a new spider file is placed in the spiders directory, **When** the worker service starts, **Then** the spider is discoverable and routable by country+portal key without any additional registration step.
2. **Given** a scrape command is published to `scraper.commands.es.idealista`, **When** the worker consumes it, **Then** the Idealista spider is selected and executed automatically.
3. **Given** a scrape command references a country+portal pair with no registered spider, **When** the worker consumes it, **Then** an error is logged and the command is rejected without crashing the worker.

---

### User Story 2 - Reliable Listing Data Collected from Idealista Spain (Priority: P1)

A data analyst triggers a zone scrape for Madrid on Idealista. The system returns structured listing records covering price, area, rooms, bathrooms, floor, elevator, parking, terrace, orientation, condition, year built, energy certificate, GPS coordinates, photos, description, and agent information — even when the site applies anti-bot measures.

**Why this priority**: Idealista is Spain's largest real-estate portal. Its data is essential for market analysis and without it the product has no value for Spanish users.

**Independent Test**: Issue a scrape command for a known Madrid zone; verify that at least 100 listings are returned and that >80% of defined fields are populated.

**Acceptance Scenarios**:

1. **Given** a zone scrape command for Idealista Spain, **When** the spider fetches search pages, **Then** paginated results are traversed until no more listings are found.
2. **Given** a listing detail URL from Idealista, **When** the spider fetches the detail page, **Then** all schema fields (price, GPS, photos, energy cert, etc.) that are present on the page are extracted.
3. **Given** the site returns a blocked response (403 or CAPTCHA), **When** the spider detects the block, **Then** it switches to the browser-based fallback and retries the same URL.
4. **Given** a URL that consistently fails across all strategies and 3 retry attempts, **When** the final retry fails, **Then** the URL is quarantined and the error is recorded without halting the broader scrape job.

---

### User Story 3 - Reliable Listing Data Collected from Fotocasa Spain (Priority: P1)

Same scenario as User Story 2 but for fotocasa.es, which uses a different page structure and embedded JSON state pattern.

**Why this priority**: Fotocasa is Spain's second-largest portal; dual-source coverage significantly improves data completeness and cross-validation.

**Independent Test**: Issue a scrape command for a known Barcelona zone on Fotocasa; verify 100+ listings returned with >80% field completeness.

**Acceptance Scenarios**:

1. **Given** a zone scrape command for Fotocasa Spain, **When** the spider fetches search pages, **Then** listing data is extracted from the embedded JSON state in each HTML response.
2. **Given** Fotocasa field names differ from the unified schema, **When** the parser processes a listing, **Then** fields are mapped correctly to the unified schema before publishing.
3. **Given** a blocked response from Fotocasa, **When** the spider detects it, **Then** the browser-based fallback is triggered identically to Story 2.

---

### User Story 4 - New Listings Detected Within 15 Minutes (Priority: P2)

A subscriber alert fires within 15 minutes of a new listing appearing on either Idealista or Fotocasa for a tracked zone. The system achieves this by polling search results sorted by newest and comparing with previously seen listing IDs.

**Why this priority**: Near-real-time detection is a key product differentiator; delayed detection reduces user trust and alert value.

**Independent Test**: Publish a synthetic "new" listing ID to the portal's newest-first search endpoint mock; confirm the system detects and scrapes it within one polling cycle (≤15 min).

**Acceptance Scenarios**:

1. **Given** a zone is being monitored, **When** a new listing appears on the portal, **Then** the system detects it within 15 minutes of first appearance.
2. **Given** a listing ID has already been seen in a previous poll, **When** it reappears in search results, **Then** it is not scraped again and no duplicate is published.
3. **Given** a poll cycle fails due to a network error, **When** the next scheduled poll runs, **Then** it completes successfully and does not miss listings published during the failed window.

---

### User Story 5 - Raw Listings Published to Messaging System with Correct Schema (Priority: P1)

Every successfully scraped listing is published as a structured message to the raw listings topic. Downstream services can consume it without additional transformation of mandatory fields.

**Why this priority**: The messaging contract is the integration boundary; incorrect schema breaks all downstream consumers simultaneously.

**Independent Test**: Consume messages from `raw.listings.es` after a test scrape; validate each message against the RawListing schema using a schema validator.

**Acceptance Scenarios**:

1. **Given** a listing is successfully scraped, **When** it is published, **Then** the message validates against the RawListing schema with all mandatory fields present.
2. **Given** a listing is published, **When** a downstream consumer reads it, **Then** it can identify the source portal, country, zone, and listing ID from the message without additional lookups.

---

### User Story 6 - Scrape Health Visible in Monitoring Dashboard (Priority: P2)

An operator opens the observability dashboard and sees per-portal metrics: total listings scraped, scrape errors, and scrape duration — updated in near real-time.

**Why this priority**: Without metrics, failures are invisible until users report missing data; proactive monitoring reduces mean time to detection.

**Independent Test**: Run a test scrape; query the metrics endpoint and confirm `listings_scraped_total`, `scrape_errors_total`, and `scrape_duration_seconds` are present with correct labels.

**Acceptance Scenarios**:

1. **Given** a scrape job completes, **When** the metrics endpoint is queried, **Then** `listings_scraped_total` is incremented by the number of listings successfully published.
2. **Given** a scrape error occurs, **When** the metrics endpoint is queried, **Then** `scrape_errors_total` is incremented with labels identifying the portal and error type.
3. **Given** a scrape job runs, **When** it finishes, **Then** `scrape_duration_seconds` records the elapsed time with portal and zone labels.

---

### Edge Cases

- What happens when a portal changes its HTML structure or API format mid-crawl?
- How does the system handle rate limiting responses (HTTP 429) versus hard blocks (403)?
- What happens if the proxy pool is exhausted and no proxies are available?
- How does the system behave when NATS is temporarily unreachable during publish?
- What happens when a listing page returns partial data (some fields unavailable)?
- How does new-listing detection handle portal-side delays in indexing new listings?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide a base spider class with abstract methods for scraping search pages, scraping detail pages, and detecting new listings.
- **FR-002**: The system MUST auto-register spider implementations upon definition, requiring no external configuration file to add a new spider.
- **FR-003**: The system MUST subscribe to scrape commands from the messaging system and route each command to the correct spider based on country and portal identifiers in the message payload.
- **FR-004**: The system MUST obtain a proxy assignment from the proxy manager service before each request batch, maintaining the same proxy for paginated crawl sessions.
- **FR-005**: The system MUST rotate User-Agent headers across requests using a pool of at least 50 distinct User-Agent strings.
- **FR-006**: The system MUST detect when an HTTP request is blocked (403, CAPTCHA markers) and automatically fall back to a browser-based rendering strategy for that URL.
- **FR-007**: The system MUST retry failed requests up to 3 times with exponential backoff before marking a URL as permanently failed.
- **FR-008**: The system MUST quarantine permanently failed URLs, recording the failure reason, without halting the broader scrape job.
- **FR-009**: The system MUST publish each successfully scraped listing as a validated RawListing message to the appropriate raw listings topic.
- **FR-010**: The Idealista spider MUST attempt a mobile API strategy first and fall back to HTML parsing if the API strategy is unavailable or blocked.
- **FR-011**: The Idealista spider MUST extract: price, area, rooms, bathrooms, floor, elevator, parking, terrace, orientation, condition, year built, energy certificate, GPS coordinates, photo URLs, description, and agent information.
- **FR-012**: The Fotocasa spider MUST extract listing data from the embedded server-side JSON state in the HTML response and map Fotocasa-specific field names to the unified schema.
- **FR-013**: The Fotocasa spider MUST extract the same set of fields as FR-011 where available.
- **FR-014**: The system MUST poll each monitored zone's search results (sorted by newest) on a configurable interval (default: every 15 minutes) and scrape only listings not previously seen.
- **FR-015**: The system MUST track seen listing IDs per zone using a persistent store to prevent duplicate scraping across poll cycles.
- **FR-016**: The system MUST apply a configurable random delay between requests (default: 2–5 seconds) to mimic human browsing behaviour.
- **FR-017**: The system MUST limit concurrent requests to a configurable maximum per portal per worker instance (default: 3).
- **FR-018**: The system MUST rotate to a new proxy after a configurable number of requests (default: every 10 requests).
- **FR-019**: The system MUST expose Prometheus-compatible metrics: `listings_scraped_total`, `scrape_errors_total`, and `scrape_duration_seconds`, each labelled with at least portal and country.

### Key Entities

- **ScraperCommand**: Instruction delivered via messaging system; contains country, portal, zone identifier, and command type (full scrape or detect-new).
- **RawListing**: Unified output record; contains all listing fields (FR-011), source portal, country, zone, listing ID, and scrape timestamp. Mandatory fields: listing ID, portal, country, price, area, GPS coordinates.
- **SpiderRegistry**: In-process map of (country, portal) → SpiderClass; populated automatically at import time.
- **ProxyAssignment**: Proxy credentials and endpoint returned by the proxy manager; scoped to a single crawl session.
- **QuarantineRecord**: Record of a permanently failed URL, including failure reason, portal, and timestamp.
- **SeenListingStore**: Per-zone persistent set of listing IDs already scraped; used to detect new listings.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Adding a new portal spider requires creating exactly one Python file with no changes to any other file or configuration.
- **SC-002**: Each spider (Idealista, Fotocasa) successfully scrapes 100 or more listings per zone in a single job run.
- **SC-003**: Each spider achieves greater than 80% field completeness (defined fields populated) across scraped listings.
- **SC-004**: No IP blocks are encountered during a 500-request test run when proxies are active and anti-bot measures are applied.
- **SC-005**: New listings are detected within 15 minutes of their first appearance on the portal.
- **SC-006**: All published raw listing messages validate against the RawListing schema; zero schema violations reach downstream consumers.
- **SC-007**: The three Prometheus metrics (`listings_scraped_total`, `scrape_errors_total`, `scrape_duration_seconds`) are visible and correctly labelled in the observability dashboard within 5 minutes of a scrape job completing.
- **SC-008**: The worker service recovers from a transient messaging-system outage and resumes publishing without data loss once connectivity is restored.

## Assumptions

- The proxy manager gRPC service (feature 010) is deployed and reachable; this feature does not implement proxy management.
- The NATS messaging system is available with JetStream enabled for durable consumer support.
- A Redis-compatible store is available for persisting seen listing IDs per zone.
- Seen listing ID sets are scoped per (portal, country, zone) key and do not expire unless explicitly cleared.
- The RawListing schema is defined in the shared data models (feature 005); this feature consumes it but does not redefine it.
- Browser-based fallback (Playwright) is available in the worker's runtime environment; installation and stealth plugin setup are part of the deployment, not this feature.
- The initial release covers Spain only (Idealista ES, Fotocasa ES); other countries are out of scope.
- Authentication tokens for the Idealista mobile API are rotated externally and injected via configuration; reverse-engineering them is part of this feature's implementation but managing token refresh is out of scope.
- Captcha solving relies on delay-and-retry strategies; third-party captcha-solving services are out of scope for v1.
- The observability stack (Prometheus, Grafana) from feature 003 is operational and scrapes the worker's metrics endpoint.
