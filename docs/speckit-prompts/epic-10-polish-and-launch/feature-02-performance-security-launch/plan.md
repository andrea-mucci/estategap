# Feature: Performance, Security & Launch Readiness

## /plan prompt

```
Implement with these technical decisions:

## Performance
- Redis caching layer: api-gateway checks Redis before DB query. Cache key = hash of query params. SET with TTL.
- DB: run EXPLAIN ANALYZE on top 10 slowest queries (identified via pg_stat_statements). Add missing indexes. Consider partial indexes for hot queries.
- Frontend: dynamic imports for heavy components (Map, Charts). next/image for automatic optimization. Preconnect hints for API and WS domains.

## Security
- CORS: environment variable ALLOWED_ORIGINS (comma-separated). Applied via chi middleware.
- CSP: report-only first, then enforce. Allow: self, API domain, CDN for fonts/images, MapLibre tiles. No inline scripts (nonce-based).
- Sealed Secrets: bitnami/sealed-secrets controller in cluster. SealedSecret CRs in Helm chart for: DB_PASSWORD, REDIS_PASSWORD, JWT_SECRET, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, LLM_API_KEY, PROXY_CREDENTIALS, SES_CREDENTIALS.
- Auth rate limit: separate Redis counter "auth:attempts:{ip}" with TTL 60s. Threshold: 5 attempts.
- CI scanning: pip-audit in ci-python.yml, govulncheck in ci-go.yml, npm audit in ci-frontend.yml. Fail pipeline on high severity.

## GDPR
- Cookie consent: shadcn Dialog on first visit. Stores preference in cookie. Blocks analytics until consent.
- Privacy policy: markdown file per locale, rendered as static page.
- Data export: API endpoint that queries all user data (profile, conversations, alert rules, portfolio, alert history) → JSON download.
- Account deletion: soft delete (set deleted_at, anonymize PII). Background job (K8s CronJob) hard-deletes after 30 days. Sends confirmation email.

## Load Testing
- K6 scripts in tests/load/: search.js (1000 VUs, 5min), chat.js (100 VUs, 10min), alerts.js (burst 10k), pipeline.js (50k messages to NATS).
- Run from K8s Job (in-cluster for accurate latency measurement)
- Monitor: Grafana dashboards during test. Capture: p50/p95/p99, error rate, HPA scaling events.

## Runbook (docs/runbook.md)
- Sections: architecture overview, service dependency map, common incidents (scraper blocked, model degraded, DB full, NATS lag), resolution playbooks, scaling procedures (manual HPA override, adding nodes), backup/restore (PostgreSQL pg_dump + restore), disaster recovery (full cluster rebuild from Helm + latest backup), contact escalation.
```
