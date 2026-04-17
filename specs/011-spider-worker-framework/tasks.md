# Tasks: Spider Worker Framework & Portal Spiders

**Input**: Design documents from `specs/011-spider-worker-framework/`  
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Tests**: Unit tests for parsers and registry; integration tests for NATS consumer round-trip and Redis dedup.

**Organization**: Tasks grouped by user story — each phase is independently testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared state dependencies)
- **[Story]**: Which user story this task belongs to (US1–US6, mapping to spec.md)

---

## Phase 1: Setup (Service Scaffold)

**Purpose**: Create the `services/spider-workers/` service from scratch with the same structure as existing Python services (`pipeline`, `ai-chat`).

- [X] T001 Create service directory tree: `services/spider-workers/`, `services/spider-workers/estategap_spiders/`, `services/spider-workers/estategap_spiders/spiders/`, `services/spider-workers/tests/unit/`, `services/spider-workers/tests/integration/`
- [X] T002 Create `services/spider-workers/pyproject.toml` with all dependencies from plan.md (nats-py, httpx, parsel, playwright, playwright-stealth, grpcio, redis, prometheus-client, pydantic-settings, structlog) and uv editable link to `libs/common`
- [X] T003 [P] Create `services/spider-workers/.env.example` with all env vars from quickstart.md (NATS_URL, REDIS_URL, PROXY_MANAGER_ADDR, METRICS_PORT, LOG_LEVEL, IDEALISTA_API_TOKEN, REQUEST_MIN_DELAY, REQUEST_MAX_DELAY, MAX_CONCURRENT_PER_PORTAL, SESSION_ROTATION_EVERY, QUARANTINE_TTL_DAYS)
- [X] T004 [P] Create `services/spider-workers/Dockerfile` — multi-stage Python 3.12 slim image; add `RUN playwright install chromium --with-deps` layer after `uv sync`
- [X] T005 Create `services/spider-workers/estategap_spiders/__init__.py` and `services/spider-workers/estategap_spiders/py.typed` (empty marker)
- [X] T006 Create `services/spider-workers/tests/__init__.py`, `tests/unit/__init__.py`, `tests/integration/__init__.py`, and `tests/conftest.py` with shared async fixtures (mock Redis, mock NATS)
- [X] T007 Create `services/spider-workers/main.py` skeleton: import config, start prometheus HTTP server on METRICS_PORT, call `consumer.run(config)` via `asyncio.run()`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure modules required by every spider and the consumer. **No user story work can begin until this phase is complete.**

**⚠️ CRITICAL**: All Phase 3+ tasks depend on these modules existing.

- [X] T008 Implement `services/spider-workers/estategap_spiders/config.py` — `pydantic_settings.BaseSettings` subclass reading all env vars from T003; include `model_config = SettingsConfigDict(env_file=".env")`
- [X] T009 [P] Implement `services/spider-workers/estategap_spiders/models.py` — `ScraperCommand` Pydantic v2 model matching Go `ScrapeJob` struct (job_id, portal, country, mode, zone_filter, search_url, created_at); add `model_validator` to normalise `country` and `portal` to lowercase
- [X] T010 [P] Implement `services/spider-workers/estategap_spiders/proxy_client.py` — thin async wrapper around `ProxyServiceStub` from `libs/common/proto/estategap/v1/proxy_pb2_grpc.py`; expose `async get_proxy(country, portal, session_id) -> ProxyAssignment` and `async report_result(proxy_id, success, status_code, latency_ms)`; `ProxyAssignment` dataclass with `proxy_url` and `proxy_id`
- [X] T011 Implement `services/spider-workers/estategap_spiders/http_client.py` — `HttpClient` async class with: `httpx.AsyncClient` initialised with injected proxy URL and 30s timeout; `USER_AGENTS` class variable (50+ desktop + mobile UA strings); per-request random UA header; `asyncio.Semaphore` for concurrency control; `is_blocked(response) -> bool` checking status 403/429 and captcha/robot/challenge body keywords; `async get(url) -> httpx.Response` with `asyncio.sleep(random.uniform(min_delay, max_delay))` before each request
- [X] T012 [P] Implement retry decorator in `services/spider-workers/estategap_spiders/http_client.py` — `@retry(max_attempts=3, base_delay=2.0, backoff=2.0)` async decorator; raises `PermanentFailureError` after all attempts exhausted; logs each retry attempt via structlog
- [X] T013 [P] Implement `services/spider-workers/estategap_spiders/browser.py` — `async fetch_with_browser(url, proxy_url) -> str`; launches `playwright.async_api` chromium headless with proxy; applies `playwright_stealth.stealth_async(context)` to the browser context; navigates to URL with `wait_until="networkidle"`; returns page HTML; always closes browser on exit
- [X] T014 [P] Implement `services/spider-workers/estategap_spiders/quarantine.py` — `QuarantineStore` async class wrapping `redis.asyncio.Redis`; `async add(url, portal, country, error)` serialises a `QuarantineEntry` (Pydantic model) to JSON and stores in Redis hash `quarantine:{portal}:{country}` with `QUARANTINE_TTL_DAYS` expiry; `async is_quarantined(url, portal, country) -> bool`
- [X] T015 [P] Implement `services/spider-workers/estategap_spiders/metrics.py` — define three `prometheus_client` metrics: `listings_scraped_total` (Counter, labels: portal, country), `scrape_errors_total` (Counter, labels: portal, country, error_type), `scrape_duration_seconds` (Histogram, labels: portal, country, buckets: 10/30/60/120/300/600/1800); `start_metrics_server(port)` calls `prometheus_client.start_http_server(port)`

