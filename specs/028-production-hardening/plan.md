# Implementation Plan: Production Hardening

**Branch**: `028-production-hardening` | **Date**: 2026-04-17 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/028-production-hardening/spec.md`

## Summary

Cross-cutting hardening epic that wires Redis caching at the API Gateway handler layer, hardens security controls (CORS allowlist, CSP headers, auth-specific rate limiting, Sealed Secrets), implements GDPR endpoints (data export, account deletion, cookie consent), adds K6 in-cluster load tests, and produces a full operational runbook.

The API Gateway already has a generic Redis cache helper (`services/api-gateway/internal/cache/cache.go`) and a subscription-tier rate limiter — this plan extends both rather than replacing them. The users table already carries `deleted_at`; soft-delete logic exists in the repository layer. The Helm chart already has `sealed-secrets.yaml` with placeholder encrypted values. All work is additive.

## Technical Context

**Language/Version**: Go 1.23 (API Gateway), TypeScript 5.5 / Next.js 15 (frontend), Python 3.12 (Alembic migration for anonymization columns if needed)
**Primary Dependencies**: chi v5.2.1, go-redis v9, shadcn/ui Dialog, next-intl, K6 v0.51+, Bitnami sealed-secrets controller, golangci-lint, govulncheck, pip-audit, ruff, mypy
**Storage**: PostgreSQL 16 + PostGIS 3.4 (users table — soft delete already present); Redis 7 (auth:attempts:{ip} rate limit counters, zone-stats / top-deals / alert-rules cache keys)
**Testing**: Go table-driven tests + testcontainers (Redis, PG); Vitest + React Testing Library (frontend); K6 scripts for load; OWASP ZAP scan
**Target Platform**: Kubernetes (staging mirrors production HPA limits)
**Performance Goals**: Listing search p95 < 300ms at 1 000 VUs; dashboard LCP < 2 s; JS bundle < 200 KB gzipped
**Constraints**: Zero OWASP ZAP high/critical findings; all CI dependency scans green; GDPR deletion completes PII anonymisation within 1 min and hard-delete within 30 days
**Scale/Scope**: Affects api-gateway, frontend, helm, .github/workflows, tests/load, docs — no new services, no new NATS streams

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I — Polyglot Service Architecture | ✅ PASS | Go for API Gateway changes, Next.js for frontend, Python for any DB migration. No cross-service imports. |
| II — Event-Driven Communication | ✅ PASS | No new inter-service communication. Existing NATS streams and gRPC contracts untouched. |
| III — Country-First Data Sovereignty | ✅ PASS | Cache keys include query-param hash (country code is a query param). Redis 7 used for caching as per constitution. |
| IV — ML-Powered Intelligence | ✅ N/A | No ML changes in this feature. |
| V — Code Quality Discipline | ✅ PASS | CI scanning (govulncheck, pip-audit, npm audit) strengthens existing gates. No new linting bypasses. |
| VI — Security & Ethical Scraping | ✅ PASS | This feature directly implements GDPR, Sealed Secrets, rate limiting, and CORS — the core obligations of Principle VI. |
| VII — Kubernetes-Native Deployment | ✅ PASS | Sealed Secrets in Helm, hard-delete CronJob as K8s CronJob manifest, K6 load test as K8s Job. All declarative. |

**Result**: No gate failures. Proceeding to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/028-production-hardening/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   ├── me-export.yaml   # OpenAPI fragment for GET /api/v1/me/export
│   └── me-delete.yaml   # OpenAPI fragment for DELETE /api/v1/me
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
services/api-gateway/
├── cmd/
│   └── routes.go              # update: mount CSP middleware + auth rate limit on /v1/auth routes
├── internal/
│   ├── middleware/
│   │   ├── cors.go            # update: read ALLOWED_ORIGINS from config (already exists)
│   │   ├── csp.go             # new: CSP header middleware (report-only flag, nonce generation)
│   │   └── auth_ratelimit.go  # new: 5 attempts/min per IP for auth endpoints
│   ├── handler/
│   │   ├── me_export.go       # new: GET /api/v1/me/export
│   │   └── me_delete.go       # new: DELETE /api/v1/me (soft delete + anonymise)
│   └── cache/
│       └── cache.go           # update: add typed helpers ZoneStatsCache, TopDealsCache, AlertRulesCache
├── config/
│   └── config.go              # update: ALLOWED_ORIGINS, CSP_REPORT_ONLY, CSP_REPORT_URI env vars
└── internal/repository/
    └── users.go               # update: AnonymiseUser(ctx, userID) method

frontend/
├── next.config.ts             # update: preconnect headers, bundle analyser
├── src/
│   ├── middleware.ts          # new or update: inject CSP nonce header from api-gateway response
│   ├── app/[locale]/
│   │   ├── layout.tsx         # update: add <CookieConsent />, preconnect <link> tags
│   │   └── privacy/
│   │       └── page.tsx       # new: static privacy policy page (reads markdown per locale)
│   ├── components/
│   │   └── cookie-consent.tsx # new: shadcn Dialog shown on first visit, sets consent cookie
│   └── content/privacy/
│       ├── en.md              # new: English privacy policy
│       ├── fr.md              # new: French privacy policy
│       └── ...                # remaining locales

.github/workflows/
├── ci-go.yml        # update: add govulncheck step, fail on HIGH
├── ci-python.yml    # update: add pip-audit step, fail on HIGH
└── ci-frontend.yml  # update: add npm audit --audit-level=high step

helm/estategap/
├── Chart.yaml                       # update: add sealed-secrets dependency if not present
├── templates/
│   ├── sealed-secrets.yaml          # update: ensure all 8 secrets covered (already has structure)
│   ├── gdpr-hard-delete-cronjob.yaml # new: K8s CronJob runs daily, deletes users where deleted_at < NOW()-30d
│   └── load-test-job.yaml           # new: K8s Job (manual trigger) for K6 in-cluster tests
└── values.yaml                      # update: CSP_REPORT_ONLY flag, ALLOWED_ORIGINS placeholder

tests/load/
├── search.js       # new: 1 000 VUs, 5 min, listing search
├── chat.js         # new: 100 VUs, 10 min, AI chat WebSocket
├── alerts.js       # new: burst 10 000 alert dispatch messages
└── pipeline.js     # new: 50 000 NATS messages to scrape pipeline

docs/
└── runbook.md      # new: architecture overview, incident playbooks, DR, backup/restore
```

