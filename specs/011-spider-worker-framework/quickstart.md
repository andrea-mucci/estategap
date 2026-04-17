# Quickstart: Spider Worker Framework

**Feature**: 011-spider-worker-framework  
**Date**: 2026-04-17

---

## Prerequisites

- Python 3.12+
- `uv` package manager
- Redis 7 running (default: `localhost:6379`)
- NATS with JetStream (default: `nats://localhost:4222`)
- `services/proxy-manager` running and reachable (gRPC, default: `localhost:50051`)
- Playwright browsers installed (see below)

---

## Setup

```bash
cd services/spider-workers

# Install dependencies
uv sync

# Install Playwright browser
uv run playwright install chromium

# Copy env template
cp .env.example .env
# Edit .env — set NATS_URL, REDIS_URL, PROXY_MANAGER_ADDR, IDEALISTA_API_TOKEN
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `NATS_URL` | `nats://localhost:4222` | NATS server URL |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis connection URL |
| `PROXY_MANAGER_ADDR` | `localhost:50051` | Proxy manager gRPC address |
| `METRICS_PORT` | `9102` | Prometheus metrics HTTP port |
| `LOG_LEVEL` | `info` | Logging level |
| `IDEALISTA_API_TOKEN` | _(required)_ | Idealista mobile API Bearer token |
| `REQUEST_MIN_DELAY` | `2.0` | Minimum delay between requests (seconds) |
| `REQUEST_MAX_DELAY` | `5.0` | Maximum delay between requests (seconds) |
| `MAX_CONCURRENT_PER_PORTAL` | `3` | Max concurrent requests per portal |
| `SESSION_ROTATION_EVERY` | `10` | Rotate proxy session every N requests |
| `QUARANTINE_TTL_DAYS` | `30` | Days before quarantine entries expire |

---

## Running

```bash
# Development
uv run python main.py

# With Docker
docker build -t estategap/spider-workers .
docker run --env-file .env estategap/spider-workers
```

---

## Running Tests

```bash
# All tests
uv run pytest

# Unit only (no external services)
uv run pytest tests/unit/

# With coverage
uv run pytest --cov=estategap_spiders tests/unit/
```

---

## Adding a New Spider

1. Create `estategap_spiders/spiders/{country}_{portal}.py`
2. Define a class that extends `BaseSpider` and sets `COUNTRY = "xx"` and `PORTAL = "myportal"`
3. Implement the three abstract methods: `scrape_search_page`, `scrape_listing_detail`, `detect_new_listings`
4. Import the module in `estategap_spiders/spiders/__init__.py`

No other changes required. The spider auto-registers on import.

---

## Verifying Metrics

After starting the service, metrics are available at:

```bash
curl http://localhost:9102/metrics | grep listings_scraped
```

Expected output (after a scrape run):

```
listings_scraped_total{country="es",portal="idealista"} 142.0
scrape_errors_total{country="es",error_type="http_blocked",portal="idealista"} 3.0
scrape_duration_seconds_count{country="es",portal="idealista"} 1.0
```

---

## Manual Test Scrape

Publish a test command to NATS (requires `nats` CLI):

```bash
nats pub scraper.commands.es.idealista '{
  "job_id": "test-001",
  "portal": "idealista",
  "country": "ES",
  "mode": "full",
  "zone_filter": ["madrid-centro"],
  "search_url": "https://www.idealista.com/venta-viviendas/madrid/",
  "created_at": "2026-04-17T10:00:00Z"
}'
```

Monitor the `raw.listings.es` subject for output:

```bash
nats sub raw.listings.es
```
