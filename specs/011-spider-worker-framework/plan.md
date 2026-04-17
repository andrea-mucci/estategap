# Implementation Plan: Spider Worker Framework & Portal Spiders

**Branch**: `011-spider-worker-framework` | **Date**: 2026-04-17 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `specs/011-spider-worker-framework/spec.md`

---

## Summary

Implement a Python async spider worker service (`services/spider-workers/`) that: (1) consumes scrape commands from NATS JetStream, (2) dynamically routes them to registered spiders via a `__init_subclass__` registry, (3) executes HTTP + Playwright-based scraping with proxy rotation and anti-bot measures, and (4) publishes validated `RawListing` messages to NATS. Two production spiders ship in this feature: Idealista Spain (mobile API primary, HTML fallback) and Fotocasa Spain (`__NEXT_DATA__` JSON extraction). New-listing detection polls on a 15-minute cycle, diffing against Redis seen-ID sets.

---

## Technical Context

**Language/Version**: Python 3.12  
**Primary Dependencies**: nats-py, httpx, parsel, playwright, playwright-stealth, grpcio, redis, prometheus_client, pydantic-settings, structlog, uv  
**Storage**: Redis 7 (seen listing IDs, quarantine records) — no PostgreSQL writes in this service  
**Testing**: pytest, pytest-asyncio, pytest-httpx, respx (httpx mocking), testcontainers[redis]  
**Target Platform**: Linux container (Kubernetes), same node as proxy-manager or adjacent  
**Project Type**: Standalone Python microservice consuming from and publishing to NATS  
**Performance Goals**: ≥100 listings/zone/run; ≤15 min new-listing detection latency; ≤3 concurrent requests per portal  
**Constraints**: Robots.txt must be respected (constitution §VI); no secrets in code; mypy strict; ruff lint passing  
**Scale/Scope**: Spain only (ES) at launch; 2 portals (Idealista, Fotocasa); horizontally scalable via NATS durable consumer

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Polyglot Service Architecture | ✅ PASS | Python service in `services/spider-workers/`; no cross-service package imports |
| II. Event-Driven Communication | ✅ PASS | Inbound: NATS JetStream `scraper.commands.>`; Outbound: NATS `raw.listings.{country}`; Proxy: gRPC |
| III. Country-First Data Sovereignty | ✅ PASS | All data partitioned by `country_code`; NATS subjects include country; Redis keys scoped by country |
| IV. ML-Powered Intelligence | N/A | No ML in this service |
| V. Code Quality Discipline | ✅ PASS | Pydantic v2 models, asyncio + httpx, structlog, ruff + mypy strict, pytest-asyncio |
| VI. Security & Ethical Scraping | ✅ PASS | Robots.txt respected per spider; geo-targeted proxies via proxy-manager; configurable throttling; no secrets in code |
| VII. Kubernetes-Native Deployment | ✅ PASS | Dockerfile required; Helm chart update required |

**Post-design re-check**: No violations introduced. Service is standalone; `libs/common` dependency is within the allowed `libs/` shared code boundary.

---

## Project Structure

### Documentation (this feature)

```text
specs/011-spider-worker-framework/
├── plan.md              ← this file
├── research.md          ← Phase 0: all decisions resolved
├── data-model.md        ← Phase 1: entities and schemas
├── quickstart.md        ← Phase 1: developer onboarding
├── contracts/
│   └── nats-subjects.md ← Phase 1: NATS in/out contracts
└── tasks.md             ← Phase 2 (/speckit.tasks command)
```

### Source Code

```text
services/spider-workers/
├── Dockerfile
├── pyproject.toml
├── .env.example
├── main.py                                  # async entrypoint
├── estategap_spiders/
│   ├── __init__.py
│   ├── py.typed
│   ├── config.py                            # pydantic-settings config
│   ├── consumer.py                          # NATS JetStream pull consumer
│   ├── metrics.py                           # Prometheus counters/histograms
│   ├── models.py                            # ScraperCommand Pydantic model
│   ├── proxy_client.py                      # gRPC ProxyService wrapper
│   ├── quarantine.py                        # Redis quarantine store
│   ├── http_client.py                       # httpx + UA rotation + retry
│   ├── browser.py                           # Playwright async fallback
│   └── spiders/
│       ├── __init__.py                      # REGISTRY + auto-import
│       ├── base.py                          # BaseSpider ABC + __init_subclass__
│       ├── es_idealista.py                  # Idealista ES spider
│       └── es_fotocasa.py                   # Fotocasa ES spider
└── tests/
    ├── __init__.py
    ├── conftest.py                          # shared fixtures (mock NATS, mock Redis)
    ├── unit/
    │   ├── __init__.py
    │   ├── test_registry.py                 # auto-registration behaviour
    │   ├── test_http_client.py              # UA rotation, proxy injection, retry
    │   ├── test_quarantine.py               # quarantine logic
    │   ├── test_es_idealista.py             # unit parse tests (fixture HTML/JSON)
    │   └── test_es_fotocasa.py              # unit parse tests
    └── integration/
        ├── __init__.py
        ├── test_consumer.py                 # NATS → spider → NATS round-trip (testcontainers)
        └── test_seen_listings.py            # Redis seen-ID dedup (testcontainers)
```

