# Tasks: Production Hardening (028)

**Input**: Design documents from `/specs/028-production-hardening/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared dependencies)
- **[Story]**: Which user story this task belongs to (US1–US4)
- All file paths are relative to the repository root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffold new directories and config changes that all later tasks depend on.

- [x] T001 Create `tests/load/` directory and add K6 test runner README at `tests/load/README.md`
- [x] T002 [P] Create `frontend/src/content/privacy/` directory for locale privacy policy files
- [x] T003 [P] Add `ANALYZE=true` bundle analyser support to `frontend/next.config.ts` (install `@next/bundle-analyzer` as devDep)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure changes that MUST be complete before any user story can be implemented.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [x] T004 Write Alembic migration `services/pipeline/alembic/versions/028_add_performance_indexes.py` — adds `users.anonymized_at TIMESTAMPTZ NULL` column and performance indexes: `ix_listings_country_status_created`, `ix_listings_zone_score_active` (partial), `ix_alert_rules_user_active` (partial), `ix_alert_history_user_created`
- [x] T005 [P] Add typed cache helpers `ZoneStatsCache`, `TopDealsCache`, `AlertRulesCache` to `services/api-gateway/internal/cache/cache.go` — each wraps the existing `GetOrSet` with the correct TTL constant (300s / 60s / 60s) and a `cacheKey(r *http.Request) string` helper using SHA-256 of sorted query params
- [x] T006 [P] Extend `services/api-gateway/internal/config/config.go` to expose three new env vars: `ALLOWED_ORIGINS` (string, comma-separated), `CSP_REPORT_ONLY` (bool, default true), `CSP_REPORT_URI` (string, optional)

**Checkpoint**: Migration applied, cache helpers available, config extended — user story work can begin.

---

## Phase 3: User Story 1 — Fast Listing Search (Priority: P1) 🎯 MVP

**Goal**: Listing search and related API responses are served from Redis cache. Frontend bundle is lean and loads fast with lazy-loaded heavy components.

**Independent Test**: Hit `/api/v1/zones/{id}/stats` twice, verify second response comes from `cache:zone-stats:*` Redis key; run `npm run build` and confirm main JS chunk ≤ 200 KB gzipped; verify MapLibre and Recharts are separate lazy chunks.

### Implementation for User Story 1

- [x] T007 [US1] Wire `ZoneStatsCache` into the zone-stats handler in `services/api-gateway/internal/handler/zones.go` — check cache before DB query, set cache on miss, include `X-Cache: HIT|MISS` response header
- [x] T008 [US1] Wire `TopDealsCache` into the top-deals handler in `services/api-gateway/internal/handler/listings.go` using the same cache-aside pattern
- [x] T009 [US1] Wire `AlertRulesCache` into the alert-rules handler in `services/api-gateway/internal/handler/alerts.go` using the same cache-aside pattern
- [x] T010 [P] [US1] Convert `MapLibreMap` component import to `next/dynamic(() => import('@/components/map/maplibre-map'), { ssr: false })` in every file that imports it under `frontend/src/`
- [x] T011 [P] [US1] Convert `RechartsWrapper` (or equivalent chart component) import to `next/dynamic` with `{ ssr: false }` in every file that imports it under `frontend/src/`
- [x] T012 [P] [US1] Replace all `<img>` tags in listing card and detail components with `next/image` in `frontend/src/components/listings/` — set `sizes` and `priority` attributes appropriately
- [x] T013 [US1] Add `<link rel="preconnect">` tags for the API domain and MapLibre tile server to `frontend/src/app/[locale]/layout.tsx` in the `<head>` section

**Checkpoint**: Cache layer active for all three endpoints. Bundle split confirmed via `npm run build` output.

---

## Phase 4: User Story 2 — Secure Platform Access (Priority: P1)

**Goal**: CORS is restricted to an allowlist. CSP headers are served (report-only first). Auth endpoints have IP-based rate limiting at 5 attempts/min. All 8 sensitive secrets are in Sealed Secrets. CI dependency scans fail the pipeline on high-severity findings.

**Independent Test**: Attempt 6 rapid auth POSTs → 6th returns 429. Request from unlisted origin → 403. OWASP ZAP baseline scan against staging returns 0 high/critical. `govulncheck ./...`, `pip-audit`, and `npm audit --audit-level=high` all exit 0 in CI.

### Implementation for User Story 2

- [x] T014 [US2] Update `services/api-gateway/internal/middleware/cors.go` to read the parsed `cfg.AllowedOrigins` slice from config (T006) instead of any hardcoded/wildcard origin — reject requests from unlisted origins with 403
- [x] T015 [P] [US2] Create `services/api-gateway/internal/middleware/csp.go` — generates a 128-bit crypto-random nonce per request, builds the CSP header string (directives per research.md), writes either `Content-Security-Policy-Report-Only` or `Content-Security-Policy` based on `cfg.CSPReportOnly`, sets `report-uri` when `cfg.CSPReportURI` is non-empty
- [x] T016 [US2] Register CSP middleware globally in `services/api-gateway/cmd/routes.go` (after CORS, before auth middleware)
- [x] T017 [P] [US2] Create `services/api-gateway/internal/middleware/auth_ratelimit.go` — uses Redis `INCR` + `EXPIRE` (only on key creation) on key `auth:attempts:{client_ip}`, threshold 5, returns `429 Too Many Requests` with `Retry-After: 60` header on breach
- [x] T018 [US2] Apply `AuthRateLimitMiddleware` to the `/v1/auth` route group in `services/api-gateway/cmd/routes.go`
- [x] T019 [P] [US2] Add `govulncheck` step to `.github/workflows/ci-go.yml` — install via `go install golang.org/x/vuln/cmd/govulncheck@latest`, run `govulncheck ./...` on api-gateway and all Go services, fail job on any finding
- [x] T020 [P] [US2] Add `pip-audit` step to `.github/workflows/ci-python.yml` — run `uv run pip-audit` in each Python service directory, fail job on HIGH or CRITICAL severity findings
- [x] T021 [P] [US2] Add `npm audit` step to `.github/workflows/ci-frontend.yml` — run `npm audit --audit-level=high` in `frontend/`, fail job on high-severity findings
- [x] T022 [US2] Audit `helm/estategap/templates/sealed-secrets.yaml` — verify it contains SealedSecret entries for all 8 required keys: `DB_PASSWORD`, `REDIS_PASSWORD`, `JWT_SECRET`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `LLM_API_KEY`, `PROXY_CREDENTIALS`, `SES_CREDENTIALS`; add any missing entries with placeholder encrypted values and document the sealing procedure in a comment

**Checkpoint**: Auth rate limit live, CSP report-only active, all CI scans wired, Sealed Secrets complete.

---

## Phase 5: User Story 3 — GDPR Rights Fulfilment (Priority: P2)

**Goal**: Users can export all their data, delete their account (with immediate PII anonymisation and 30-day hard delete), and manage cookie consent. A privacy policy page is available in all supported locales.

**Independent Test**: `GET /api/v1/me/export` returns JSON containing profile, alert_rules, portfolio_properties, alert_history, and conversations fields. `DELETE /api/v1/me` with body returns 202 and sets `deleted_at`/`anonymized_at` in DB. First incognito visit shows consent Dialog before any analytics fire.

### Implementation for User Story 3

- [x] T023 [US3] Add `AnonymiseUser(ctx context.Context, userID uuid.UUID) error` method to `services/api-gateway/internal/repository/users.go` — executes a single UPDATE setting `deleted_at = now()`, `anonymized_at = now()`, `email = 'deleted-' || user_id || '@deleted.invalid'`, `name = 'Deleted User'`, `avatar_url = NULL`
- [ ] T024 [P] [US3] Implement `GET /api/v1/me/export` handler in `services/api-gateway/internal/handler/me_export.go` — aggregates user profile from PostgreSQL, alert_rules, portfolio_properties, alert_history (last 1000), and conversation sessions from Redis SCAN `chat:session:{userID}:*`; sets `Content-Disposition: attachment` header; returns JSON matching the schema in `specs/028-production-hardening/contracts/me-export.yaml`
- [ ] T025 [P] [US3] Implement `DELETE /api/v1/me` handler in `services/api-gateway/internal/handler/me_delete.go` — validates `{"confirm": "delete my account"}` body, calls `repo.AnonymiseUser`, invalidates Redis session keys `session:{userID}:*`, sends async confirmation email via existing SES client, returns 202 with `scheduled_hard_delete_after` date; matches contract in `specs/028-production-hardening/contracts/me-delete.yaml`
- [x] T026 [US3] Register GDPR endpoints in `services/api-gateway/cmd/routes.go` under the authenticated `/api/v1` group: `GET /me/export` → `meExportHandler.ServeHTTP`, `DELETE /me` → `meDeleteHandler.ServeHTTP`
- [x] T027 [P] [US3] Create `helm/estategap/templates/gdpr-hard-delete-cronjob.yaml` — K8s CronJob scheduled `0 2 * * *` UTC, runs a PostgreSQL client pod executing: cascade DELETE of alert_rules/portfolio_properties/alert_history for expired users, then `DELETE FROM users WHERE deleted_at < NOW() - INTERVAL '30 days'`, then Redis key cleanup via a shell loop on `chat:session:{id}:*` for each deleted user ID
- [x] T028 [P] [US3] Create `frontend/src/components/cookie-consent.tsx` — shadcn `Dialog` component: shown when `eg_consent` cookie is absent, presents accept/deny buttons, writes `eg_consent=granted|denied` cookie (max-age 31536000, SameSite=Lax, Secure, path=/), exported as a Client Component
- [x] T029 [US3] Add `<CookieConsent />` to `frontend/src/app/[locale]/layout.tsx`; wrap any analytics `<Script>` tags in a `ConsentGate` client component that reads the `eg_consent` cookie and renders children only when value is `granted`
- [x] T030 [P] [US3] Write privacy policy Markdown files for all supported locales in `frontend/src/content/privacy/` (at minimum `en.md`, `fr.md`, `de.md`, `es.md`, `it.md`, `pt.md`) — include sections: data collected, legal basis, retention periods, user rights (access, deletion, portability), cookie policy, contact/DPO details
- [x] T031 [US3] Create `frontend/src/app/[locale]/privacy/page.tsx` — Next.js static page that reads the locale-specific Markdown file at build time with `fs.readFileSync`, renders it using `react-markdown` with `remark-gfm`, generates static params for all supported locales
- [x] T032 [P] [US3] Create `frontend/src/app/[locale]/data-removal/page.tsx` — agent/third-party data removal request form using react-hook-form + Zod; fields: requester name, email, subject type (agent/landlord/other), description, GDPR rights type; on submit, POSTs to `POST /api/v1/data-removal-requests`; add corresponding stub handler in api-gateway if not already present

**Checkpoint**: Full GDPR flow testable — export, delete, consent banner, privacy page, removal form all functional.

---

## Phase 6: User Story 4 — Operational Confidence (Priority: P3)

**Goal**: K6 load test scripts cover all four scenarios and run in-cluster. Operational runbook is complete.

**Independent Test**: K6 `search.js` runs to completion against staging with p95 < 300ms threshold. `docs/runbook.md` is reviewed in a tabletop exercise for each incident type.

### Implementation for User Story 4

- [x] T033 [US4] Write `tests/load/search.js` — K6 script: 1 000 VUs, 5 min duration, 30s ramp-up, targets `GET /api/v1/listings` with varied country/zone/price filters; thresholds: `http_req_duration{p(95)}<300`, `http_req_failed<0.01`; outputs summary to stdout and InfluxDB/Prometheus remote-write if env var set
- [x] T034 [P] [US4] Write `tests/load/chat.js` — K6 script: 100 VUs, 10 min, WebSocket connections to `wss://{WS_HOST}/chat`; each VU sends 5 chat messages per minute; thresholds: `ws_session_duration{p(95)}<5000`, `ws_msgs_sent>0`
- [x] T035 [P] [US4] Write `tests/load/alerts.js` — K6 script: burst scenario — 100 VUs × 100 iterations (no ramp), targets alert dispatch trigger endpoint; thresholds: `http_req_duration{p(95)}<500`, `http_req_failed<0.01`
- [x] T036 [P] [US4] Write `tests/load/pipeline.js` — K6 script using `k6/x/nats` extension (or HTTP NATS proxy): publishes 50 000 messages to the `listings.ingested` subject; measures publish throughput; threshold: completes within 5 min
- [x] T037 [US4] Create `helm/estategap/templates/load-test-job.yaml` — K8s Job (manual trigger, no schedule) using `grafana/k6:latest` image with NATS extension; mounts K6 scripts from a ConfigMap (`k6-scripts`); runs `search.js` → `chat.js` → `alerts.js` → `pipeline.js` sequentially; env vars for target host injected via Helm values
- [x] T038 [US4] Write `docs/runbook.md` with these sections: (1) Architecture overview with Mermaid service graph, (2) Service dependency map and startup order, (3) Incident playbooks — Scraper Blocked (proxy rotation, portal backoff), Model Degraded (roll back ONNX artefact in MinIO, restart ml-scorer), DB Full (identify large tables, pg_dump offload, resize PVC), NATS Lag (consumer group check, replay from stream, scale pipeline), High Error Rate (trace via Grafana Tempo, identify failing service, scale via HPA), HPA Not Scaling (check KEDA ScaledObject, verify metrics-server, manual kubectl patch), (4) Scaling procedures — manual HPA override and node addition, (5) Backup/restore — `pg_dump`/`pg_restore` commands, MinIO `mc mirror`, NATS stream export, (6) Disaster recovery — full cluster rebuild from Helm + latest backup step-by-step, (7) Escalation contacts table (roles and methods, filled by operator)

