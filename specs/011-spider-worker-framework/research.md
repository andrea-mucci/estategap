# Research: Spider Worker Framework

**Feature**: 011-spider-worker-framework  
**Date**: 2026-04-17  
**Status**: Complete — all NEEDS CLARIFICATION resolved

---

## Decision 1: NATS Consumer Pattern (JetStream pull vs push)

**Decision**: JetStream pull consumer with durable subscription.

**Rationale**: The existing `NatsClient` in `libs/common` uses a basic push subscribe (`nc.subscribe`). For the spider worker we need durable, at-least-once delivery so in-progress scrape jobs survive worker restarts. JetStream pull consumers allow the worker to control fetch rate (important for rate-limited scrapers) and avoid message overflow on slow consumers. `nats-py` (`nats.aio`) fully supports JetStream pull consumers with `js.subscribe(subject, durable=..., stream=...)`.

**Alternatives considered**:
- Push consumer (core NATS): simpler but no durability — jobs lost on worker crash.
- Celery/RQ task queue: heavier dependency, not aligned with existing NATS-first event bus.

---

## Decision 2: Spider Auto-Registration via `__init_subclass__`

**Decision**: Use Python's `__init_subclass__` hook in `BaseSpider` to populate a global registry dict keyed by `(country_code, portal_id)`.

**Rationale**: Zero-config registration — importing a spider module is sufficient to register it. The consumer module imports all spiders in `spiders/__init__.py` via `import estategap_spiders.spiders.es_idealista` etc. Adding a new spider requires only one file. Compatible with mypy strict mode (registry is typed `dict[tuple[str, str], type[BaseSpider]]`).

**Alternatives considered**:
- Explicit registration call: requires editing `__init__.py` for every new spider — fails SC-001.
- `importlib` dynamic discovery by scanning the `spiders/` directory: more complex, harder to type-check.

---

## Decision 3: gRPC Proxy Client Integration

**Decision**: Use the pre-generated stubs in `libs/common/proto/estategap/v1/proxy_pb2_grpc.py` (`ProxyServiceStub`). Wrap in a thin `ProxyClient` class in `estategap_spiders/proxy_client.py` that calls `GetProxy` before a batch and `ReportResult` after each request.

**Rationale**: The proto stubs already exist. The `GetProxyRequest` accepts `country_code`, `portal_id`, and `session_id` — exactly the parameters needed for sticky-session paginated crawls (reuse same `session_id` across pages). `grpcio` and `grpcio-tools` are already available via the common lib's generated stubs.

**Alternatives considered**:
- HTTP proxy round-robin without proxy-manager: breaks proxy rotation and health tracking already built in feature 010.

---

## Decision 4: HTTP Client — httpx Async

**Decision**: `httpx.AsyncClient` with a 30-second timeout, proxy URL injected from `ProxyClient.GetProxy`, and per-request User-Agent sampled from a 50+ entry list bundled in `http_client.py`.

**Rationale**: `httpx` is already a dependency in `services/pipeline`. Async-native, supports HTTP/2, straightforward proxy injection via `proxies={"all://": proxy_url}`. Connection pool reuse within a session.

**Block detection heuristic**: status 403, 429, or body contains `captcha` / `robot` / `challenge` keyword → mark as blocked.

**Alternatives considered**:
- `aiohttp`: similar capability but less ergonomic; not already in the stack.
- `requests`: sync, incompatible with asyncio architecture.

---

## Decision 5: Playwright Fallback — `playwright-stealth`

**Decision**: `playwright.async_api` with `playwright-stealth` applied to each page context. Launch `chromium` headless. Only instantiate when httpx is blocked (lazy init).

**Rationale**: `playwright-stealth` patches navigator properties, WebGL fingerprint, and other bot-detection signals. Lazy init avoids browser startup cost for every request. `playwright` is already listed in the constitution's Python stack.

**Alternatives considered**:
- `puppeteer` (Node): cross-language boundary, complicates the Python service.
- `selenium`: older, heavier, no stealth plugin ecosystem.
- `undetected-chromedriver`: Selenium-based, harder to maintain.

---

## Decision 6: Seen Listing ID Store — Redis SADD/SISMEMBER

**Decision**: Redis `SADD`/`SISMEMBER` per key `seen:{portal}:{country}:{zone_id}`. No TTL — sets are permanent per zone unless explicitly cleared by an operator command.

