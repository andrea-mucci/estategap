# Feature: Scraping Orchestrator & Proxy Manager

## /plan prompt

```
Implement with these technical decisions:

## Scrape Orchestrator
- services/scrape-orchestrator/
- Scheduler: use Go time.Ticker per portal with configurable interval from DB
- Job message format (NATS JSON): {job_id, portal, country, mode (full/incremental), zone_filter, search_url, created_at}
- Job tracking: Redis hash "jobs:{job_id}" with status + timestamps. TTL 24h.
- Internal API (chi, port 8082): POST /jobs/trigger, GET /jobs/{id}/status, GET /jobs/stats
- On startup: load all enabled portals from DB, create tickers. Reload on SIGHUP or every 5min.

## Proxy Manager
- services/proxy-manager/
- gRPC server on port 50052
- Proxy pool: in-memory map[country][]Proxy with mutex. Loaded from env vars (PROXY_PROVIDER_URL, PROXY_COUNTRIES).
- Health tracking: per-proxy sliding window of last 100 results. Health score = success_count / total_count. Proxy with score < 0.5 = unhealthy.
- Blacklist: Redis SET "proxy:blacklist:{ip}" with TTL 30min
- Sticky sessions: Redis hash "proxy:sticky:{session_id}" → proxy_id with TTL 10min
- Provider integration: support Bright Data, SmartProxy, Oxylabs via adapter pattern (each has different auth: user:pass@host:port or API)
```