**Checkpoint**: Foundation modules complete — user story implementation can begin.

---

## Phase 3: User Story 1 — Framework Dynamically Loads Any Spider (P1) 🎯 MVP

**Goal**: A working NATS consumer that routes scrape commands to any registered spider, publishes `RawListing` messages to `raw.listings.{country}`, and retries + quarantines failures.

**Independent Test**: Start the worker with only the stub spider from `tests/conftest.py`; publish a test `ScraperCommand` to NATS; verify a `RawListing` message appears on `raw.listings.es` and that the stub spider was invoked.

### Implementation for User Story 1

- [X] T016 [US1] Implement `services/spider-workers/estategap_spiders/spiders/base.py` — `BaseSpider` ABC with `COUNTRY: ClassVar[str]` and `PORTAL: ClassVar[str]` class variables; `__init_subclass__` hook that registers concrete subclasses in `REGISTRY` keyed by `(COUNTRY.lower(), PORTAL.lower())`; three abstract async methods: `scrape_search_page(zone: str, page: int) -> list[RawListing]`, `scrape_listing_detail(url: str) -> RawListing | None`, `detect_new_listings(zone: str, since_ids: set[str]) -> list[str]`; constructor accepts `Config` instance
- [X] T017 [US1] Implement `services/spider-workers/estategap_spiders/spiders/__init__.py` — declare `REGISTRY: dict[tuple[str, str], type[BaseSpider]] = {}`; import `es_idealista` and `es_fotocasa` modules at module level (triggers `__init_subclass__` registration); expose `get_spider(country, portal) -> type[BaseSpider] | None` helper
- [X] T018 [US1] Implement `services/spider-workers/estategap_spiders/consumer.py` — `async run(config: Config)` function; connects to NATS JetStream; creates pull subscriber on `scraper.commands.>` with durable name `spider-worker` and stream `SCRAPER_COMMANDS`; fetch loop parses each message as `ScraperCommand`; looks up spider class from `REGISTRY`; NAKs unknown portals; on known portal: instantiates spider, dispatches to `_run_full_scrape` or `_run_detect_new` based on `command.mode`; ACKs on success, NAKs with delay on transient error
- [X] T019 [US1] [US5] Implement `_run_full_scrape(spider, command, js, config)` in `consumer.py` — iterates `scrape_search_page` page-by-page until empty result; for each `RawListing`: serialises to JSON and publishes to `raw.listings.{country_code.lower()}`; on `PermanentFailureError`: calls `quarantine.add()`; increments `LISTINGS_SCRAPED` or `SCRAPE_ERRORS` metrics; wraps the full run in `SCRAPE_DURATION.time()` context manager
- [X] T020 [US1] Add unit tests for spider registry in `services/spider-workers/tests/unit/test_registry.py` — test: stub spider auto-registers on class definition; `get_spider("es", "test")` returns correct class; `get_spider("es", "unknown")` returns `None`; registration key is case-insensitive

