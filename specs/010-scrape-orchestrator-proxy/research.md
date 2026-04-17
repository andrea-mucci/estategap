# Research: Scrape Orchestrator & Proxy Manager

**Branch**: `010-scrape-orchestrator-proxy` | **Phase**: 0 | **Date**: 2026-04-17

## Summary

All technical decisions were explicitly provided in the user input. This research document records
each decision, its rationale, and alternatives considered.

---

## Decision 1: Scheduler Design — Per-Portal time.Ticker

**Decision**: Use one `time.Ticker` per portal, created on startup and stored in a map keyed by
portal name. Tickers are stopped and recreated on config reload.

**Rationale**: Simpler than a cron library for this use case. Each portal has an independent
schedule; a shared cron dispatcher would add unnecessary coupling. `time.Ticker` is stdlib,
reliable, and goroutine-safe when wrapped with a cancel context.

**Alternatives considered**:
- `robfig/cron` — adds external dependency; overkill for fixed-interval ticking.
- Single goroutine with `time.Sleep` — not suitable for dynamic intervals or multiple portals.
- NATS-based delayed publishing — adds broker dependency to scheduling; couples concerns.

---

## Decision 2: NATS Subject Pattern — `scraper.commands.{country}.{portal}`

**Decision**: Publish job messages as JSON to `scraper.commands.{country}.{portal}`.

**Rationale**: Subject hierarchy enables consumers to subscribe to all jobs for a country
(`scraper.commands.IT.>`) or a specific portal (`scraper.commands.IT.immobiliare`). Matches
NATS JetStream wildcard conventions. Country-first aligns with Constitution Principle III.

**Alternatives considered**:
- `scraper.commands.{portal}` — loses country granularity in routing.
- `scraper.jobs` (single subject) — no routing flexibility; all consumers see all jobs.
- Kafka topics — not in the technology stack.

---

## Decision 3: Job Tracking — Redis Hash with 24h TTL

**Decision**: Store job state as a Redis hash `jobs:{job_id}` with fields: `status`,
`portal`, `country`, `mode`, `created_at`, `started_at`, `completed_at`, `error`. TTL 24h.

**Rationale**: Jobs are transient operational data, not business records. Redis provides
sub-millisecond reads for status polling. 24h TTL is sufficient for operational visibility
without accumulating stale data. No persistence requirement beyond the run window.

**Alternatives considered**:
- PostgreSQL `scrape_jobs` table — durable but requires a DB write on every status transition;
  query overhead for stats; not appropriate for high-frequency transient state.
- NATS KV — viable but Redis is already in the stack for sessions and caching; no need for
  a second KV store.
- In-memory only — lost on restart; unsuitable for observability.

---

## Decision 4: Internal API — chi on Port 8082

**Decision**: HTTP server using chi on port 8082, same pattern as api-gateway (port 8080)
and ws-server (port 8081).

**Rationale**: Port 8082 is the next sequential internal port. chi is already the standard
router in this monorepo. Internal API (no auth required, not externally exposed via ingress).

**Endpoints**:
- `POST /jobs/trigger` — body: `{portal, country, mode, zone_filter, search_url}`
- `GET /jobs/{id}/status` — returns job hash fields
- `GET /jobs/stats` — aggregates counts by status (scans `jobs:*` keys with SCAN)
- `GET /health` — liveness probe

**Alternatives considered**:
- gRPC for internal API — heavier; no real benefit over HTTP for manual trigger use case.
- Pure NATS request/reply — harder to expose for manual curl/ops tooling.

---

## Decision 5: Config Reload — SIGHUP + 5-Minute Ticker

**Decision**: A background goroutine listens for `syscall.SIGHUP` via `signal.Notify` and
also fires a `time.Ticker` every 5 minutes. On either trigger, reload portals from DB and
reconcile the ticker map (add new, stop removed, keep unchanged).

**Rationale**: SIGHUP is the UNIX standard for config reload; zero downtime, no restart.
5-minute fallback ensures consistency even if signal is missed in Kubernetes environments.

**Alternatives considered**:
- Restart-only reload — requires pod restart; causes missed ticks during rollout.
- inotify on config file — DB-driven config doesn't map to file changes.
- Kubernetes ConfigMap watch — adds K8s API dependency to the service; excessive coupling.

---

## Decision 6: Proxy Pool — In-Memory map[country][]Proxy with sync.RWMutex

**Decision**: Load proxies from environment variables at startup. Maintain `map[string][]*Proxy`
in memory, protected by `sync.RWMutex`. No dynamic reloading required (providers are stable).

**Environment variable format**:
```
PROXY_COUNTRIES=IT,ES,FR
PROXY_IT_PROVIDER=brightdata
PROXY_IT_ENDPOINT=zproxy.lum-superproxy.io:22225
PROXY_IT_USERNAME=user123
PROXY_IT_PASSWORD=secret
```

