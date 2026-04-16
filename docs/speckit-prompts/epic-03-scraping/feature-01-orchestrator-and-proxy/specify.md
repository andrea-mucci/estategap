# Feature: Scraping Orchestrator & Proxy Manager

## /specify prompt

```
Build the Go services that coordinate scraping jobs and manage the proxy pool.

## What
1. Scrape Orchestrator (Go): reads portal configurations from PostgreSQL (portal table: name, country, enabled, scrape_frequency, search_urls). Runs a scheduler that publishes scraping jobs to NATS streams (scraper.commands.{country}.{portal}) at configurable intervals per portal. Tracks job status (pending, running, completed, failed). Supports: full sweep mode (every 6h), incremental new-listing mode (every 15min for priority zones), manual trigger via internal API.

2. Proxy Manager (Go): gRPC service implementing ProxyService. Manages pool of residential proxy IPs organized by country. Pool loaded from config (proxy provider credentials + country endpoints). GetProxy(country, portal, sticky_session) returns a healthy proxy. ReportResult(proxy_id, success/failure, status_code) updates proxy health. Rotation: round-robin with health weighting. Blacklist IPs that receive 403/429 for 30 minutes. Sticky sessions: return same proxy for sequential requests (paginated crawls). Prometheus metrics: pool size, healthy count, block rate per country.

## Acceptance Criteria
- Orchestrator publishes jobs to correct NATS subjects on schedule
- Manual trigger publishes immediate job
- Job status tracked and queryable
- Proxy manager returns healthy proxy within 10ms
- Blocked proxy not returned for 30min
- Sticky session returns same IP for same session_id
- Metrics show pool health per country
```
