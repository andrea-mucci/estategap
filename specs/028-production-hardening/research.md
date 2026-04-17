# Research: Production Hardening (028)

**Branch**: `028-production-hardening` | **Date**: 2026-04-17

All decisions resolved — no NEEDS CLARIFICATION markers remain.

## Performance Caching

**Decision**: Extend the existing `services/api-gateway/internal/cache/cache.go` GetOrSet pattern with three typed helpers — `ZoneStatsCache` (TTL 300s), `TopDealsCache` (TTL 60s), `AlertRulesCache` (TTL 60s). Cache key = `"cache:{scope}:" + hex(SHA-256(sorted-query-params))`.

**Rationale**: The generic Redis cache helper is already production-tested. Typed wrappers enforce TTL contracts and prevent key collisions. SHA-256 of sorted params is deterministic regardless of param order in the HTTP request.

**Alternatives considered**: Per-field composite keys (more code, equivalent collision resistance); full query string (encoding variance causes key misses).

## Database Query Optimisation

**Decision**: Use `pg_stat_statements` (already enabled per spec assumptions) to identify the 10 slowest queries. Run `EXPLAIN (ANALYZE, BUFFERS)` on each. Deliver missing indexes as a new Alembic migration (`028_add_performance_indexes.py`). Candidate indexes based on common query patterns:
- `listings(country_code, status, created_at DESC)` — search + pagination
- `listings(zone_id, score_value DESC) WHERE status = 'active'` — top deals (partial index)
- `alert_rules(user_id, is_active) WHERE is_active = true` — alert engine hot path (partial index)
- `alert_history(user_id, created_at DESC)` — dashboard history queries

**Rationale**: Partial indexes on boolean/status columns give 3–10× speedup on selective queries. The Alembic migration keeps index changes version-controlled and reviewable.

**Alternatives considered**: Manual `CREATE INDEX CONCURRENTLY` (not reproducible); ORM-level annotations (not used — pgx/raw SQL).

## Frontend Bundle Optimisation

**Decision**: `next/dynamic(() => import(...), { ssr: false })` for `MapLibreMap` and `RechartsWrapper` components. `next/image` for all listing photos. `<link rel="preconnect">` for API domain and MapLibre tile server in root layout.

**Rationale**: MapLibre GL JS (~600 KB unminified) and Recharts (~300 KB) are the only components exceeding 50 KB individually. Dynamic import splits them to separate lazy chunks that download only when the component mounts. `next/image` handles WebP conversion and lazy loading automatically.

**Alternatives considered**: Route-level code splitting (already done by App Router, not sufficient for heavy within-route components); manual webpack chunk hints (fragile, breaks on Next.js upgrades).

## CORS Allowlist

**Decision**: Read `ALLOWED_ORIGINS` env var at startup (comma-separated). Update `internal/middleware/cors.go` to replace any hardcoded origins with the parsed list. The middleware already exists and sets correct CORS headers.

**Rationale**: The existing cors.go has the middleware wiring. The only change is replacing any hardcoded or wildcard origin with the env-var-driven allowlist.

**Alternatives considered**: Dynamic DB-stored allowlist (over-engineered for a list that changes with deployments, not at runtime).

## Content Security Policy

**Decision**: New `internal/middleware/csp.go` generates a crypto-random 128-bit nonce per request. CSP header value:
```
default-src 'self';
script-src 'self' 'nonce-{nonce}';
style-src 'self' 'nonce-{nonce}' https://fonts.googleapis.com;
font-src 'self' https://fonts.gstatic.com;
img-src 'self' data: https://*.tile.openstreetmap.org https://*.maptiler.com blob:;
connect-src 'self' {API_DOMAIN} wss://{WS_DOMAIN};
frame-ancestors 'none';
```
Initially delivered as `Content-Security-Policy-Report-Only` (with `CSP_REPORT_URI` env var). Set `CSP_REPORT_ONLY=false` to enforce.

