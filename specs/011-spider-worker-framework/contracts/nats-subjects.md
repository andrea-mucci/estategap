# NATS Contract: Spider Worker

**Feature**: 011-spider-worker-framework  
**Date**: 2026-04-17

---

## Inbound: `scraper.commands.{country}.{portal}`

**Producer**: `services/scrape-orchestrator` (Go)  
**Consumer**: `services/spider-workers` (this feature)  
**Stream**: `SCRAPER_COMMANDS` (JetStream, must exist before workers start)  
**Delivery**: At-least-once, durable consumer `spider-worker`

### Message Schema

JSON object matching the Go `ScrapeJob` struct:

```json
{
  "job_id": "string (UUID)",
  "portal": "string (e.g. 'idealista')",
  "country": "string (ISO 3166-1 alpha-2, e.g. 'ES')",
  "mode": "string ('full' | 'detect_new')",
  "zone_filter": ["string", "..."],
  "search_url": "string (base URL for zone search)",
  "created_at": "string (RFC3339)"
}
```

### Routing

Subject tokens after `scraper.commands.` are `{country}.{portal}` in **lowercase**. Examples:
- `scraper.commands.es.idealista`
- `scraper.commands.es.fotocasa`

The spider worker subscribes to `scraper.commands.>` and routes by parsing the subject tokens.

---

## Outbound: `raw.listings.{country}`

**Producer**: `services/spider-workers` (this feature)  
**Consumer**: `services/pipeline`  
**Stream**: `RAW_LISTINGS` (JetStream)  
**Delivery**: At-least-once

### Message Schema

JSON-serialised `RawListing` (from `libs/common/estategap_common/models/listing.py`):

```json
{
  "external_id": "string (portal-assigned listing ID)",
  "portal": "string",
  "country_code": "string (ISO 3166-1 alpha-2)",
  "raw_json": {
    "price": "integer (cents)",
    "currency": "string",
    "area_m2": "float",
    "usable_area_m2": "float | null",
    "rooms": "integer | null",
    "bathrooms": "integer | null",
    "floor": "integer | null",
    "total_floors": "integer | null",
    "has_elevator": "boolean | null",
    "has_parking": "boolean | null",
    "parking_spaces": "integer | null",
    "has_terrace": "boolean | null",
    "terrace_area_m2": "float | null",
    "orientation": "string | null",
    "condition": "string | null",
    "year_built": "integer | null",
    "energy_cert": "string | null",
    "energy_kwh": "float | null",
    "latitude": "float | null",
    "longitude": "float | null",
    "photos": ["string (URL)", "..."],
    "description": "string | null",
    "agent_name": "string | null",
    "agent_id": "string | null",
    "listing_url": "string",
    "zone_id": "string",
    "listing_type": "string ('sale' | 'rent')",
    "property_type": "string"
  },
  "scraped_at": "string (ISO 8601 UTC)"
}
```

### Subject Pattern

`raw.listings.{country}` where `{country}` is the lowercase ISO country code. Example: `raw.listings.es`.

---

## JetStream Stream Definitions

These streams must be provisioned (by the infrastructure/orchestrator setup) before the spider workers start:

| Stream | Subjects | Retention | Max Age |
|--------|----------|-----------|---------|
| `SCRAPER_COMMANDS` | `scraper.commands.>` | WorkQueue | 24h |
| `RAW_LISTINGS` | `raw.listings.>` | Limits | 7d |