**Checkpoint**: Load tests run successfully in staging. Runbook reviewed and approved.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final validation, CSP enforcement switch, and verification of all acceptance criteria.

- [ ] T039 [P] Run the full quickstart.md validation checklist against staging — verify CORS headers, rate limiting, cache HIT/MISS headers, GDPR export completeness, account deletion DB state, cookie consent blocking behaviour, bundle size, and preconnect hints; document any discrepancies
- [ ] T040 [P] Run OWASP ZAP baseline scan against staging: `docker run ghcr.io/zaproxy/zaproxy:stable zap-baseline.py -t https://staging.estategap.com -r zap-report.html`; fix any HIGH or CRITICAL findings before marking this task complete
- [ ] T041 Switch `CSP_REPORT_ONLY=false` in `helm/estategap/values-staging.yaml` after ZAP scan passes and CSP report-only violations have been resolved; validate no JS functionality is broken in staging before promoting to production values

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — can start immediately
- **Foundational (Phase 2)**: Depends on Setup — BLOCKS all user stories (T004–T006)
- **User Stories (Phases 3–6)**: All depend on Foundational phase
  - US1 (P1) and US2 (P1) can proceed in parallel once Foundational is complete
  - US3 (P2) depends on Foundational; can run in parallel with US1/US2 but `AnonymiseUser` (T023) requires DB migration (T004)
  - US4 (P3) is entirely independent of US1–US3 and can proceed in parallel
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