**Structure Decision**: Single Python service using the same layout as `services/pipeline/` and `services/ai-chat/`. Package name: `estategap_spiders`. The `spiders/` sub-package contains the registry and all spider implementations.

---

## Implementation Design

### 1. `BaseSpider` and Registry (`spiders/base.py`, `spiders/__init__.py`)

```python
# spiders/base.py
from abc import ABC, abstractmethod
from typing import ClassVar
from estategap_common.models.listing import RawListing

class BaseSpider(ABC):
    COUNTRY: ClassVar[str]   # e.g. "ES"
    PORTAL: ClassVar[str]    # e.g. "idealista"

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if hasattr(cls, "COUNTRY") and hasattr(cls, "PORTAL"):
            from estategap_spiders.spiders import REGISTRY
            REGISTRY[(cls.COUNTRY.lower(), cls.PORTAL.lower())] = cls

    @abstractmethod
    async def scrape_search_page(
        self, zone: str, page: int
    ) -> list[RawListing]: ...

    @abstractmethod
    async def scrape_listing_detail(self, url: str) -> RawListing | None: ...

    @abstractmethod
    async def detect_new_listings(
        self, zone: str, since_ids: set[str]
    ) -> list[str]: ...  # returns new listing URLs
```

```python
# spiders/__init__.py — auto-import triggers registration
from typing import TYPE_CHECKING
REGISTRY: dict[tuple[str, str], type["BaseSpider"]] = {}

from estategap_spiders.spiders import es_idealista, es_fotocasa  # noqa: E402, F401
```

---

### 2. `ScraperCommand` and NATS Consumer (`models.py`, `consumer.py`)

The consumer subscribes to the `SCRAPER_COMMANDS` JetStream stream with a durable pull consumer. On each message:

1. Parse JSON → `ScraperCommand`
2. Lookup `REGISTRY[(command.country.lower(), command.portal.lower())]`
3. Instantiate spider and call `scrape_search_page` (mode=`full`) or `detect_new_listings` (mode=`detect_new`)
4. Publish each `RawListing` to `raw.listings.{country}`
5. ACK message on success; NAK with delay on transient failure; quarantine on permanent failure

```python
# consumer.py (simplified flow)
async def run(config: Config) -> None:
    nc = await nats.connect(config.nats_url)
    js = nc.jetstream()
    sub = await js.pull_subscribe("scraper.commands.>", durable="spider-worker", stream="SCRAPER_COMMANDS")
    async for msg in fetch_loop(sub):
        cmd = ScraperCommand.model_validate_json(msg.data)
        spider_cls = REGISTRY.get((cmd.country.lower(), cmd.portal.lower()))
        if spider_cls is None:
            await msg.nak()
            continue
        spider = spider_cls(config)
        await dispatch(spider, cmd, js, config)
        await msg.ack()
```

---

### 3. HTTP Client with UA Rotation and Proxy Injection (`http_client.py`)

```python
class HttpClient:
    USER_AGENTS: ClassVar[list[str]] = [...]  # 50+ desktop/mobile UAs

    def __init__(self, proxy: ProxyAssignment, config: Config) -> None:
        self._client = httpx.AsyncClient(
            proxy=proxy.proxy_url,
            timeout=30.0,
            headers={"User-Agent": random.choice(self.USER_AGENTS)},
            follow_redirects=True,
        )
        self._request_count = 0
        self._semaphore = asyncio.Semaphore(config.max_concurrent_per_portal)

    async def get(self, url: str, **kwargs: object) -> httpx.Response:
        async with self._semaphore:
            await asyncio.sleep(
                random.uniform(config.request_min_delay, config.request_max_delay)
            )
            resp = await self._retry_get(url, **kwargs)
            self._request_count += 1
            return resp

    def is_blocked(self, response: httpx.Response) -> bool:
        return response.status_code in {403, 429} or any(
            marker in response.text.lower()
            for marker in ("captcha", "robot", "challenge", "access denied")
        )
```

**Retry decorator** (`@retry(max_attempts=3, base_delay=2.0, backoff=2.0)`): implemented as an async decorator in `http_client.py`. Raises `PermanentFailureError` after exhausting attempts.

---

### 4. Playwright Browser Fallback (`browser.py`)

```python
async def fetch_with_browser(url: str, proxy: ProxyAssignment) -> str:
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            proxy={"server": proxy.proxy_url},
        )
        context = await browser.new_context()
        await stealth_async(context)   # playwright-stealth
        page = await context.new_page()
        await page.goto(url, wait_until="networkidle")
        content = await page.content()
        await browser.close()
        return content
```

The spider calls `fetch_with_browser` only when `http_client.is_blocked(response)` is True.

---

### 5. Idealista Spider (`es_idealista.py`)

**Strategy 1 — Mobile API**:
- Endpoint: `https://api.idealista.com/3.5/es/search` with POST body (search params)
- Headers: `Authorization: Bearer {config.idealista_api_token}`, `User-Agent: idealista/8.x (Android 13)`
- Response: JSON `{"elementList": [...], "totalPages": N}`
- Each element is a complete listing record; map to `raw_json`