**Rationale**: Nonce-based CSP is the only approach compatible with Next.js server-rendered inline scripts. Report-only mode first allows violation capture before enforcement breaks the app.

**Alternatives considered**: Hash-based CSP (Next.js RSC generates dynamic script content, hashes can't be precomputed at build time); `unsafe-inline` (defeats XSS protection entirely).

## Auth Rate Limiting

**Decision**: New `internal/middleware/auth_ratelimit.go` uses `INCR` + `EXPIRE` (only if key didn't exist) pattern in Redis. Key: `auth:attempts:{client_ip}`, TTL: 60s, threshold: 5. Returns `429 Too Many Requests` with `Retry-After: 60` header.

**Rationale**: The existing ratelimit.go middleware is subscription-tier-based (different semantics). A separate middleware avoids coupling brute-force protection to subscription logic. Redis INCR is atomic and handles concurrent requests correctly.

**Alternatives considered**: In-memory counter (doesn't survive pod restarts, fails under multi-replica deployment); extending existing ratelimit.go (coupling risk).

## Sealed Secrets

**Decision**: Extend the existing `helm/estategap/templates/sealed-secrets.yaml` to ensure all 8 secrets are covered: `DB_PASSWORD`, `REDIS_PASSWORD`, `JWT_SECRET`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `LLM_API_KEY`, `PROXY_CREDENTIALS`, `SES_CREDENTIALS`. The `bitnami/sealed-secrets` Helm dependency is added to `Chart.yaml` if not already present. Encrypted values are populated per-environment by the operator (outside this feature's scope).

**Rationale**: The sealed-secrets.yaml already exists in the Helm chart. The Bitnami Sealed Secrets controller encrypts secrets with the cluster's public key; only the controller can decrypt them. Secrets never appear plaintext in Git.

**Alternatives considered**: HashiCorp Vault (larger operational surface, requires separate infra); ExternalSecrets Operator (adds another CRD dependency without meaningful advantage here).

## CI Dependency Scanning

**Decision**:
- `ci-go.yml`: add `go install golang.org/x/vuln/cmd/govulncheck@latest && govulncheck ./...` step; fail on any finding
- `ci-python.yml`: add `uv run pip-audit` step; fail on HIGH or CRITICAL
- `ci-frontend.yml`: add `npm audit --audit-level=high` step; fail on high severity

**Rationale**: Each scanner is the canonical tool for its ecosystem. `pip-audit` checks against OSV database. `govulncheck` checks against Go vulnerability database. `npm audit` checks against npm advisory database. All three can emit non-zero exit codes that fail the pipeline.

**Alternatives considered**: Snyk (requires external SaaS account, licensing cost); Dependabot (PRs only, not blocking CI gates).

## Cookie Consent

**Decision**: shadcn `Dialog` component rendered in root layout (`app/[locale]/layout.tsx`). On mount, reads `eg_consent` cookie. If absent, shows modal. On accept/deny, writes `eg_consent=granted|denied` (max-age 31536000, SameSite=Lax). Analytics scripts wrapped in a `ConsentGate` component that renders children only when `eg_consent === 'granted'`.

**Rationale**: Cookie is readable in SSR (Next.js `cookies()` API) and client-side. `ConsentGate` can conditionally render both RSC and client components. shadcn Dialog is already available in the component library.

**Alternatives considered**: Third-party consent SDK (cookie overhead, external dependency); localStorage (not accessible in SSR, lost on private browsing).

## GDPR Data Export

**Decision**: `GET /api/v1/me/export` handler aggregates:
1. User profile from PostgreSQL `users` table
2. Alert rules from `alert_rules` WHERE `user_id = $1`
3. Portfolio properties from `portfolio_properties` WHERE `user_id = $1`
4. Alert history from `alert_history` WHERE `user_id = $1` (last 1000 entries)
5. Conversation history from Redis SCAN with pattern `chat:session:{user_id}:*`, reading each key

All results marshalled to JSON. Response header `Content-Disposition: attachment; filename="estategap-export-{date}.json"`.

**Rationale**: Conversations live exclusively in Redis (per architecture of service 018). A complete GDPR export must include them. SCAN is used to avoid blocking the Redis server with KEYS.

**Alternatives considered**: Background job + download link (adds complexity; data must be available immediately for GDPR compliance); skipping Redis conversations (incomplete export, GDPR risk).

## Account Deletion

**Decision**: `DELETE /api/v1/me` with body `{"confirm": "delete my account"}`:
1. Verify user exists and is not already deleted
2. In a single PostgreSQL transaction: set `deleted_at = now()`, `anonymized_at = now()`, overwrite `email = 'deleted-{uuid}@deleted.invalid'`, `name = 'Deleted User'`, `avatar_url = NULL`
3. Invalidate all active sessions: `DEL session:{user_id}:*` pattern in Redis
4. Publish `UserDeleted` event to NATS (optional — for downstream cleanup)
5. Send confirmation email via SES (async, non-blocking)
6. Return `202 Accepted`

**K8s CronJob** (`helm/estategap/templates/gdpr-hard-delete-cronjob.yaml`): runs daily at 02:00 UTC. Executes SQL: `DELETE FROM users WHERE deleted_at < NOW() - INTERVAL '30 days'` plus cascade deletes for `alert_rules`, `portfolio_properties`, `alert_history`.

**Rationale**: Two-phase deletion (immediate anonymisation + deferred hard delete) satisfies GDPR while providing a grace period for accidental deletions. The 30-day window is standard practice in EU-regulated services. Overwriting PII fields (rather than nulling) avoids NOT NULL constraint issues.

**Alternatives considered**: Immediate hard delete (no grace period for accidental deletes); separate deletion-request table with manual processing (slower compliance).

## Load Testing

**Decision**: K6 scripts in `tests/load/` targeting staging cluster endpoints. Executed via a K8s Job (`helm/estategap/templates/load-test-job.yaml`) using `grafana/k6:latest` image. Scripts:
- `search.js`: 1 000 VUs, 5 min duration, ramp-up 30s. Target: `GET /api/v1/listings?...`
- `chat.js`: 100 VUs, 10 min, WebSocket connections to `ws://websocket-server/chat`
- `alerts.js`: burst scenario — 100 VUs × 100 iterations, POST to alert trigger endpoint
- `pipeline.js`: 50 000 NATS messages to `listings.ingested` subject using k6 NATS extension

Thresholds defined in each script: `http_req_duration{p(95)} < 300`, `http_req_failed < 0.01`.

**Rationale**: In-cluster execution eliminates external network latency from measurements, giving accurate service-to-service numbers. Grafana dashboards (already deployed) capture HPA events during the run.

**Alternatives considered**: Artillery (less Kubernetes-native, fewer extensions); Locust (Python, adds Python dep to a Go-test context); external cloud load testing (egress cost, inaccurate internal latency).

## Runbook

**Decision**: Single Markdown file at `docs/runbook.md`. Sections:
1. Architecture overview (service graph, data flow diagram in Mermaid)
2. Service dependency map (what depends on what, startup order)
3. Incident playbooks: Scraper blocked / Model degraded / DB full / NATS lag / High error rate / HPA not scaling
4. Scaling procedures: manual HPA override (`kubectl patch hpa`), adding nodes, resizing PVCs
5. Backup/restore: PostgreSQL `pg_dump` + `pg_restore` commands, MinIO backup, NATS stream backup
6. Disaster recovery: full cluster rebuild from Helm + latest backup, step-by-step
7. Escalation contacts: roles and contact methods (placeholder — filled by operator)

**Rationale**: A single file is easier to maintain and version-control than a wiki. Mermaid diagrams render in GitHub and most doc tools. All commands are copy-pasteable.

**Alternatives considered**: Confluence wiki (external dependency, version control harder); GitBook (setup overhead); per-service runbooks (fragmented, harder to cross-reference during incidents).