| Story | Depends On | Blocking Tasks |
|-------|-----------|----------------|
| US1 — Performance | T004 (migration), T005 (cache helpers) | T007–T013 |
| US2 — Security | T006 (config) | T014–T022 |
| US3 — GDPR | T004 (migration), T023 (AnonymiseUser) | T024–T032 |
| US4 — Operational | None (documentation + load scripts) | T033–T038 |

### Within Each User Story

- Cache wiring (T007–T009): sequential, each handler is a separate file → can partially parallel
- Frontend perf (T010–T013): all different files → fully parallel
- Security middleware (T014–T018): CSP before mount (T015 before T016); auth rate limit before mount (T017 before T018)
- GDPR backend (T023 before T024/T025 before T026)
- GDPR frontend (T028 before T029; T030 before T031)
- Load tests (T033–T036): fully parallel, different files

### Parallel Opportunities

All `[P]` tasks within a phase can launch simultaneously as separate agents.

---

## Parallel Example: Phase 4 (Security)

```
# These can all run in parallel:
Agent A: T015 — Create csp.go middleware
Agent B: T017 — Create auth_ratelimit.go middleware
Agent C: T019 — Add govulncheck to ci-go.yml
Agent D: T020 — Add pip-audit to ci-python.yml
Agent E: T021 — Add npm audit to ci-frontend.yml

# Then sequentially:
T016 — Mount CSP middleware in routes.go   (after T015)
T018 — Mount auth rate limit in routes.go  (after T017)
T022 — Audit Sealed Secrets YAML
```