**Rationale**: Proxy credentials change infrequently (provider contract changes). In-memory
pool gives sub-millisecond access. Environment variables follow K8s Sealed Secrets pattern
(Constitution VI). No DB round-trip in the hot path.

**Alternatives considered**:
- PostgreSQL-backed pool — adds DB latency to every GetProxy call; breaks <10ms SLA.
- Redis-backed pool — adds network hop; still sub-10ms but unnecessary for mostly-static data.
- Config file — harder to manage per-environment with Sealed Secrets.

---

## Decision 7: Health Scoring — Sliding Window of 100 Results

**Decision**: Per-proxy circular buffer of last 100 `bool` results. Health score =
`success_count / 100`. Score < 0.5 = unhealthy (not returned by GetProxy).

**Implementation**: `[100]bool` array with a head pointer (mod 100). Thread-safe via the
proxy-level mutex. Initialized with all `true` (assume healthy until proven otherwise).

**Rationale**: Sliding window is responsive to recent failures without being too sensitive
to isolated errors. 100 samples is enough to smooth noise. 50% threshold is a conservative
midpoint; can be tuned via config if needed.

**Alternatives considered**:
- EWMA (exponential weighted moving average) — more accurate but harder to reason about
  and test; overkill for this use case.
- Fixed time window (last 5 minutes) — requires timestamps per result; more memory.
- Simple consecutive failure count — doesn't recover gracefully from isolated errors.

---

## Decision 8: Blacklist — Redis SET Key with 30min TTL

**Decision**: On 403/429, set `proxy:blacklist:{ip}` in Redis with `EX 1800` (30 min TTL).
`GetProxy` checks Redis before returning any proxy.

**Rationale**: Redis TTL handles automatic expiry with no cleanup goroutine needed.
Blacklist is cross-instance — if the proxy manager is scaled to multiple replicas,
all instances share the blacklist. Consistent with existing Redis usage patterns.

**Alternatives considered**:
- In-memory blacklist with time.AfterFunc cleanup — doesn't work across replicas; memory leak
  risk if cleanup fires fail.
- Health score decay — too slow; a proxy causing 429s should be removed immediately.

---

## Decision 9: Sticky Sessions — Redis Hash with 10min TTL

**Decision**: `proxy:sticky:{session_id}` → `proxy_id` string in Redis. TTL 10 min.
On `GetProxy` with non-empty `session_id`: GETEX to retrieve and renew TTL.

**Rationale**: Redis hash (actually a simple string key → proxy_id string) is sufficient.
10-minute TTL aligns with typical paginated crawl session duration. GETEX atomically gets
and extends TTL, preventing mid-session expiry.

**Alternatives considered**:
- In-memory session map — doesn't survive restarts; not shared across replicas.
- Cookie-based routing — proxies don't have session state; client-side approach wrong layer.

---

## Decision 10: Provider Adapter Pattern

**Decision**: Define a `ProxyProvider` interface:
```go
type ProxyProvider interface {
    BuildProxyURL(username, password, endpoint, sessionID string) string
    Name() string
}
```
Three concrete adapters: `BrightDataAdapter`, `SmartProxyAdapter`, `OxylabsAdapter`.
Each implements `BuildProxyURL` with its specific URL format.

**Provider URL formats**:
- **Bright Data**: `http://{username}-session-{sessionID}:{password}@{endpoint}`
- **SmartProxy**: `http://{username}:{password}@{endpoint}` (no session in URL; session via X-Smartproxy-Session header)
- **Oxylabs**: `http://{username}:{password}@{endpoint}` (sticky via username suffix `-sessid-{sessionID}`)

**Rationale**: Adapter pattern isolates provider-specific auth logic. Adding a new provider
requires only a new adapter struct. No switch statements scattered across the codebase.

**Alternatives considered**:
- Single config template string — brittle, no type safety, hard to test.
- Strategy pattern via function pointers — less readable than named types.

---

## Decision 11: Proto Update — Add session_id to GetProxyRequest

**Decision**: Update `proto/estategap/v1/proxy.proto` to add `string session_id = 3` to
`GetProxyRequest`. Empty string means no sticky session.

**Rationale**: The existing proto is missing the sticky session field. Must be added before
implementing the service. Backward compatible (proto3 optional fields).

---

## Decision 12: Prometheus Metrics Labels

**Decision**: Three metric families:
```
proxy_pool_size{country="IT", provider="brightdata"} 50
proxy_healthy_count{country="IT", provider="brightdata"} 47
proxy_block_rate{country="IT", provider="brightdata"} 0.06
```
`proxy_block_rate` = blacklisted count / pool size, updated on every ReportResult call.

**Rationale**: Country + provider labels enable per-provider health comparison. Block rate
as a ratio (not absolute count) is more useful for alerting thresholds.