**Structure Decision**: Extends the existing monorepo layout. New files follow established per-service conventions (middleware/, handler/, repository/ in api-gateway; components/ in frontend). Load tests land in `tests/load/` alongside existing integration tests.

## Complexity Tracking

No constitution violations — this section is not required.

---

## Phase 0: Research

*See [research.md](./research.md) for full findings.*

### Decision Log

| Topic | Decision | Rationale | Alternatives Considered |
|-------|----------|-----------|------------------------|
| Cache key strategy | SHA-256 hash of sorted query param string | Deterministic, collision-resistant, short key | Full query string (too long, varied encoding); per-field composite (more code, same result) |
| CSP delivery | Go middleware writes `Content-Security-Policy-Report-Only` header; `CSP_REPORT_ONLY=false` flips to enforce | Allows gradual rollout; no Next.js build coupling | Next.js next.config.ts headers (can't share nonce across RSC/client boundary easily) |
| Nonce strategy | Crypto-random nonce per request, injected into CSP header and passed as `<meta name="csp-nonce">` for client hydration | Required for inline Next.js scripts; avoids `unsafe-inline` | Hash-based (not feasible with dynamic RSC scripts); `unsafe-inline` (violates CSP goal) |
| Auth rate limit separation | Separate Redis counter `auth:attempts:{ip}` with TTL 60s, threshold 5 — distinct from subscription-tier limiter | Auth brute-force protection has different semantics to API throughput limiting | Extending existing ratelimit.go (risks coupling two distinct policies) |
| CORS allowlist source | `ALLOWED_ORIGINS` env var (comma-separated), read at startup into chi middleware | Existing cors.go already has the structure; env var aligns with 12-factor | Hardcoded list (inflexible); DB-driven (over-engineered) |
| Sealed Secrets coverage | Extend existing `sealed-secrets.yaml` to cover all 8 secrets: DB_PASSWORD, REDIS_PASSWORD, JWT_SECRET, STRIPE_SECRET_KEY, STRIPE_WEBHOOK_SECRET, LLM_API_KEY, PROXY_CREDENTIALS, SES_CREDENTIALS | Helm template already present; placeholder encrypted values need replacing per environment | Vault (larger operational surface); plain K8s Secrets (violates Principle VI) |
| Cookie consent persistence | `consent` cookie (name: `eg_consent`, value: `granted`/`denied`, max-age: 31536000) | No server-side DB change; survives page reloads and SSR pre-checks | localStorage (not accessible in SSR/middleware); sessionStorage (lost on tab close) |
| Analytics blocking | Conditional load of analytics scripts based on `eg_consent` cookie value read in root layout | Cookie accessible in RSC and Next.js middleware | Zustand flag (lost on reload before hydration) |
| GDPR export data sources | Profile + alert_rules + portfolio_properties + alert_history from PostgreSQL; conversation history from Redis using key pattern `chat:session:{user_id}:*` | Conversations are stored only in Redis (per service 018 architecture) | Skipping Redis conversations (incomplete export); migrating chat to DB (out of scope) |
| Account deletion anonymisation | In-handler: set `deleted_at = now()`, `email = deleted-{uuid}@deleted.invalid`, `name = Deleted User`, clear `avatar_url`. CronJob: hard-DELETE rows where `deleted_at < NOW() - INTERVAL '30 days'` | `deleted_at` already exists; anonymisation is idempotent; CronJob is K8s-native | Immediate hard delete (GDPR allows 30-day grace; safer for accidental deletions); separate service (over-engineered) |
| Load test execution | K8s Job with `grafana/k6:latest` image, hostNetwork for cluster-internal DNS resolution | In-cluster gives accurate service-mesh latency; avoids external network noise | Local laptop (network noise); CI runner (can't sustain 1 000 VUs) |
| DB query analysis | Run `SELECT query, mean_exec_time FROM pg_stat_statements ORDER BY mean_exec_time DESC LIMIT 10` in staging; add targeted indexes via Alembic migration | pg_stat_statements assumed enabled (confirmed in spec assumptions) | Manual EXPLAIN ANALYZE per endpoint (slower, less systematic) |
| Bundle optimisation | `next/dynamic` with `{ ssr: false }` for MapLibre and Recharts components; `next/image` for all listing photos; preconnect `<link>` tags in layout.tsx for API and tile server domains | These are the only components >50 KB each; dynamic import splits them to lazy chunks | Route-level code splitting (already done by Next.js App Router); manual webpack chunking (fragile) |
| Privacy policy delivery | MDX/Markdown files in `frontend/src/content/privacy/{locale}.md`; Next.js static page reads file at build time with `fs.readFileSync`; rendered with `react-markdown` + `remark-gfm` | Static generation = zero runtime cost; already using react-markdown in chat UI | CMS (out of scope); hardcoded JSX (not editable without code change) |

---

## Phase 1: Design & Contracts

*See [data-model.md](./data-model.md) and [contracts/](./contracts/) for full artefacts.*

### Data Model Changes

**No new tables required.** All changes are additive column updates or pure Redis/cookie state:

**`users` table** (PostgreSQL — existing):
- `deleted_at TIMESTAMPTZ` — already present, already checked in repository queries
- `anonymized_at TIMESTAMPTZ NULL` — new column: set when PII fields are overwritten, enables idempotent re-runs
- Email, name, avatar_url fields overwritten in-place during anonymisation (not nulled, replaced with anonymous values)

**Redis key spaces** (new, no schema migration):
- `cache:zone-stats:{hash}` — TTL 300s (zone stats)
- `cache:top-deals:{hash}` — TTL 60s (top deals)
- `cache:alert-rules:{hash}` — TTL 60s (alert rules)
- `auth:attempts:{ip}` — TTL 60s, integer counter (auth rate limit)

**Cookie**:
- `eg_consent` — client cookie, max-age 31536000, SameSite=Lax, path=/

### API Contracts

**GET /api/v1/me/export**

- Auth: Bearer JWT required
- Response: `200 OK` with `Content-Disposition: attachment; filename="estategap-export-{date}.json"`
- Body: JSON object (see [contracts/me-export.yaml](./contracts/me-export.yaml))
  ```json
  {
    "exported_at": "2026-04-17T12:00:00Z",
    "profile": { "id": "...", "email": "...", "name": "...", "created_at": "..." },
    "alert_rules": [...],
    "portfolio_properties": [...],
    "alert_history": [...],
    "conversations": [{ "session_id": "...", "messages": [...] }]
  }
  ```
- Errors: `401 Unauthorized` (no/invalid JWT), `404 Not Found` (user soft-deleted), `500 Internal Server Error`

**DELETE /api/v1/me**

- Auth: Bearer JWT required
- Body: `{ "confirm": "delete my account" }` (confirmation string prevents accidental calls)
- Response: `202 Accepted` with `{ "message": "Account deletion scheduled. PII anonymised immediately." }`
- Side-effects: sets `deleted_at`, `anonymized_at`, overwrites PII fields; invalidates all user sessions in Redis; sends confirmation email via SES; schedules hard-delete via CronJob
- Errors: `400 Bad Request` (missing/wrong confirmation), `401 Unauthorized`, `409 Conflict` (already deleted)

### Quickstart

See [quickstart.md](./quickstart.md) for local dev and staging test instructions.

Key validation steps:
1. `ALLOWED_ORIGINS=http://localhost:3000 go run ./cmd` → verify CORS headers
2. Attempt 6 rapid POST `/api/v1/auth/login` → expect 429 on attempt 6
3. `curl -H "Authorization: Bearer $TOKEN" /api/v1/me/export` → expect JSON download
4. `DELETE /api/v1/me` with body → expect 202, verify `deleted_at` set in DB
5. First visit to frontend → expect cookie consent Dialog before page is interactive
6. `next build && npx bundlesize` → verify < 200 KB gzipped for main chunk
