# Tasks: Zone Analytics, Portfolio Tracker & Admin Panel

**Input**: Design documents from `specs/024-zones-portfolio-admin/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1–US6)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Directory creation, OpenAPI contract publication, and i18n scaffolding needed before any implementation begins.

- [X] T001 Create frontend component directories: `frontend/src/components/zones/`, `frontend/src/components/portfolio/`, `frontend/src/components/admin/`; and page directory `frontend/src/app/[locale]/(protected)/zones/[id]/`
- [X] T002 [P] Add `zoneAnalytics`, `portfolio`, and `admin` i18n namespace keys to `frontend/src/messages/en.json` — include keys for all labels, headings, error messages, empty states, and CTA buttons referenced in the spec
- [X] T003 [P] Update `services/api-gateway/openapi.yaml` to include: extended `ZoneAnalytics.months` item with `avg_days_on_market`, new `ZonePriceDistribution` schema, `PortfolioProperty`, `PortfolioSummary`, `CreatePortfolioPropertyRequest`, `UpdatePortfolioPropertyRequest`, and all admin schemas (`ScrapingPortalStat`, `MLModelVersion`, `AdminUser`, `CountryConfig`, `SystemHealth`) — copy from `specs/024-zones-portfolio-admin/contracts/`
- [X] T004 Regenerate TypeScript API types by running `npm run generate-api-types` inside `frontend/` — verify `frontend/src/types/api.ts` contains new schemas; commit the generated file

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before any user story implementation. Includes JWT role claims, admin middleware, DB migrations, zone analytics SQL extension, currency utilities, and middleware admin guard.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 Extend `AccessTokenClaims` struct in `services/api-gateway/internal/service/auth.go` with `Role string \`json:"role"\`` field; populate it at token issuance in `services/api-gateway/internal/handler/auth.go` — `role = "admin"` when email ends with `@estategap.com`, else `"user"`
- [X] T006 [P] Create `services/api-gateway/internal/middleware/admin.go` — implement `RequireAdmin(next http.Handler) http.Handler` that reads the JWT role claim from context (set by existing `Authenticator`) and writes HTTP 403 + JSON error when role is not `"admin"`
- [X] T007 [P] Create Alembic migration `services/pipeline/alembic/versions/xxxx_add_portfolio_properties.py` — create the `portfolio_properties` table with all columns and indexes defined in `specs/024-zones-portfolio-admin/data-model.md` including the `updated_at` auto-update trigger
- [X] T008 [P] Create Alembic migration `services/pipeline/alembic/versions/xxxx_add_users_preferred_currency.py` — add `preferred_currency VARCHAR(3) NOT NULL DEFAULT 'EUR'` column to the `users` table
- [X] T009 Extend `ZoneMonthStat` struct in `services/api-gateway/internal/repository/zones.go` with `AvgDaysOnMarket float64` field; update `GetZoneAnalytics` SQL query to compute `COALESCE(AVG(EXTRACT(EPOCH FROM (NOW() - l.first_seen_at)) / 86400), 0)::double precision AS avg_days_on_market` in the `stats` CTE; update `pgx.CollectRows` scan to include the new column; update `zoneAnalyticsFromMonths` mapping function in `services/api-gateway/internal/handler/zones.go` to expose `avg_days_on_market` in the JSON response
- [X] T010 [P] Add `GetZonePriceDistribution(ctx, zoneID) ([]float64, int, error)` to `services/api-gateway/internal/repository/zones.go` — query `SELECT price_per_m2_eur FROM listings WHERE zone_id = $1 AND status = 'active' ORDER BY RANDOM() LIMIT 500` plus `SELECT COUNT(*) FROM listings WHERE zone_id = $1 AND status = 'active'`; cache result for 5 minutes using same Redis pattern as `GetZoneAnalytics`; add `PriceDistribution(w, r)` handler to `services/api-gateway/internal/handler/zones.go` and register route `r.Get("/zones/{id}/price-distribution", zonesHandler.PriceDistribution)` in `services/api-gateway/cmd/routes.go`
- [X] T011 [P] Create `frontend/src/app/api/exchange-rates/route.ts` — Next.js Route Handler that fetches ECB daily XML feed (`https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml`), parses it into `Record<string, number>` (rate vs EUR), caches the result in Redis with a 24-hour TTL key `"exchange_rates:ecb:daily"`, and returns JSON; fall back to cached value on fetch failure
- [X] T012 [P] Create `frontend/src/lib/currency.ts` — export `convertFromEUR(amountEUR: number, currency: string, rates: Record<string, number>): number`, `formatCurrency(amount: number, currency: string, locale: string): string`, and `SUPPORTED_CURRENCIES: string[]` constant; EUR rate is always 1.0
- [X] T013 [P] Create `frontend/src/hooks/useExchangeRates.ts` — TanStack Query hook that fetches `/api/exchange-rates`; stale time 60 minutes; returns `{ rates, isLoading, error }`
- [X] T014 Update `frontend/src/middleware.ts` — add admin route guard: after existing authentication check, for paths matching `/:locale/admin(/*)?`, verify `token.role === "admin"`; if not, redirect to `/:locale/dashboard?error=forbidden`
- [X] T015 [P] Add new API client functions to `frontend/src/lib/api.ts`: `fetchZonePriceDistribution(accessToken, zoneId)`, `fetchPortfolioProperties(accessToken)`, `createPortfolioProperty(accessToken, body)`, `updatePortfolioProperty(accessToken, id, body)`, `deletePortfolioProperty(accessToken, id)` — follow exact patterns of existing `fetchZoneAnalytics` and `createCustomZone` functions using the typed `openapi-fetch` client