**Checkpoint**: Framework wired end-to-end. Any spider class with `COUNTRY`/`PORTAL` classvars is auto-discovered and routable.

---

## Phase 4: User Story 2 — Idealista Spain Spider (P1)

**Goal**: Idealista ES spider scrapes ≥100 listings/zone with >80% field completeness using mobile API primary strategy and HTML parsel fallback.

**Independent Test**: Run `consumer.py` with only the Idealista spider loaded; publish a `ScraperCommand` for a Madrid zone; verify ≥100 `RawListing` messages published to `raw.listings.es` with price, area, rooms, GPS, and photos populated.

### Implementation for User Story 2

- [X] T021 [US2] Create `services/spider-workers/estategap_spiders/spiders/es_idealista.py` — `IdealistaSpider(BaseSpider)` class with `COUNTRY = "ES"` and `PORTAL = "idealista"`; constructor calls `super().__init__(config)`; add `_api_token` from config; add `_session_rotation_count` counter
- [X] T022 [US2] Implement Strategy 1 (mobile API) in `es_idealista.py` — `async _fetch_api_page(zone, page) -> dict` POSTs to `https://api.idealista.com/3.5/es/search` with JSON body (numPage, maxItems=50, zone params), headers `Authorization: Bearer {token}` and `User-Agent: idealista/8.x (Android 13)`; parses JSON response `{"elementList": [...], "totalPages": N}` and returns raw dict; on 401/403: marks token as invalid, returns empty
- [X] T023 [US2] Implement `_map_api_response(element: dict, zone: str) -> RawListing` in `es_idealista.py` — maps all Idealista API JSON fields to `raw_json` schema from data-model.md: price → `price`, size → `area_m2`, rooms → `rooms`, bathrooms → `bathrooms`, floor → `floor`, hasLift → `has_elevator`, parkingSpace.hasParkingSpace → `has_parking`, hasTerrace → `has_terrace`, orientation → `orientation`, status → `condition`, constructionYear → `year_built`, energyCertification.energyConsumption.rating → `energy_cert`, latitude/longitude → GPS fields, multimedia.images[].url → `photos`, description → `description`, suggestedTexts.title → context, contact.agency.name → `agent_name`
- [X] T024 [US2] Implement Strategy 2 (HTML fallback) in `es_idealista.py` — `async _fetch_html_page(url: str) -> str`: calls `http_client.get(url)`; if `is_blocked(response)`: calls `browser.fetch_with_browser(url, proxy_url)` instead; `_parse_search_html(html, zone) -> list[RawListing]`: parsel CSS `.item-info-container` for listing list; extracts `href` for detail URL and `external_id` from URL path
- [X] T025 [US2] Implement `scrape_listing_detail` in `es_idealista.py` — fetches detail page HTML (with httpx → Playwright fallback); uses parsel to extract: `.info-features span` for area/rooms/floor/bathrooms, `.price-features__container` for price, `img[src*="img3.idealista.com"]` for photos, `<script type="application/ld+json">` JSON-LD for GPS coordinates; returns complete `RawListing` with all fields populated from the detail page
- [X] T026 [US2] Implement `scrape_search_page(zone, page) -> list[RawListing]` in `es_idealista.py` — tries `_fetch_api_page` first; if result empty or API unavailable: falls back to `_fetch_html_page`; paginates via `?pagina={page}` (HTML) or `numPage={page}` (API); returns empty list when no results (signals consumer to stop pagination)
- [X] T027 [US2] Add unit tests for Idealista parser in `services/spider-workers/tests/unit/test_es_idealista.py` — fixture: sample API JSON response (20 listings) and sample HTML search result page; test: `_map_api_response` correctly maps all non-null fields; `_parse_search_html` returns correct listing URLs; `scrape_search_page` returns empty list when API returns `elementList: []`; GPS extracted from JSON-LD fixture

**Checkpoint**: Idealista spider independently scrapes full listing data from fixture responses. Ready for live testing against the actual portal with proxies.

---

## Phase 5: User Story 3 — Fotocasa Spain Spider (P1)

**Goal**: Fotocasa ES spider scrapes ≥100 listings/zone with >80% field completeness from `__NEXT_DATA__` JSON embedded in HTML.

