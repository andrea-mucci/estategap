# Feature: Performance, Security & Launch Readiness

## /specify prompt

```
Harden the platform for production: performance optimization, security audit, GDPR compliance, load testing, and operational documentation.

## What
1. Performance: Redis caching for zone stats (TTL 5min), top deals (TTL 1min), alert rules (TTL 60s). DB query optimization (EXPLAIN ANALYZE all slow queries, ensure index usage). Frontend: Next.js ISR for zone pages, image lazy loading, bundle size < 200KB gzipped.

2. Security: CORS whitelist. CSP headers. SQL injection review (all parameterized). XSS prevention (CSP + React defaults). K8s Sealed Secrets for all sensitive config. Dependency scanning in CI (pip-audit, govulncheck, npm audit). Rate limiting on auth endpoints (5 attempts/min). OWASP ZAP scan.

3. GDPR: cookie consent banner, privacy policy (all supported languages), data export endpoint (GET /api/v1/me/export), account deletion (DELETE /api/v1/me with cascade), agent data removal request form.

4. Load testing: K6 scripts for listing search (1000 concurrent), AI chat (100 concurrent), alert dispatch (10k in 5min), scraping throughput (50k listings). Identify bottlenecks. Tune HPA.

5. Documentation: runbook with incident response, common failures and fixes, scaling procedures, backup/restore, disaster recovery.

## Acceptance Criteria
- API p95 < 300ms for listing search
- Dashboard loads < 2s
- OWASP ZAP: no high/critical findings
- Dependency scans clean in CI
- Data export returns complete user data as JSON
- Account deletion removes all data within 24h
- Load test: system handles target load without errors, HPA scales correctly
- Runbook covers all operational scenarios
- Backup restore tested successfully
```
