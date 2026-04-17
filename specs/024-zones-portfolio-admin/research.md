# Research: Zone Analytics, Portfolio Tracker & Admin Panel

**Feature**: 024-zones-portfolio-admin  
**Date**: 2026-04-17

---

## R-001: Zone Analytics — Existing API coverage vs. required metrics

**Decision**: Extend `GetZoneAnalytics` repository method to include `avg_days_on_market` per month; compute `inventory_count` and `deal_frequency` on the frontend from existing fields.

**Rationale**:
- The existing `/api/v1/zones/{id}/analytics` response already returns `median_price_m2_eur`, `listing_count`, `deal_count` per month.
- `inventory_count` is the current-period `listing_count` (last month in the series).
- `deal_frequency` = `deal_count / listing_count` (derived, no backend change).
- `avg_days_on_market` requires a new SQL expression: `AVG(EXTRACT(EPOCH FROM (NOW() - l.first_seen_at)) / 86400)` filtered to active listings in the zone. This is added to `GetZoneAnalytics` as a per-month field.
- No new endpoint is needed. The analytics response schema gains an `avg_days_on_market` field (number, double).

**Alternatives considered**:
- New `/zones/{id}/stats` snapshot endpoint — rejected; snapshot data duplicates what the extended analytics already provides; an extra round-trip hurts FCP.
- Compute days-on-market in frontend from listing data — rejected; listings are paginated and fetching all for a zone is expensive.

---

## R-002: Price Distribution Histogram — data source and binning strategy

**Decision**: New backend endpoint `GET /api/v1/zones/{id}/price-distribution` returns a flat list of current listing `price_per_m2_eur` values for the zone (capped at 500 values). Frontend uses `d3-array`'s `bin()` to compute histogram bins client-side.

