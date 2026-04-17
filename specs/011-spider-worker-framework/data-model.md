# Data Model: Spider Worker Framework

**Feature**: 011-spider-worker-framework  
**Date**: 2026-04-17

---

## Existing Models (consumed, not redefined)

### `RawListing` — `libs/common/estategap_common/models/listing.py`

The spider's primary output. Already defined:

```python
class RawListing(EstateGapModel):
    external_id: str        # portal-assigned listing ID
    portal: str             # e.g. "idealista", "fotocasa"
    country_code: str       # ISO 3166-1 alpha-2, e.g. "ES"
    raw_json: dict[str, Any]  # all extracted fields (see below)
    scraped_at: AwareDatetime
```

**`raw_json` schema for ES portals** (fields populated by spiders; all optional except `price` and `area`):

| Field key | Type | Description |
|-----------|------|-------------|
| `price` | `int` | Asking price in original currency (cents) |
| `currency` | `str` | ISO 4217, e.g. `"EUR"` |
| `area_m2` | `float` | Built area in m² |
| `usable_area_m2` | `float \| null` | Usable area |
| `rooms` | `int \| null` | Number of bedrooms |
| `bathrooms` | `int \| null` | Number of bathrooms |
| `floor` | `int \| null` | Floor number |
| `total_floors` | `int \| null` | Total floors in building |
| `has_elevator` | `bool \| null` | Elevator present |
| `has_parking` | `bool \| null` | Parking included |
| `parking_spaces` | `int \| null` | Number of parking spaces |
| `has_terrace` | `bool \| null` | Terrace present |
| `terrace_area_m2` | `float \| null` | Terrace size |
| `orientation` | `str \| null` | e.g. `"south"`, `"north-east"` |
| `condition` | `str \| null` | e.g. `"new"`, `"good"`, `"needs_renovation"` |
| `year_built` | `int \| null` | Construction year |
| `energy_cert` | `str \| null` | Rating letter: `"A"`–`"G"` |
| `energy_kwh` | `float \| null` | kWh/m²/year |
| `latitude` | `float \| null` | GPS latitude |
| `longitude` | `float \| null` | GPS longitude |
| `photos` | `list[str]` | Absolute photo URLs |
| `description` | `str \| null` | Original portal description text |
| `agent_name` | `str \| null` | Agency / agent name |
| `agent_id` | `str \| null` | Portal-assigned agent ID |
| `listing_url` | `str` | Canonical listing URL |
| `zone_id` | `str` | Zone identifier from the scrape command |
| `listing_type` | `str` | `"sale"` or `"rent"` |
| `property_type` | `str` | `"residential"`, `"commercial"`, etc. |

---

## New Models (defined in this feature)

### `ScraperCommand` — `estategap_spiders/models.py`

Deserialized from the NATS message payload. Matches the Go `ScrapeJob` struct exactly.

```python
class ScraperCommand(BaseModel):
    job_id: str
    portal: str              # e.g. "idealista"
    country: str             # e.g. "ES"
    mode: str                # "full" | "detect_new"
    zone_filter: list[str]   # zone IDs to scrape; empty = all
    search_url: str          # base search URL for this zone
    created_at: datetime
```

### `ProxyAssignment` — `estategap_spiders/proxy_client.py`

Thin wrapper around the gRPC `GetProxyResponse`.

```python
class ProxyAssignment:
    proxy_url: str    # http://user:pass@host:port
    proxy_id: str     # opaque ID for ReportResult
```

### `QuarantineEntry` — `estategap_spiders/quarantine.py`

Stored as Redis hash field value (JSON-serialised).

```python
class QuarantineEntry(BaseModel):
    url: str
    portal: str
    country: str
    error: str
    attempt_count: int
    quarantined_at: AwareDatetime
```

### `SpiderRegistry` — `estategap_spiders/spiders/__init__.py`

In-process mapping populated via `__init_subclass__`.

```python
REGISTRY: dict[tuple[str, str], type[BaseSpider]] = {}
# key: (country_code.lower(), portal_id.lower())
# e.g. ("es", "idealista") → IdealistaSpider
```

---

## State in Redis

| Key pattern | Type | TTL | Purpose |
|-------------|------|-----|---------|
| `seen:{portal}:{country}:{zone_id}` | Set | none | Seen listing IDs for new-listing detection |
| `quarantine:{portal}:{country}` | Hash | 30d | Permanently failed URLs |

---

## NATS Subjects

| Subject | Direction | Producer | Consumer |
|---------|-----------|----------|----------|
| `scraper.commands.{country}.{portal}` | in | scrape-orchestrator (Go) | spider-worker (this service) |
| `raw.listings.{country}` | out | spider-worker | pipeline service |

**Message format** (both subjects): JSON-encoded Pydantic model, UTF-8.

---

## Metrics Labels

All three Prometheus metrics carry the following label set:

| Label | Example values |
|-------|---------------|
| `portal` | `idealista`, `fotocasa` |
| `country` | `es` |
| `error_type` (scrape_errors_total only) | `http_blocked`, `captcha`, `parse_error`, `timeout`, `quarantined` |