**Strategy 2 — HTML (parsel)**:
- GET `{search_url}?pagina={page}`
- Parse with `parsel.Selector`
- Search results: `.item-info-container` divs → extract ID, URL, basic fields
- Detail page: `.info-features span`, `.price-features__container`, JSON-LD `<script type="application/ld+json">` for GPS
- Photos: `img[src*="img3.idealista.com"]`

**Pagination**: Increment `page` until the response contains no listings or API returns `totalPages < page`.

**New listing detection**:
- Request search with `order=publicationDate&sort=desc`
- Parse first 50 IDs
- `await redis.sdiff("seen:idealista:es:{zone}", set_of_new_ids)` → return only truly new IDs

---

### 6. Fotocasa Spider (`es_fotocasa.py`)

**Data extraction**:
```python
selector = parsel.Selector(html)
next_data_raw = selector.css('script#__NEXT_DATA__::text').get()
data = json.loads(next_data_raw)
listings = data["props"]["pageProps"]["initialProps"]["listings"]
```

**Field mapping** (Fotocasa → unified `raw_json`):
| Fotocasa field | raw_json field |
|----------------|---------------|
| `id` | `external_id` |
| `price.amount` | `price` |
| `surface` | `area_m2` |
| `rooms` | `rooms` |
| `bathrooms` | `bathrooms` |
| `floor` | `floor` |
| `hasLift` | `has_elevator` |
| `hasParking` | `has_parking` |
| `hasTerrace` | `has_terrace` |
| `ubication.latitude` | `latitude` |
| `ubication.longitude` | `longitude` |
| `multimedia.images[].url` | `photos` |
| `description` | `description` |
| `agency.name` | `agent_name` |
| `energyCertificate.energyRating` | `energy_cert` |

**Pagination**: Fotocasa search URLs use `?page={n}`. `__NEXT_DATA__` contains `totalPages`.

---

### 7. New Listing Detection Loop

The `detect_new` mode is triggered by the scrape orchestrator on a 15-minute schedule. The spider:

1. Fetches the first 1–3 search result pages sorted by newest
2. Collects listing IDs from the page
3. Calls `redis.smismember("seen:{portal}:{country}:{zone}", ids)` — O(N) single round-trip
4. For each unseen ID: enqueue `scrape_listing_detail(url)` 
5. After scraping, `redis.sadd("seen:{portal}:{country}:{zone}", *new_ids)` 
6. Publish new `RawListing` messages

---

### 8. Metrics (`metrics.py`)

```python
from prometheus_client import Counter, Histogram, start_http_server

LISTINGS_SCRAPED = Counter(
    "listings_scraped_total",
    "Total listings successfully scraped and published",
    ["portal", "country"],
)
SCRAPE_ERRORS = Counter(
    "scrape_errors_total",
    "Total scrape errors",
    ["portal", "country", "error_type"],
)
SCRAPE_DURATION = Histogram(
    "scrape_duration_seconds",
    "Scrape job duration in seconds",
    ["portal", "country"],
    buckets=[10, 30, 60, 120, 300, 600, 1800],
)
```

`start_http_server(config.metrics_port)` called once in `main.py`.

---

### 9. Dependency Additions

New dependencies added to `services/spider-workers/pyproject.toml`:

```toml
dependencies = [
    "nats-py>=2.7",
    "httpx>=0.27",
    "parsel>=1.9",
    "playwright>=1.44",
    "playwright-stealth>=1.0",
    "grpcio>=1.62",
    "redis>=5.0",
    "prometheus-client>=0.20",
    "pydantic-settings>=2.2",
    "structlog>=24.1",
    "estategap-common",
]
```

---

### 10. Dockerfile

Follows the same pattern as `services/pipeline/Dockerfile`. Adds a `RUN playwright install chromium --with-deps` layer after pip install.

---

### 11. Helm Chart Update

Add `spider-workers` Deployment to `helm/estategap/templates/`. Key settings:
- `resources.requests.cpu: 500m`, `memory: 512Mi`
- `resources.limits.cpu: 2`, `memory: 2Gi` (Playwright headless is memory-intensive)
- `METRICS_PORT: 9102` annotated for Prometheus scraping (`prometheus.io/scrape: "true"`)
- Env vars from existing `estategap-secrets` Kubernetes Secret

---

## Complexity Tracking

No constitution violations. All design choices are within the established Python service pattern.

---

## Risks and Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Idealista API token rotation | Medium | Token injected via config/secret; rotation is operational, not code |
| `__NEXT_DATA__` schema change in Fotocasa | Medium | Field mapping is isolated in `es_fotocasa.py`; unit tests with fixture HTML catch regressions |
| Playwright memory leak in long-running process | Low-Medium | Browser launched and closed per blocked request (not persistent); Kubernetes memory limits + liveness probe |
| Redis key growth for seen-IDs | Low | ~50 bytes/ID; 50k IDs/zone = 2.5 MB — negligible at current scale |
| NATS `SCRAPER_COMMANDS` stream not provisioned | Medium | Worker startup checks stream existence; fails fast with clear error log |