## Parallel Example: Phase 5 (GDPR)

```
# These can all run in parallel:
Agent A: T024 — me_export.go handler
Agent B: T025 — me_delete.go handler
Agent C: T027 — GDPR CronJob Helm manifest
Agent D: T028 — CookieConsent component
Agent E: T030 — Privacy policy Markdown files

# Then sequentially:
T023 — AnonymiseUser repository method  (before T024, T025)
T026 — Register GDPR routes             (after T024, T025)
T029 — Wire CookieConsent in layout     (after T028)
T031 — Privacy policy page              (after T030)
T032 — Data removal request form        (parallel with T031)
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 — both P1)

1. Complete Phase 1 (Setup) + Phase 2 (Foundational)
2. Complete Phase 3 (US1 — Performance) in parallel with Phase 4 (US2 — Security)
3. **STOP and VALIDATE**: Run quickstart.md performance checks + OWASP ZAP scan
4. Ship P1 stories to staging

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 + US2 (parallel) → Performance + Security → **Deploy/Demo (MVP)**
3. US3 → GDPR compliance → **Deploy (legal requirement)**
4. US4 → Load testing + Runbook → **Operational readiness**
5. Polish → ZAP scan clean, CSP enforced → **Production-ready**

### Parallel Team Strategy

With multiple developers:

1. All: Setup + Foundational (Phases 1–2) together (~1h)
2. Once Foundational done:
   - Developer A: US1 — Performance (T007–T013)
   - Developer B: US2 — Security backend (T014–T022)
   - Developer C: US3 — GDPR (T023–T032)
   - Developer D: US4 — Load tests + Runbook (T033–T038)
3. All: Polish (Phase 7) after stories merge

---

## Task Summary

| Phase | Tasks | Story | Parallel |
|-------|-------|-------|----------|
| Setup | T001–T003 | — | T002, T003 |
| Foundational | T004–T006 | — | T005, T006 |
| US1 Performance | T007–T013 | US1 | T010–T013 |
| US2 Security | T014–T022 | US2 | T015, T017, T019–T022 |
| US3 GDPR | T023–T032 | US3 | T024–T025, T027–T028, T030, T032 |
| US4 Operational | T033–T038 | US4 | T034–T036 |
| Polish | T039–T041 | — | T039, T040 |
| **Total** | **41 tasks** | | |

---

## Notes

- `[P]` tasks = different files, no incomplete dependencies — safe to parallelise
- Each user story is independently completable and testable
- Commit after each phase checkpoint
- CSP starts report-only (T015); only enforce after ZAP scan passes (T041)
- DB migration (T004) uses `CREATE INDEX CONCURRENTLY` — safe on live DB, takes longer
- GDPR hard-delete CronJob (T027) dry-run in staging with a test user before production