**Checkpoint**: Foundation ready — JWT carries role, admin middleware exists, migrations ready, zone analytics SQL extended, currency utils available, middleware guards admin. User story implementation can now begin.

---

## Phase 3: User Story 1 — Zone Analytics Deep Dive (Priority: P1) 🎯 MVP

**Goal**: Replace the `/zones/[id]` stub with a fully functional analytics detail page showing six metrics, price trend chart, volume chart, and price distribution histogram.

**Independent Test**: Navigate to `/en/zones/{any-valid-zone-id}`. Verify: six metric tiles display non-zero values; the 12-month price trend LineChart renders with data points; the volume BarChart renders; the price histogram renders with binned bars. Open browser network tab and confirm a single `zones/{id}` detail call and one `zones/{id}/analytics` call complete within 2 seconds.

- [X] T016 Create `frontend/src/hooks/useZoneStats.ts` — combine `useQuery` for zone detail (`GET /api/v1/zones/{id}`) and zone analytics (`GET /api/v1/zones/{id}/analytics`) into a single hook returning `{ zone, analytics, isLoading, error }`; reuse existing `fetchZoneAnalytics` and add `fetchZoneDetail` (via `GET /api/v1/zones/{id}`) to `lib/api.ts` if not already present
- [X] T017 [P] [US1] Create `frontend/src/components/zones/ZoneMetricsBar.tsx` — six `Card` tiles in a responsive CSS grid displaying: median price/m² (last month's `median_price_m2_eur` converted to preferred currency), 12-month trend % (first vs last month), total volume (sum of `listing_count`), avg days on market (last month's `avg_days_on_market`), inventory (last month's `listing_count`), deal frequency % (`deal_count / listing_count * 100`); accept `analytics: ZoneAnalytics`, `rates: Record<string,number>`, `preferredCurrency: string` as props
- [X] T018 [P] [US1] Create `frontend/src/components/zones/ZonePriceTrendChart.tsx` — Recharts `ResponsiveContainer` + `LineChart` rendering 12 monthly `median_price_m2_eur` values converted to preferred currency on Y-axis; X-axis shows abbreviated month labels; include `Tooltip` showing exact value and date; accept `months: ZoneAnalytics["months"]`, `rates`, `preferredCurrency` as props
- [X] T019 [P] [US1] Create `frontend/src/components/zones/ZoneVolumeChart.tsx` — Recharts `BarChart` rendering 12 monthly `listing_count` values; X-axis is month, Y-axis is count; bars colored by deal tier ratio (`deal_count / listing_count`); include `Tooltip`
- [X] T020 [P] [US1] Create `frontend/src/components/zones/ZonePriceHistogram.tsx` — fetches `GET /api/v1/zones/{id}/price-distribution` via TanStack Query; uses `d3-array` `bin()` with Sturges threshold count (`Math.ceil(Math.log2(n)) + 1`); renders as Recharts `BarChart`; shows empty state with warning when fewer than 5 data points; convert `prices_eur` to preferred currency before binning
- [X] T021 [US1] Create `frontend/src/components/zones/ZoneAnalyticsClient.tsx` — `"use client"` component that composes `ZoneMetricsBar`, `ZonePriceTrendChart`, `ZoneVolumeChart`, `ZonePriceHistogram`; reads preferred currency from session; calls `useZoneStats`, `useExchangeRates`; handles loading skeletons and error states per component
- [X] T022 [US1] Create `frontend/src/app/[locale]/(protected)/zones/[id]/page.tsx` — async server component following the pattern in `listing/[id]/page.tsx`; awaits `params`, calls `createServerApiClient()` to prefetch zone detail, passes `initialZone` to `ZoneAnalyticsClient`; add `generateMetadata` returning zone name + country; create sibling `loading.tsx` with `LoadingSkeleton` rows

**Checkpoint**: User Story 1 fully functional. Zone detail page renders with all six metrics and three charts. Independently testable.

---

## Phase 4: User Story 2 — Cross-Country Zone Comparison (Priority: P1)

**Goal**: Add a comparison tool to the zone analytics page that lets users select up to 5 zones from any country and view a side-by-side table and overlay trend chart.

**Independent Test**: On `/en/zones/{id}`, open the comparison panel, search for and select 3 zones from 2 different countries. Verify the comparison table renders with all metrics for each zone in a single currency. Toggle a zone off in the overlay chart and verify its line disappears. Try to add a 6th zone and confirm it is blocked.

- [X] T023 Create `frontend/src/hooks/useZoneComparison.ts` — manages selected zone IDs (max 5) in component state; uses TanStack `useQueries` to fetch `GET /api/v1/zones/{id}/analytics` for each selected zone ID in parallel (reuses cached results); fetches `GET /api/v1/zones/compare?ids=...` for summary table data; returns `{ selectedIds, addZone, removeZone, comparisonData, analyticsMap, isLoading }`
- [X] T024 [P] [US2] Create `frontend/src/components/zones/ZoneComparisonTool.tsx` — `"use client"` component with: (1) multi-select combobox using shadcn `Command`+`Popover` that calls `searchZoneList` (existing hook) for autocomplete across all countries, enforces max-5 limit with toast on overflow; (2) side-by-side comparison table showing zone name, country, median price/m², volume, avg days on market, inventory, deal frequency — all monetary values converted via `convertFromEUR`; (3) overlay `LineChart` (Recharts) with one colored `Line` per selected zone sharing the same X-axis (months), each toggleable via legend click; accept `useZoneComparison` hook result as props
- [X] T025 [US2] Integrate `ZoneComparisonTool` into `frontend/src/components/zones/ZoneAnalyticsClient.tsx` — add a "Compare Zones" collapsible section below the histogram using shadcn `Collapsible`; wire `useZoneComparison` hook; pass currency rates and preferred currency to `ZoneComparisonTool`

**Checkpoint**: User Story 2 complete. Zone comparison tool works independently on any zone analytics page.

---

## Phase 5: User Story 3 — Portfolio Property Management Backend (Priority: P2)

**Goal**: Build the Go backend for portfolio CRUD — repository, handler, and route registration. This unblocks both US3 and US4 frontend work.

**Independent Test**: With a valid JWT, `POST /api/v1/portfolio/properties` with a valid body returns 201 with the created property including geocoded lat/lng. `GET /api/v1/portfolio/properties` returns the list. `PUT` updates and `DELETE` removes the property. A request for another user's property returns 403.

- [X] T026 Create `services/api-gateway/internal/repository/portfolio.go` — implement: `CreatePortfolioProperty(ctx, userID, req)` (inserts row, geocodes address via Nominatim in a goroutine after creation, updates lat/lng/zone_id asynchronously), `ListPortfolioProperties(ctx, userID) ([]PortfolioProperty, PortfolioSummary, error)` (left-joins ML estimate via `model_versions` for summary), `UpdatePortfolioProperty(ctx, userID, propertyID, req)`, `DeletePortfolioProperty(ctx, userID, propertyID) error`; `PortfolioSummary` is computed in SQL using `SUM`, `AVG` aggregates
- [X] T027 Create `services/api-gateway/internal/handler/portfolio.go` — `PortfolioHandler` struct with pgxpool and MLHandler ref; implement `List(w,r)` → `GET /portfolio/properties`, `Create(w,r)` → `POST`, `Update(w,r)` → `PUT /{id}`, `Delete(w,r)` → `DELETE /{id}`; validate request body with Zod-equivalent Go struct tags + manual checks (purchase_date not future, price > 0); ownership check in Update/Delete returns 403 on mismatch
- [X] T028 Wire portfolio handler in `services/api-gateway/cmd/main.go` (instantiate `PortfolioHandler`) and mount routes in `services/api-gateway/cmd/routes.go` under the authenticated group: `r.Route("/portfolio", func(r chi.Router) { r.Get("/properties", ph.List); r.Post("/properties", ph.Create); r.Put("/properties/{id}", ph.Update); r.Delete("/properties/{id}", ph.Delete) })`

**Checkpoint**: Portfolio backend complete and testable via curl/Postman independently of frontend.

---

## Phase 6: User Story 3 — Portfolio Property Management Frontend (Priority: P2)

**Goal**: Build the property CRUD UI components: form dialog for add/edit and the property table with edit/delete actions.

**Independent Test**: On `/en/portfolio`, click "Add Property", fill in all fields with valid data, submit — property appears in the list. Click edit, change rental income, save — list updates. Click delete and confirm — property removed. Submit with a future purchase date — inline validation error appears.

- [X] T029 Create `frontend/src/hooks/usePortfolio.ts` — TanStack Query hooks: `usePortfolioList()` (fetches `GET /api/v1/portfolio/properties`, returns `{ properties, summary, isLoading, error }`), `useCreateProperty()` mutation, `useUpdateProperty()` mutation, `useDeleteProperty()` mutation; all mutations invalidate `["portfolio"]` query key on success; optimistic delete marks row as pending
- [X] T030 [P] [US3] Create `frontend/src/components/portfolio/PropertyFormDialog.tsx` — shadcn `Dialog` with `react-hook-form` + Zod schema matching `CreatePortfolioPropertyRequest`; fields: address (text input), country (Select from `useCountries()`), purchase_price (number), purchase_currency (Select from `SUPPORTED_CURRENCIES`), purchase_date (date input, max today), monthly_rental_income (number, default 0), area_m2 (optional number), property_type (Select: residential/commercial/industrial/land), notes (optional Textarea); submit calls `useCreateProperty` or `useUpdateProperty` depending on whether `initialValues` prop is provided; shows field-level Zod errors inline
- [X] T031 [US3] Create `frontend/src/components/portfolio/PortfolioPropertyTable.tsx` — shadcn `Table` with columns: address, country, purchase price (converted to preferred currency), purchase date, monthly rental income (converted), estimated value (formatted or "Not available"), gain/loss (colored green/red), yield %; action column with Edit (opens `PropertyFormDialog` pre-filled) and Delete (shadcn `AlertDialog` confirmation) buttons; show skeleton rows while loading; show empty state with "Add Property" CTA when list is empty

**Checkpoint**: Portfolio property CRUD fully functional in the UI. Independently testable end-to-end.

---

## Phase 7: User Story 4 — Portfolio Dashboard & ROI Metrics (Priority: P2)

**Goal**: Compose the portfolio page with summary cards showing aggregated investment metrics in the user's preferred currency.

**Independent Test**: With 3 properties in different currencies in the portfolio, navigate to `/en/portfolio`. Summary cards show total invested (sum, converted to preferred currency), total current value (sum of ML estimates where available), unrealized gain/loss (absolute + %), average rental yield %. With no properties, summary cards show zeros and an "Add Property" CTA.

- [X] T032 [US4] Create `frontend/src/components/portfolio/PortfolioSummaryCards.tsx` — four shadcn `Card` components: (1) Total Invested (sum of `purchase_price_eur` converted to preferred currency), (2) Current Value (sum of `estimated_value_eur` where not null, converted), (3) Unrealized Gain/Loss (colored badge showing absolute value + percentage), (4) Avg Rental Yield % ; accept `summary: PortfolioSummary`, `rates`, `preferredCurrency` as props; show skeleton when `isLoading`; footnote showing count of properties with/without ML estimate
- [X] T033 Create `frontend/src/components/portfolio/PortfolioClient.tsx` — `"use client"` top-level component; composes `PortfolioSummaryCards` + `PortfolioPropertyTable` + floating "Add Property" button (opens `PropertyFormDialog`); calls `usePortfolio`, `useExchangeRates`; reads preferred currency from session (`session.user.preferredCurrency ?? "EUR"`)
- [X] T034 [US4] Replace stub at `frontend/src/app/[locale]/(protected)/portfolio/page.tsx` — async server component; calls `requireSession(locale)` for auth; renders `<Suspense fallback={<LoadingSkeleton rows={5} />}><PortfolioClient /></Suspense>`; add `generateMetadata` returning portfolio page title from i18n; add sibling `loading.tsx`

**Checkpoint**: Portfolio page fully functional with CRUD + summary metrics + currency conversion. US3 and US4 both testable independently.

---

## Phase 8: User Story 5 — Admin Scraping & ML Monitoring (Priority: P3)

**Goal**: Build the backend and frontend for admin Scraping Health and ML Models tabs, including the manual retrain trigger.

**Independent Test**: Log in as `admin@estategap.com`, navigate to `/en/admin`. Scraping Health tab shows a table with portal rows grouped by country, each with status badge, last scrape time, and 24h listing count. ML Models tab shows a table with MAPE/MAE/R² per country and a "Retrain Now" button. Click Retrain for one country — button shows loading state then "Queued" confirmation with a job ID. A non-admin user navigating to `/en/admin` is redirected to dashboard.

- [X] T035 Create `services/api-gateway/internal/repository/admin.go` — implement: `GetScrapingStats(ctx) ([]ScrapingPortalStat, error)` (reads Redis heartbeat keys `scraper:health:*` for current status, queries `listings` table for 24h counts grouped by portal and country); `GetMLModels(ctx) ([]MLModelVersion, error)` (queries `model_versions` table ordered by `trained_at DESC`); `IsRetrainingInProgress(ctx, country string) (bool, error)` (checks Redis key `ml:retrain:in_progress:{country}`)
- [X] T036 Create `services/api-gateway/internal/handler/admin.go` — `AdminHandler` struct with repo, NATS conn, Redis; implement `ScrapingStats(w,r)` → `GET /admin/scraping/stats`; `MLModels(w,r)` → `GET /admin/ml/models`; `TriggerRetrain(w,r)` → `POST /admin/ml/retrain` — checks `IsRetrainingInProgress`, returns 409 if true; publishes NATS JetStream message to subject `ml.retrain.requested` with payload `{country, requested_by, job_id}`, sets Redis key `ml:retrain:in_progress:{country}` with 2-hour TTL; responds 202 `{job_id, status: "queued"}`
- [X] T037 Mount admin routes in `services/api-gateway/cmd/routes.go` under a new authenticated + admin-only group: `r.Group(func(r chi.Router) { r.Use(mw.RequireAdmin); r.Get("/admin/scraping/stats", ah.ScrapingStats); r.Get("/admin/ml/models", ah.MLModels); r.Post("/admin/ml/retrain", ah.TriggerRetrain) })`; wire `AdminHandler` in `services/api-gateway/cmd/main.go`
- [X] T038 [P] [US5] Add admin API client functions to `frontend/src/lib/api.ts`: `fetchAdminScrapingStats(accessToken)`, `fetchAdminMLModels(accessToken)`, `triggerMLRetrain(accessToken, country)` — follow existing typed client pattern
- [X] T039 [P] [US5] Create `frontend/src/hooks/useAdminScraping.ts` — TanStack Query hook fetching `fetchAdminScrapingStats`; refetch interval 30 seconds; returns `{ portals, isLoading, error }`
- [X] T040 [P] [US5] Create `frontend/src/hooks/useAdminML.ts` — `useAdminMLModels()` query (refetch 60s) + `useRetrainMutation()` mutation that calls `triggerMLRetrain` and shows toast on success/error
- [X] T041 [P] [US5] Create `frontend/src/components/admin/ScrapingHealthTab.tsx` — shadcn `Table` grouped by country; columns: portal name, status (Badge: green=active, red=error, yellow=paused), last scrape time (relative), 24h listings, success rate (%), blocks 24h; auto-refreshes via `useAdminScraping` 30s interval; shows loading skeleton and error state
- [X] T042 [P] [US5] Create `frontend/src/components/admin/MLModelsTab.tsx` — shadcn `Table` showing model versions per country; columns: country, version, MAPE (%), MAE, R², trained at, active badge; "Retrain Now" button per row — disabled with "Training…" label when `train_status === "training"`; click calls `useRetrainMutation`; shows shadcn `Alert` with job_id on success

**Checkpoint**: Admin Scraping and ML tabs functional. Retrain trigger works. Admin guard tested.

---

## Phase 9: User Story 6 — Admin Users, Countries & System (Priority: P3)

**Goal**: Complete the admin panel with Users, Countries, and System Health tabs.

**Independent Test**: On `/en/admin`, switch to Users tab and verify paginated user list loads with search working. Switch to Countries tab and toggle a country off — confirm the change persists after page reload. Switch to System tab and verify NATS queue depths, DB size, and Redis memory metrics display.

- [X] T043 Extend `services/api-gateway/internal/repository/admin.go` — add: `ListUsers(ctx, page, limit, q, tier string) ([]AdminUser, int, error)` (queries `users` table with ILIKE search on email/name, tier filter, pagination); `GetCountries(ctx) ([]CountryConfig, error)` (queries countries table joined with portals); `UpdateCountry(ctx, code string, enabled bool, portals []PortalConfig) (CountryConfig, error)`; `GetSystemHealth(ctx) (SystemHealth, error)` (queries NATS monitoring HTTP endpoint, `pg_stat_activity`, Redis INFO)
- [X] T044 Extend `services/api-gateway/internal/handler/admin.go` — add: `ListUsers(w,r)`, `ListCountries(w,r)`, `UpdateCountry(w,r)`, `SystemHealth(w,r)`; mount in `services/api-gateway/cmd/routes.go` under the existing `RequireAdmin` group: `r.Get("/admin/users", ah.ListUsers); r.Get("/admin/countries", ah.ListCountries); r.Put("/admin/countries/{code}", ah.UpdateCountry); r.Get("/admin/system/health", ah.SystemHealth)`
- [X] T045 [P] [US6] Add remaining admin API functions to `frontend/src/lib/api.ts`: `fetchAdminUsers(accessToken, params)`, `fetchAdminCountries(accessToken)`, `updateAdminCountry(accessToken, code, body)`, `fetchSystemHealth(accessToken)`
- [X] T046 [P] [US6] Create `frontend/src/hooks/useAdminUsers.ts` — paginated query with search `q` and `tier` filter params; returns `{ users, total, page, setPage, setQuery, setTier, isLoading }`
- [X] T047 [P] [US6] Create `frontend/src/hooks/useAdminCountries.ts` — list query + `useUpdateCountryMutation` that invalidates country list on success
- [X] T048 [P] [US6] Create `frontend/src/hooks/useAdminSystem.ts` — query with 15-second refetch interval; returns `{ health, isLoading, error }`
- [X] T049 [P] [US6] Create `frontend/src/components/admin/UsersTab.tsx` — shadcn `Table` with search input (debounced 300ms) and tier Select filter; columns: email, name, role badge, tier badge, last active (relative time), created at; pagination controls using shadcn `Pagination`; rows are non-clickable (user detail is out of scope per spec edge case)
- [X] T050 [P] [US6] Create `frontend/src/components/admin/CountriesTab.tsx` — list of country cards each showing enabled/disabled `Switch` toggle (calls `useUpdateCountryMutation` on change with `AlertDialog` confirmation), list of portals with their enabled status; include a collapsed JSON editor (shadcn `Textarea`) per portal for config editing
- [X] T051 [P] [US6] Create `frontend/src/components/admin/SystemHealthTab.tsx` — three shadcn `Card` sections: NATS (table of subjects with consumer lag and message count), Database (connection pool gauge, size in GB), Redis (memory usage bar, hit rate %, connected clients); auto-refreshes every 15s via `useAdminSystem`; shows error per section independently so partial failures don't blank the whole tab
- [X] T052 Create `frontend/src/components/admin/AdminClient.tsx` — `"use client"` component with shadcn `Tabs` containing five `TabsContent` panels: Scraping Health, ML Models, Users, Countries, System; lazy-render tab content on first activation using `useState` mounted flag; reads session to confirm admin role client-side (belt-and-suspenders in addition to middleware guard)
- [X] T053 [US6] Replace stub at `frontend/src/app/[locale]/(protected)/admin/page.tsx` — async server component; calls `requireSession(locale)`, checks `session.user.role === "admin"` and calls `notFound()` otherwise; renders `<AdminClient />`; add `generateMetadata` with admin panel title; add sibling `loading.tsx`

**Checkpoint**: All six user stories complete. Full admin panel functional with all five tabs.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: i18n completeness, loading states, preferred currency setting, and final wiring.

- [X] T054 [P] Copy all new i18n keys added to `frontend/src/messages/en.json` (T002) to the remaining 9 locale files: `es.json`, `fr.json`, `it.json`, `de.json`, `pt.json`, `nl.json`, `pl.json`, `sv.json`, `el.json` — use English values as initial translations (next-intl falls back to default locale for missing keys, but having the keys prevents console warnings)
- [X] T055 [P] Add `PATCH /api/v1/auth/me` endpoint support for `preferred_currency` field in `services/api-gateway/internal/handler/auth.go` — validate currency code is in supported list; update `users.preferred_currency` column; expose `preferred_currency` in `GET /api/v1/auth/me` response; update `frontend/src/auth.ts` session callbacks to read and propagate `preferredCurrency` field
- [X] T056 [P] Add currency selector control to `frontend/src/components/layout/UserMenu.tsx` — shadcn `Select` showing current preferred currency; calls `PATCH /api/v1/auth/me { preferred_currency }` on change then triggers session update; list is sourced from `SUPPORTED_CURRENCIES` constant in `currency.ts`
- [X] T057 [P] Add `loading.tsx` Suspense boundary files for `/portfolio` and `/admin` routes (if not already created in T034/T053) — use `LoadingSkeleton` with appropriate row counts
- [ ] T058 Verify end-to-end: run `npm run build` inside `frontend/`, confirm no TypeScript errors; run `golangci-lint run ./...` inside `services/api-gateway/`, confirm no lint errors; manually test the golden path for each of the six user stories

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 (T003/T004 must complete before T009/T015) — **BLOCKS all user stories**
- **Phase 3 (US1)**: Depends on Phase 2 — no dependency on US2/US3/US4/US5/US6
- **Phase 4 (US2)**: Depends on Phase 3 (uses `ZoneAnalyticsClient`) — only story with a dependency on another story
- **Phase 5 (US3 backend)**: Depends on Phase 2 only — can run in parallel with Phase 3
- **Phase 6 (US3 frontend)**: Depends on Phase 5 (needs backend running) and Phase 2
- **Phase 7 (US4)**: Depends on Phase 6 (composes US3 components)
- **Phase 8 (US5)**: Depends on Phase 2 only — can run in parallel with Phases 3–7
- **Phase 9 (US6)**: Depends on Phase 8 (extends same admin handler/repo)
- **Phase 10 (Polish)**: Depends on all story phases complete

### User Story Dependencies

- **US1 (P1)**: Starts after Phase 2 — no story dependencies
- **US2 (P1)**: Starts after US1 complete (integrates into `ZoneAnalyticsClient`)
- **US3 (P2)**: Starts after Phase 2 — no story dependencies; backend (Phase 5) can parallel with US1
- **US4 (P2)**: Starts after US3 frontend (Phase 6) complete
- **US5 (P3)**: Starts after Phase 2 — can parallel with US1 and US3 backend
- **US6 (P3)**: Starts after US5 complete (extends same Go files)

### Within Each Phase

- Tasks marked `[P]` within the same phase have no inter-dependencies and can execute concurrently
- Backend (Go) tasks and frontend (TypeScript) tasks within a phase can always run in parallel
- Route mounting tasks (T028, T037, T044) must follow their corresponding handler/repo tasks

---

## Parallel Execution Examples

### Phase 2 Foundational — can run in parallel after T003/T004

```
T005  Extend JWT role claim (Go)
T006  RequireAdmin middleware (Go)        ← parallel with T005
T007  portfolio_properties migration      ← parallel with T005, T006
T008  users.preferred_currency migration  ← parallel with T007
T010  price-distribution endpoint         ← parallel with T009
T011  Exchange rate Route Handler (TS)    ← parallel with T005–T010
T012  currency.ts utility (TS)            ← parallel with T011
T013  useExchangeRates hook (TS)          ← parallel with T012
T015  api.ts new functions                ← parallel with T011–T013
```

### Phase 3 US1 Charts — can run in parallel after T016

```
T017  ZoneMetricsBar     ← parallel
T018  ZonePriceTrendChart ← parallel
T019  ZoneVolumeChart    ← parallel
T020  ZonePriceHistogram ← parallel
```

### Phase 8 US5 — backend then frontend in parallel

```
T035  admin repository (Go)
T036  admin handler (Go)       → T037 route mount
T038  admin api.ts functions   ← parallel with T035–T037
T039  useAdminScraping hook    ← parallel with T040
T040  useAdminML hook          ← parallel with T039
T041  ScrapingHealthTab        ← parallel with T042
T042  MLModelsTab              ← parallel with T041
```

---

## Implementation Strategy

### MVP First (US1 only — Zone Analytics Page)

1. Complete Phase 1: Setup (T001–T004)
2. Complete Phase 2: Foundational (T005–T015)
3. Complete Phase 3: US1 (T016–T022)
4. **STOP and VALIDATE**: Navigate to any zone detail page; all six metrics and three charts render correctly
5. Ship / demo zone analytics independently

### Incremental Delivery

1. Setup + Foundational → infrastructure ready
2. US1 (Zone Analytics) → test + demo → highest-value P1 delivered
3. US2 (Comparison) → test + demo → P1 complete
4. US3+US4 (Portfolio) → test + demo → P2 delivered
5. US5+US6 (Admin) → test + demo → P3 delivered
6. Polish → i18n complete, currency selector wired

### Parallel Team Strategy (3 developers)

After Phase 2 is complete:
- **Dev A**: US1 (Phase 3) → US2 (Phase 4)
- **Dev B**: US3 backend (Phase 5) → US3 frontend (Phase 6) → US4 (Phase 7)
- **Dev C**: US5 (Phase 8) → US6 (Phase 9)

All three streams converge at Phase 10 (Polish).

---

## Notes

- `[P]` tasks = different files, no blocking dependencies within the same phase
- `[USn]` label maps each task to a user story for traceability
- Each user story phase delivers an independently testable increment
- No test tasks included (not requested in spec); add with `TDD: true` flag if needed
- Commit after each phase checkpoint or logical task group
- Run `golangci-lint` after each Go file addition
- Run `npm run type-check` after each TypeScript file addition
- T009 extends `services/api-gateway/internal/repository/zones.go` and `handler/zones.go` — coordinate with T009 if doing T005 in the same session to avoid merge conflicts on those files