**Independent Test**: Run consumer with only Fotocasa spider loaded; publish a `ScraperCommand` for a Barcelona zone; verify ≥100 `RawListing` messages on `raw.listings.es` with correctly mapped field names.

### Implementation for User Story 3

- [X] T028 [US3] Create `services/spider-workers/estategap_spiders/spiders/es_fotocasa.py` — `FotocasaSpider(BaseSpider)` with `COUNTRY = "ES"` and `PORTAL = "fotocasa"`; implement `_extract_next_data(html: str) -> dict` using `parsel.Selector(html).css('script#__NEXT_DATA__::text').get()` followed by `json.loads()`; raises `ParseError` if tag missing
- [X] T029 [US3] Implement field mapping in `es_fotocasa.py` — `_map_listing(raw: dict, zone: str) -> RawListing`: maps Fotocasa fields to unified `raw_json` per data-model.md table (surface→area_m2, rooms→rooms, bathrooms→bathrooms, floor→floor, hasLift→has_elevator, hasParking→has_parking, hasTerrace→has_terrace, ubication.latitude→latitude, ubication.longitude→longitude, multimedia.images[].url→photos, description→description, agency.name→agent_name, energyCertificate.energyRating→energy_cert, price.amount→price); set `currency="EUR"` explicitly
- [X] T030 [US3] Implement `scrape_search_page(zone, page) -> list[RawListing]` in `es_fotocasa.py` — fetches `{search_url}?page={page}` with httpx (Playwright fallback on block); calls `_extract_next_data`; navigates `data["props"]["pageProps"]["initialProps"]["listings"]`; maps each item via `_map_listing`; reads `data["props"]["pageProps"]["totalPages"]` to determine pagination end; returns empty list on final page or parse error
- [X] T031 [US3] Implement `scrape_listing_detail(url) -> RawListing | None` in `es_fotocasa.py` — fetches detail page; extracts `__NEXT_DATA__`; navigates `data["props"]["pageProps"]["realEstate"]` for the single listing record; returns fully mapped `RawListing` with detail-level fields (description, photos, GPS, energy cert) merged from the richer detail JSON
- [X] T032 [US3] Add unit tests for Fotocasa parser in `services/spider-workers/tests/unit/test_es_fotocasa.py` — fixture: sample `__NEXT_DATA__` JSON (search page with 25 listings and detail page for one listing); test: `_extract_next_data` parses correctly; `_map_listing` maps all fields including Fotocasa-specific names; `scrape_search_page` returns empty list when `totalPages` equals current page; `scrape_listing_detail` merges detail-level fields

**Checkpoint**: Both production spiders (Idealista ES, Fotocasa ES) independently scrape and publish listings. Framework dynamically loads both via the registry.

---

## Phase 6: User Story 4 — New Listing Detection (P2)

**Goal**: Both spiders detect new listings within 15 minutes by polling newest-first search results, comparing against Redis seen-ID sets, and scraping only truly new listings.

**Independent Test**: Pre-populate Redis seen-ID set with N-1 known IDs; publish a `detect_new` mode command; verify only the 1 unseen listing URL is scraped and its `RawListing` published; a second run for the same zone publishes nothing.

### Implementation for User Story 4

