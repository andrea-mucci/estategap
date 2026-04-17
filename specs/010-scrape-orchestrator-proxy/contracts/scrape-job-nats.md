# NATS Contract: Scrape Job Messages

**Subject pattern**: `scraper.commands.{country}.{portal}`

**Examples**:
- `scraper.commands.IT.immobiliare`
- `scraper.commands.ES.idealista`
- `scraper.commands.FR.seloger`

**Stream**: `SCRAPER_COMMANDS` (pre-created by infrastructure)
- Subjects: `scraper.commands.>`
- Retention: WorkQueuePolicy (each message consumed once)
- MaxAge: 1h (stale jobs are discarded)
- Replicas: 3

---

## Message Schema (JSON)

```json
{
  "job_id":      "550e8400-e29b-41d4-a716-446655440000",
  "portal":      "immobiliare",
  "country":     "IT",
  "mode":        "full",
  "zone_filter": ["zone-abc", "zone-def"],
  "search_url":  "https://www.immobiliare.it/vendita-case/roma/?prezzoMinimo=50000",
  "created_at":  "2026-04-17T10:30:00Z"
}
```

### Field Definitions

| Field         | Type            | Required | Description                                               |
|---------------|-----------------|----------|-----------------------------------------------------------|
| `job_id`      | string (UUID v4)| Yes      | Unique job identifier for tracking                        |
| `portal`      | string          | Yes      | Portal name matching `portals.name` in DB                 |
| `country`     | string          | Yes      | ISO 3166-1 alpha-2 country code                           |
| `mode`        | string enum     | Yes      | `full` = all listings; `incremental` = new listings only  |
| `zone_filter` | []string        | No       | Zone IDs to restrict scraping scope; empty = all zones    |
| `search_url`  | string          | Yes      | The specific search URL to scrape                         |
| `created_at`  | string (RFC3339)| Yes      | Job creation timestamp                                    |

### Mode Semantics

- **`full`**: Scrape all pages of the search URL. Triggered every 6h per portal.
  Used for full inventory sweeps.
- **`incremental`**: Scrape only the first page(s), targeting newly listed items.
  Triggered every 15min for priority zones.

---

## Internal HTTP API (port 8082)

### POST /jobs/trigger

Publish an immediate job outside the regular schedule.

**Request body**:
```json
{
  "portal":      "immobiliare",
  "country":     "IT",
  "mode":        "full",
  "zone_filter": [],
  "search_url":  "https://www.immobiliare.it/vendita-case/milano/"
}
```

**Response 202**:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "pending"
}
```

**Response 400** — missing required fields  
**Response 503** — NATS unavailable

---

### GET /jobs/{id}/status

**Response 200**:
```json
{
  "job_id":       "550e8400-e29b-41d4-a716-446655440000",
  "status":       "completed",
  "portal":       "immobiliare",
  "country":      "IT",
  "mode":         "full",
  "created_at":   "2026-04-17T10:30:00Z",
  "started_at":   "2026-04-17T10:30:01Z",
  "completed_at": "2026-04-17T10:45:22Z",
  "error":        ""
}
```

**Response 404** — job ID not found (expired TTL or never existed)

---

### GET /jobs/stats

**Response 200**:
```json
{
  "pending":   3,
  "running":   12,
  "completed": 847,
  "failed":    5,
  "total":     867
}
```

Stats are computed by scanning `jobs:*` keys in Redis (SCAN with pattern match).

---

### GET /health

**Response 200**:
```json
{
  "status": "ok",
  "db": "ok",
  "nats": "ok",
  "redis": "ok"
}
```