**Rationale**: Redis SADD is O(1), SISMEMBER is O(1). For typical zones with 5k–50k listings, memory usage is ~1–10 MB per zone per portal (Redis uses intset encoding for integer-like IDs). Redis 7 (already deployed, feature 003) supports this natively.

**Alternatives considered**:
- PostgreSQL set: higher latency for tight polling loops, requires schema changes outside this feature's scope.
- Bloom filter (Redis bloom module): probabilistic — false negatives would miss listings; not worth the complexity.

---

## Decision 7: Quarantine Store — Redis Hash

**Decision**: Quarantine permanently failed URLs in a Redis hash `quarantine:{portal}:{country}` → `{url: JSON{error, timestamp, attempt_count}}`. TTL: 30 days (configurable).

**Rationale**: Simple, inspectable with `redis-cli`. Reuses existing Redis infrastructure. Hash per portal/country keeps keys organised.

**Alternatives considered**:
- NATS dead-letter subject: good for observability but introduces another consumer; overkill for URL-level quarantine.

---

## Decision 8: Prometheus Metrics Exposure

**Decision**: `prometheus_client` Python library. Expose metrics via a simple HTTP server on a dedicated port (default 9102) using `start_http_server()`. Labels: `portal`, `country`.

**Metrics**:
- `listings_scraped_total` — Counter, labels: portal, country
- `scrape_errors_total` — Counter, labels: portal, country, error_type
- `scrape_duration_seconds` — Histogram, labels: portal, country

**Rationale**: `prometheus_client` is the standard Python Prometheus library. `start_http_server` runs in a background thread without blocking the asyncio event loop.

**Alternatives considered**:
- Expose via FastAPI endpoint: adds a web framework dependency not needed elsewhere in this service.

---

## Decision 9: Idealista — Mobile API vs HTML Fallback

**Decision**: Strategy 1 (primary) mimics the Idealista Android app API (JSON endpoints, `Authorization: Bearer` token injected from config, custom `User-Agent: idealista/x.y (Android)`). Strategy 2 (fallback) uses `parsel` CSS selectors on the desktop HTML page.

**Rationale**: The mobile API returns structured JSON with all listing fields in one response — superior data completeness vs HTML parsing. HTML fallback ensures coverage when token is rotated or API structure changes. `parsel` is the same library used by Scrapy, already in the Python stack.

**API endpoint pattern**: `https://api.idealista.com/3.5/es/search?...` (documented reverse-engineering; tokens injected via config, not hardcoded).

---

## Decision 10: Fotocasa — `__NEXT_DATA__` Extraction

**Decision**: Extract the `<script id="__NEXT_DATA__" type="application/json">` tag, JSON-parse it, and navigate the `props.pageProps` tree to the listing array. Use `parsel` to locate the tag, then `json.loads` the content.

**Rationale**: Fotocasa is a Next.js SSR app. The full server-rendered state is embedded in `__NEXT_DATA__`, including listing details. This is far more reliable than DOM scraping since the JSON structure is self-documenting and stable across React re-renders.

**Field mapping**: Fotocasa uses different field names (e.g., `surface` → `built_area_m2`, `rooms` → `bedrooms`). A static mapping dict in `es_fotocasa.py` translates to the unified `RawListing.raw_json` schema.

---

## Decision 11: Async Concurrency Control

**Decision**: `asyncio.Semaphore(max_concurrent)` per portal instance, default 3. Random delay via `asyncio.sleep(random.uniform(min_delay, max_delay))` between requests, configurable per portal.

**Rationale**: `asyncio.Semaphore` is the standard Python async concurrency primitive. Per-portal semaphore isolates portals so one slow portal doesn't starve another.

---

## Decision 12: Retry with Exponential Backoff

**Decision**: Decorator `@retry(max_attempts=3, base_delay=2.0, backoff=2.0)` applied to `fetch()` in the HTTP client. After 3 failures, raise `PermanentFailure` which the spider catches and routes to quarantine.

**Rationale**: Consistent retry logic in one place rather than per-spider. Exponential backoff (2s, 4s, 8s) avoids hammering a temporarily overloaded portal. Base delay is configurable.

---

## All Clarifications Resolved

No `NEEDS CLARIFICATION` markers remain. All decisions above are consistent with:
- The existing `RawListing` schema in `libs/common` (uses `raw_json: dict[str, Any]` — spider stores all extracted fields here)
- The existing NATS infrastructure (JetStream enabled)
- The existing proxy gRPC stubs
- The constitution's Python stack requirements (Pydantic v2, asyncio, httpx, Scrapy/Playwright, structlog, ruff, mypy strict)