- [X] T033 [US4] Add Redis seen-ID helper to `services/spider-workers/estategap_spiders/spiders/base.py` — `async _get_seen_ids(redis, zone) -> set[str]` using key `seen:{portal}:{country}:{zone}`; `async _mark_seen(redis, zone, ids: set[str])` using `redis.sadd(..., *ids)`; `async _filter_new(redis, zone, candidate_ids: set[str]) -> set[str]` using `redis.smismember` in a single round-trip
- [X] T034 [US4] Implement `detect_new_listings(zone, since_ids) -> list[str]` in `es_idealista.py` — requests search page with API param `order=publicationDate&sort=desc` (or HTML equivalent `?orden=publicacion-desc`); collects listing IDs from first 3 pages (up to 150 IDs); calls `_filter_new(redis, zone, collected_ids)` to get unseen subset; returns list of detail URLs for unseen listings; does NOT mark them as seen (marking happens after successful scrape in consumer dispatch)
- [X] T035 [US4] Implement `detect_new_listings(zone, since_ids) -> list[str]` in `es_fotocasa.py` — same approach: requests search sorted by `publicationDate` descending via URL param `?sortType=publicationDate&sortDirection=desc`; extracts IDs from `__NEXT_DATA__` first 3 pages; returns unseen listing detail URLs
- [X] T036 [US4] Implement `_run_detect_new(spider, command, js, config)` in `consumer.py` — calls `spider.detect_new_listings(zone, set())`; for each returned URL: calls `spider.scrape_listing_detail(url)`; if successful: publishes to `raw.listings.{country}`, calls `_mark_seen(redis, zone, {listing_id})`; increments metrics; handles `PermanentFailureError` → quarantine
- [X] T037 [US4] Add integration test in `services/spider-workers/tests/integration/test_seen_listings.py` — uses `testcontainers[redis]`; stub spider returns 5 listing IDs on first call and 6 on second (1 new); verify: first `detect_new` call returns 5 URLs; `seen:` key has 5 members; second call returns 1 URL; `seen:` key has 6 members

**Checkpoint**: New-listing detection working for both portals. Combined with scrape-orchestrator's 15-minute scheduling, this satisfies SC-005.

---

## Phase 7: User Story 6 — Prometheus Metrics (P2)

**Goal**: All three metrics (`listings_scraped_total`, `scrape_errors_total`, `scrape_duration_seconds`) are populated with portal/country labels and visible at `http://localhost:9102/metrics`.

**Independent Test**: Run a minimal scrape using the stub spider; `curl http://localhost:9102/metrics` and confirm all three metric families are present with correct labels.

### Implementation for User Story 6

- [X] T038 [US6] Wire `LISTINGS_SCRAPED.labels(portal=..., country=...).inc()` and `SCRAPE_DURATION.labels(...).observe(elapsed)` into `_run_full_scrape` in `consumer.py` (metrics.py already defines the objects from T015)
- [X] T039 [US6] Wire `SCRAPE_ERRORS.labels(portal=..., country=..., error_type=...).inc()` into all error paths in `consumer.py` — error_type values: `"http_blocked"` (403/captcha), `"timeout"` (httpx timeout), `"parse_error"` (extraction failure), `"quarantined"` (permanent failure), `"unknown_portal"` (registry miss)
- [X] T040 [US6] Add Kubernetes Prometheus scrape annotations to `helm/estategap/templates/spider-workers-deployment.yaml` — add pod annotations `prometheus.io/scrape: "true"`, `prometheus.io/port: "9102"`, `prometheus.io/path: "/metrics"`; set `METRICS_PORT` env var from values; also add resource limits (cpu: 2, memory: 2Gi) for Playwright headless
- [X] T041 [US6] Call `start_metrics_server(config.metrics_port)` in `services/spider-workers/main.py` before entering the consumer loop; add structured log line confirming metrics server started

**Checkpoint**: Metrics visible at `/metrics` endpoint and Kubernetes-annotated for Prometheus scraping. Satisfies SC-007.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Helm deployment manifest, linting gate, integration smoke test, and Helm validation.