**Rationale**:
- d3-array is already a dependency of MapLibre and is safe to import.
- Bin thresholds are data-driven (Sturges' rule: `ceil(log2(n)) + 1`), making them responsive to data density.
- Returning raw price values (not pre-binned buckets) gives the frontend full control over bin count and formatting, avoiding a backend API change whenever the UI wants different granularity.
- Cap at 500 values keeps the payload < 8KB (500 × 8-byte float64 = 4KB JSON).

**Alternatives considered**:
- Pre-computed histogram buckets on backend — rejected; tight coupling between bin count and API contract; harder to adjust without version bump.
- Compute entirely from existing zone detail median — rejected; a single median cannot represent distribution shape.

---

## R-003: Zone Comparison — data fetching strategy

**Decision**: The comparison tool fetches zone analytics for each selected zone individually via the existing `GET /api/v1/zones/{id}/analytics` endpoint (parallel TanStack Query requests). The existing `GET /zones/compare?ids=` endpoint is used only for the side-by-side summary table (static snapshot metrics), not for the time-series overlay charts.

**Rationale**:
- The `Compare` endpoint already returns `ZoneDetail`-equivalent data (id, name, country, median_price_m2_eur, listing_count, deal_count, price_trend_pct) for multiple zones in one request — ideal for the comparison table.
- Time-series data for overlay charts requires the full monthly series per zone; fetching analytics individually (with caching) is simpler than building a bulk analytics endpoint.
- TanStack Query with `useQueries` enables parallel fetching with shared cache — previously-viewed zone analytics are free from cache.

**Alternatives considered**:
- New `POST /zones/compare-analytics` bulk endpoint — rejected; adds backend complexity and a new API surface for a pattern already solvable client-side with parallel queries.

---

## R-004: Currency conversion — architecture

**Decision**: Currency conversion lives in the frontend. A Next.js Route Handler at `/api/exchange-rates` fetches EUR-base rates from the European Central Bank (ECB) daily XML feed, caches the result in Redis (24h TTL via the existing Redis client available to Next.js API routes), and returns a JSON map of `{ [currency_code]: rate_vs_eur }`. A `currency.ts` utility module provides `convertFromEUR(amount, targetCurrency, rates)` and `formatCurrency(amount, currency, locale)`.

**Rationale**:
- All backend prices are stored and returned in EUR-normalised form (e.g., `median_price_m2_eur`, `asking_price_eur`). This is a constitutional guarantee (Principle III).
- ECB provides a free, reliable, daily-updated XML feed at `https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml` — no API key required, no rate limits relevant to this usage.
- A Next.js Route Handler with Redis caching avoids making an external HTTP call on every user page load; rates are stable within a day.
- User currency preference is stored in the NextAuth session (existing `subscriptionTier` pattern extended to `preferredCurrency`), defaulting to EUR.

**Alternatives considered**:
- Separate exchange rate microservice — rejected; over-engineered for what is essentially a cached HTTP fetch plus a map lookup.
- Commercial API (Fixer.io, Open Exchange Rates) — rejected; ECB feed is free, authoritative for EUR, and covers all currencies needed for European real estate markets.
- Backend currency conversion (return prices pre-converted) — rejected; would require the API Gateway to know the user's preferred currency per-request and invalidate all caches differently per-user. EUR normalisation is already in the contract.

---

## R-005: Portfolio — data persistence and ML value estimation

**Decision**: New `portfolio_properties` PostgreSQL table. All monetary fields stored in the user's chosen currency plus EUR-normalised equivalents. ML estimated value sourced on-demand from the existing `GET /api/v1/model/estimate?lat=&lng=&area_m2=&property_type=` endpoint (MLHandler.Estimate).

**Rationale**:
- Storing original currency preserves the user's mental model; EUR-normalised column enables consistent aggregation server-side.
- The existing `MLHandler.Estimate` endpoint already takes `lat`, `lng`, `area_m2`, `property_type` and returns `estimated_price_eur`. Portfolio properties with a geocoded address can be passed to this endpoint.
- Geocoding of the address is performed at property creation time via a Next.js server action that calls a geocoding API (OpenStreetMap Nominatim — free, no key, appropriate for EU data).

**Alternatives considered**:
- New ML estimate endpoint specifically for portfolio — rejected; the existing estimate endpoint is generic enough and avoids duplication.
- Client-side geocoding — rejected; exposes geocoding to CORS constraints and client-side latency; server-side is more reliable.

---

## R-006: Portfolio — currency preference storage

**Decision**: User currency preference stored as a new `preferred_currency` column in the `users` table (Alembic migration). Exposed via `GET /api/v1/auth/me` response and settable via `PATCH /api/v1/auth/me`. The NextAuth session is updated with this value at login and after mutations via the existing token refresh flow.

**Rationale**:
- Currency preference must survive browser sessions and be consistent across devices — therefore server-persisted, not localStorage.
- Extending the existing `users` table and `/auth/me` endpoint is the minimal-change approach; no new endpoint needed.

**Alternatives considered**:
- LocalStorage preference — rejected; does not survive cross-device usage; inconsistent with user settings philosophy.
- Separate user settings table — rejected; over-engineered for a single new column.

---

## R-007: Admin — backend endpoint structure

**Decision**: New `/api/v1/admin/` route group in the Go API Gateway, mounted under a `RequireAdmin` middleware that validates the JWT `role` claim equals `"admin"`. Five sub-routes map to the five admin tabs.

**Rationale**:
- The existing JWT claims include `Email` (via `AccessTokenClaims` in auth service). Since admin role assignment is already email-domain-based, the JWT can include a `role` claim (e.g., `"admin"` or `"user"`) at token issuance — requires extending `AccessTokenClaims` struct and the login handler.
- A single dedicated middleware (`RequireAdmin`) follows the existing pattern (`RequireAuth`) and makes the guard visible and testable in isolation.

**Alternatives considered**:
- Frontend-only guard — rejected; trivially bypassable; API data would still be exposed. Backend guard is the only secure option.
- Separate admin microservice — rejected; over-engineered; admin traffic is very low; Go api-gateway already has the DB/Redis connections needed.

---

## R-008: Admin — scraping stats data source

**Decision**: Scraping health stats queried from PostgreSQL tables (`portals`, `scraping_runs` or equivalent tracking table). If a `scraping_runs` table does not exist, the admin handler queries Redis for per-portal heartbeat keys set by the spider workers (pattern: `scraper:health:{portal_id}`).

**Rationale**:
- Spider workers (feature 011) already write heartbeat/status information to Redis (`scraper:health:*` keys). This is the lowest-latency source for current status.
- A PostgreSQL query can provide historical aggregates (24h listings count, error rate) from the `listings` table filtered by `portal` and `created_at`.

---

## R-009: Admin — manual retrain trigger

**Decision**: `POST /api/v1/admin/ml/retrain` publishes a NATS JetStream message to subject `ml.retrain.requested` with payload `{ country: string, requested_by: string, job_id: uuid }`. The ml-trainer service (Python, feature 014) already subscribes to NATS and handles this event by creating a Kubernetes Job. The API Gateway responds immediately with `{ job_id, status: "queued" }`.

**Rationale**:
- Constitution Principle II mandates NATS for async inter-service events. A manual retrain is an async operation (training takes minutes); a fire-and-forget NATS publish is the correct pattern.
- The ml-trainer already consumes NATS events for scheduled retraining (feature 014). Adding a `ml.retrain.requested` subject extends this existing consumer.
- The `job_id` UUID allows the frontend to poll a status endpoint or display the reference to the admin.

**Alternatives considered**:
- Direct K8s API call from Go api-gateway — rejected; requires K8s RBAC for the api-gateway pod; couples the gateway to K8s internals.
- gRPC call to ml-trainer — rejected; NATS is already the constitution-prescribed async channel; adding a gRPC endpoint to ml-trainer just for this would duplicate the event-driven pattern.

---

## R-010: Admin — system health metrics source

**Decision**: System health tab fetches three data points:
- **NATS**: NATS monitoring HTTP endpoint (`http://nats:8222/jsz?all=true`) — available inside the cluster.
- **PostgreSQL**: `pg_stat_activity` and `pg_database_size()` queries run by the admin handler using the existing `pgxpool`.
- **Redis**: `INFO memory` and `INFO stats` commands via the existing `go-redis` client.

All three are called by the admin handler, aggregated into a single JSON response, and returned to the frontend.

**Rationale**:
- All three data sources are accessible from inside the cluster to the api-gateway pod without new infrastructure.
- A single aggregated endpoint avoids three separate frontend requests and reduces N×CORS preflight overhead.
- Prometheus is the long-term source for NATS consumer lag, but the NATS monitoring API is simpler for a direct query without requiring Prometheus to be reachable from the api-gateway.

---

## R-011: Frontend middleware admin guard

**Decision**: Update `middleware.ts` to check `session.user.role === "admin"` for routes matching `/*/admin`. On failure, redirect to `/[locale]/dashboard` with a query param `?error=forbidden`.

**Rationale**:
- Next.js middleware runs on every request before the page renders, making it the earliest possible guard.
- Middleware cannot return a 403 response for navigational requests (browser expects HTML); redirect is the correct UX.
- The API routes (`/api/v1/admin/*`) return 403 from the Go backend — the frontend middleware is a UX convenience, not a security boundary.

---

## R-012: i18n — translation key strategy

**Decision**: Add new namespaces `zoneAnalytics`, `portfolio`, and `admin` to all 10 locale JSON files. English file written first; other locales use English values as fallback (next-intl already handles missing keys gracefully with fallback locale).

**Rationale**: Consistent with the existing pattern where namespaces map 1:1 to major page sections.
