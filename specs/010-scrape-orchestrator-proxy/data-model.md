# Data Model: Scrape Orchestrator & Proxy Manager

**Branch**: `010-scrape-orchestrator-proxy` | **Phase**: 1 | **Date**: 2026-04-17

---

## Scrape Orchestrator

### Entity: Portal (read from PostgreSQL)

Read-only from the `portals` table. No writes by this service.

| Field             | Type             | Notes                                      |
|-------------------|------------------|--------------------------------------------|
| `name`            | `string`         | Portal identifier, e.g., `immobiliare`     |
| `country`         | `string`         | ISO 3166-1 alpha-2, e.g., `IT`             |
| `enabled`         | `bool`           | Only enabled portals are scheduled         |
| `scrape_frequency`| `time.Duration`  | Parsed from PostgreSQL `interval` type      |
| `search_urls`     | `[]string`       | List of search URLs to scrape              |

### Entity: ScrapeJob (NATS message + Redis state)

**NATS message** (JSON, published to `scraper.commands.{country}.{portal}`):

```json
{
  "job_id":    "uuid-v4",
  "portal":    "immobiliare",
  "country":   "IT",
  "mode":      "full | incremental",
  "zone_filter": ["zone-id-1", "zone-id-2"],
  "search_url": "https://www.immobiliare.it/vendita-case/...",
  "created_at": "2026-04-17T10:30:00Z"
}
```

**Redis hash** (`jobs:{job_id}` — TTL 24h):

| Field          | Type     | Values                                    |
|----------------|----------|-------------------------------------------|
| `status`       | string   | `pending`, `running`, `completed`, `failed` |
| `portal`       | string   | Portal name                               |
| `country`      | string   | ISO country code                          |
| `mode`         | string   | `full` or `incremental`                   |
| `created_at`   | string   | RFC3339 timestamp                         |
| `started_at`   | string   | RFC3339, empty until worker picks up      |
| `completed_at` | string   | RFC3339, empty until terminal state       |
| `error`        | string   | Error message if failed, else empty       |

**State transitions**:
```
pending → running → completed
                 ↘ failed
```
Note: `pending → running` is set by the spider worker (via a separate status update mechanism
or a dedicated NATS reply subject). The orchestrator sets `pending` on publish.

### Entity: PortalTicker (in-memory, not persisted)

```go
type PortalTicker struct {
    Portal  Portal
    Ticker  *time.Ticker
    Cancel  context.CancelFunc
}
```

Stored in `map[string]*PortalTicker` keyed by `portal.name`.

---

## Proxy Manager

### Entity: Proxy (in-memory)

```go
type Proxy struct {
    ID          string       // uuid-v4, generated at startup
    Country     string       // ISO alpha-2
    Provider    string       // "brightdata", "smartproxy", "oxylabs"
    Endpoint    string       // host:port
    Username    string
    Password    string
    Health      *HealthWindow
    mu          sync.Mutex
}
```

### Entity: HealthWindow (in-memory, per proxy)

```go
type HealthWindow struct {
    results  [100]bool  // circular buffer: true=success, false=failure
    head     int        // next write index (mod 100)
    count    int        // total samples recorded (capped at 100)
    successes int       // running success count in current window
}
```

- Score = `successes / min(count, 100)`
- New proxy: `count=0`, score treated as 1.0 (optimistic start)
- Unhealthy threshold: score < 0.5

### Entity: ProxyPool (in-memory)

```go
type ProxyPool struct {
    mu      sync.RWMutex
    proxies map[string][]*Proxy  // keyed by country code
    roundRobin map[string]int    // current RR index per country
}
```

### Redis Keys (Proxy Manager)

| Key pattern                     | Type   | TTL    | Contents                          |
|----------------------------------|--------|--------|-----------------------------------|
| `proxy:blacklist:{ip}`          | String | 30 min | Value: `"1"` (presence = blocked) |
| `proxy:sticky:{session_id}`     | String | 10 min | Value: `proxy_id` (UUID)          |

### Proxy URL Formats by Provider

| Provider    | URL Format                                                        |
|-------------|-------------------------------------------------------------------|
| Bright Data | `http://{user}-session-{sid}:{pass}@{endpoint}`                  |
| SmartProxy  | `http://{user}:{pass}@{endpoint}` (session via username suffix)  |
| Oxylabs     | `http://{user}-sessid-{sid}:{pass}@{endpoint}`                   |

When `session_id` is empty, omit the session suffix (random rotation).

### Prometheus Metric Definitions

| Metric Name            | Type  | Labels                   | Description                              |
|------------------------|-------|--------------------------|------------------------------------------|
| `proxy_pool_size`      | Gauge | `country`, `provider`    | Total proxies configured per country     |
| `proxy_healthy_count`  | Gauge | `country`, `provider`    | Proxies with health score ≥ 0.5          |
| `proxy_block_rate`     | Gauge | `country`, `provider`    | Blacklisted / pool size ratio            |

Metrics are updated:
- `proxy_pool_size` — at startup and config reload
- `proxy_healthy_count` + `proxy_block_rate` — after every `ReportResult` call

---

## Protobuf Contract Update

`proxy.proto` requires one addition: `session_id` in `GetProxyRequest`.

See `contracts/proxy.proto.diff` for the change.