- [X] T042 Create `helm/estategap/templates/spider-workers-deployment.yaml` — Kubernetes Deployment for `estategap/spider-workers`; `replicas: 1` (NATS durable consumer; horizontal scaling via multiple consumer instances each with unique durable name or via NATS consumer groups); env vars from `estategap-secrets` Secret; liveness probe on metrics port `/metrics`
- [ ] T043 [P] Run `uv run ruff check services/spider-workers/` and `uv run mypy --strict services/spider-workers/estategap_spiders/` from repo root; fix all lint and type errors
- [X] T044 [P] Add integration test for NATS consumer round-trip in `services/spider-workers/tests/integration/test_consumer.py` — publishes a `ScraperCommand` for the stub spider using `testcontainers` NATS; asserts a `RawListing` message arrives on `raw.listings.es` within 5 seconds
- [ ] T045 Run quickstart.md validation: `uv sync`, `playwright install chromium`, `pytest tests/unit/` — all pass; verify `curl http://localhost:9102/metrics` returns all three metric families after a stub scrape run

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)        → no dependencies — start immediately
Phase 2 (Foundational) → requires Phase 1 — BLOCKS all user story phases
Phase 3 (US1 + US5)   → requires Phase 2 — framework wiring
Phase 4 (US2)          → requires Phase 3 (BaseSpider ABC)
Phase 5 (US3)          → requires Phase 3 (BaseSpider ABC) — can run in parallel with Phase 4
Phase 6 (US4)          → requires Phase 4 AND Phase 5 (both spiders must implement detect_new_listings)
Phase 7 (US6)          → requires Phase 3 (consumer.py exists) — can start in parallel with Phase 4/5
Phase 8 (Polish)       → requires all prior phases
```

### User Story Dependencies

- **US1 (P1)**: Depends on Phase 2 only — no inter-story dependencies
- **US5 (P1)**: Embedded in US1 Phase 3 — co-implemented with the consumer's publish step
- **US2 (P1)**: Depends on US1 (BaseSpider ABC from T016) — no other story dependencies
- **US3 (P1)**: Depends on US1 (BaseSpider ABC from T016) — parallel with US2
- **US4 (P2)**: Depends on US2 AND US3 (both spiders must implement `detect_new_listings`)
- **US6 (P2)**: Depends on US1 consumer existing (T018) — can be wired in parallel with US2/US3

### Within Each User Story

- Spider class definition → mapping function → search page method → detail page method
- Unit test fixtures must be prepared before writing parser unit tests

---

## Parallel Opportunities

### Phase 1 (all parallelisable)

```
Task: T003 Create .env.example
Task: T004 Create Dockerfile
```

### Phase 2 (parallelisable after T008)

```
Task: T009 Create models.py (ScraperCommand)
Task: T010 Create proxy_client.py
Task: T011 Create http_client.py core (depends on T008 config)
Task: T013 Create browser.py
Task: T014 Create quarantine.py
Task: T015 Create metrics.py
```

### Phase 4 and Phase 5 (run in parallel after Phase 3)

```
Developer A: T021–T027 (Idealista spider)
Developer B: T028–T032 (Fotocasa spider)
```

### Phase 7 (can start after T018 consumer.py exists)

```
Developer C: T038–T041 (metrics wiring) — parallel with Phase 4/5
```

---

## Parallel Example: Phase 4 (Idealista Spider)

```bash
# After T021 (class skeleton) exists, these can run in parallel:
Task: "Implement Strategy 1 mobile API in es_idealista.py"      # T022
Task: "Write unit test fixtures for Idealista responses"        # part of T027
```

---

## Implementation Strategy

### MVP (User Story 1 + Framework Wire-Up Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: US1 — framework + registry + consumer + NATS publish (T016–T020)
4. **STOP and VALIDATE**: Publish a test `ScraperCommand` for a stub spider → verify `RawListing` on NATS
5. Spider framework is proven end-to-end with a trivial spider

### Incremental Delivery

1. Phases 1–2 → Foundation ready
2. Phase 3 → Framework works end-to-end with stub spider (MVP!)
3. Phase 4 → Idealista ES live (100+ listings verifiable)
4. Phase 5 → Fotocasa ES live (two-portal coverage)
5. Phase 6 → New listing detection (15-min SLA)
6. Phase 7 → Metrics visible in Grafana
7. Phase 8 → Helm deployed, CI passing

### Parallel Team Strategy

After Phase 3 completes:
- **Developer A**: Phase 4 (Idealista, T021–T027)
- **Developer B**: Phase 5 (Fotocasa, T028–T032)
- **Developer C**: Phase 7 (Metrics wiring, T038–T041)
- Phase 6 begins when A and B merge their spider branches

---

## Notes

- `[P]` tasks operate on different files with no conflicting writes — safe to parallelise
- `[US#]` label maps each task to a spec.md user story for traceability
- Each phase ends with a checkpoint — validate that phase before proceeding
- Playwright adds ~300 MB to the Docker image; ensure Kubernetes memory limits (2 Gi) are applied in T040
- The `SCRAPER_COMMANDS` JetStream stream must be provisioned by the scrape-orchestrator startup (feature 010) before the spider worker starts — document this dependency in the Helm notes
- `mypy --strict` will flag missing type annotations in any module imported from `libs/common`; use `# type: ignore[import-untyped]` only where the stub files are absent
