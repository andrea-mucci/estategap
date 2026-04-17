# Tasks: Listing & Zone Data Endpoints

**Input**: Design documents from `specs/007-listing-zone-endpoints/`  
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unresolved dependencies)
- **[Story]**: Which user story this task belongs to (US1–US6)
- All paths are relative to the repo root

---

## Phase 1: Setup (Prerequisite Verification)

**Purpose**: Confirm all prerequisites from research.md before writing any code. Unblocks all subsequent phases.

- [X] T001 Verify `zone_statistics` materialized view exists in PostgreSQL by running `\dv zone_statistics` — if absent, create an Alembic migration in `services/pipeline/` (or the active migrations path) that creates the view and its unique index on `zone_id`
- [X] T002 Verify `listings.location` GIST spatial index exists by running `\d listings` — if absent, add a migration that creates `CREATE INDEX CONCURRENTLY ON listings USING GIST (location)`
- [X] T003 Check `libs/pkg/models/user.go` for `AllowedCountries []string` field on `User` struct — if absent, add the field with db tag `db:"allowed_countries"` and create a migration adding the `allowed_countries text[] DEFAULT '{}'` column to the `users` table

**Checkpoint**: All three prerequisites confirmed or migrations created and applied.

---

## Phase 2: Foundational (Shared Infrastructure)

**Purpose**: Core infrastructure used by multiple user stories. Must be complete before Phase 3+.

**⚠️ CRITICAL**: No user story implementation can begin until this phase is complete.

- [X] T004 [P] Add `encodeFloatCursor(val float64, id uuid.UUID) string` and `decodeFloatCursor(cursor string) (float64, uuid.UUID, error)` to `services/api-gateway/internal/repository/helpers.go` — encode as `base64url("{float64_bits_hex}|{uuid_string}")` using `math.Float64bits`
- [X] T005 [P] Add `listEnvelope(data any, nextCursor string, hasMore bool, totalCount int64, currency string) map[string]any` helper to `services/api-gateway/internal/handler/common.go` that returns the standard `{data, pagination:{next_cursor, has_more}, meta:{total_count, currency}}` envelope
- [X] T006 Create `services/api-gateway/internal/cache/cache.go` with a `Client` struct wrapping `*redis.Client` and a generic `GetOrSet[T any](ctx, key, ttl, fn) (T, error)` method: attempt JSON GET → on miss call fn(), JSON-marshal result, SET with TTL, return value
- [X] T007 Update `services/api-gateway/cmd/main.go` to instantiate `cache.NewClient(redisClient)` after the Redis client is created and assign it to `cacheClient`; update `NewZonesRepo` and (later) `NewReferenceRepo` signatures to accept `*cache.Client` — placeholder wiring only at this stage, full wiring happens per-story

**Checkpoint**: Helpers and cache client compile and are importable by repository and handler packages.

---

## Phase 3: User Story 1 — Find Investment Opportunities (Priority: P1) 🎯 MVP

**Goal**: Deliver a fully featured listing search: 20+ filters, multi-sort, cursor pagination, currency conversion, and subscription tier gating.

**Independent Test**: `GET /v1/listings?country=ES&deal_tier=1&sort_by=deal_score&currency=USD` returns results sorted by deal_score DESC, prices converted to USD, `X-Currency: USD` header present, and free-tier users receive only listings older than 48 hours.

- [X] T008 [P] [US1] Extend `ListingFilter` struct in `services/api-gateway/internal/repository/listings.go` with 8 new fields: `ZoneID *uuid.UUID`, `PropertyType string`, `MinBedrooms *int`, `MinBathrooms *int`, `PortalID *uuid.UUID`, `MinDaysOnMarket *int`, `MaxDaysOnMarket *int`, `SortBy string`, `SortDir string`, `Currency string`, `FreeTierGate bool`, `AllowedCountries []string`
- [X] T009 [US1] Rewrite `SearchListings()` in `services/api-gateway/internal/repository/listings.go`:
  - Add new filter conditions for the 8 new `ListingFilter` fields
  - Add validated dynamic `ORDER BY` using an allowlist map (`recency`→`first_seen_at`, `deal_score`→`deal_score`, `price`→`asking_price_eur`, `price_m2`→`price_per_m2_eur`, `days_on_market`→`days_on_market`)
  - Add composite cursor condition using `decodeFloatCursor` for non-recency sorts and existing `decodeTimeCursor` for recency
  - Add LEFT JOIN on `exchange_rates` (latest rate for `filter.Currency`) and a `price_converted` computed column when currency ≠ EUR
  - Add `AND first_seen_at < NOW() - INTERVAL '48 hours'` when `FreeTierGate` is true
  - Add `AND country = ANY($N)` when `AllowedCountries` is non-empty
  - Run a second `SELECT COUNT(*)` with the same WHERE (no cursor, no LIMIT) using `context.WithTimeout(ctx, 200ms)`; return count alongside results
  - Return the exchange rate date string alongside results for the `X-Exchange-Rate-Date` header
  - Change return signature to `([]models.Listing, string, int64, string, error)` — items, nextCursor, totalCount, rateDateStr, err
- [X] T010 [P] [US1] Add new parse helpers to `services/api-gateway/internal/handler/common.go`: `parseOptionalInt(raw string) (*int, error)`, `parseSortBy(raw string) (string, error)`, `parseSortDir(raw string) string`, `parseUUID(raw string) (*uuid.UUID, error)`
- [X] T011 [US1] Update `ListingsHandler` in `services/api-gateway/internal/handler/listings.go`:
  - Add `usersRepo` field to the struct; update `NewListingsHandler` constructor to accept it
  - Rewrite `buildListingFilter()` to parse all new query params (zone_id, property_type, min_bedrooms, min_bathrooms, portal_id, min/max_days_on_market, sort_by, sort_dir, currency)
  - Rewrite `List()`: read tier from `ctxkey.UserTier`; for `free` set `FreeTierGate=true`; for `basic` fetch user by ID from `usersRepo` and set `AllowedCountries`; set `X-Currency` and `X-Exchange-Rate-Date` response headers; return `listEnvelope` with `listingSummaryPayload` items
  - Add `listingSummaryPayload` (fields: id, source, country, city, address, asking_price, asking_price_eur, price_converted, currency, price_per_m2_eur, area_m2, bedrooms, bathrooms, property_category, property_type, deal_score, deal_tier, status, days_on_market, photo_url, first_seen_at) to `handler/common.go`
  - Add `listingSummaryFromModel(item *models.Listing, convertedPrice *decimal.Decimal, currency string) listingSummaryPayload` conversion helper to `handler/common.go`
- [X] T012 [US1] Update `services/api-gateway/cmd/main.go`: pass `usersRepo` to `handler.NewListingsHandler`; update `NewListingsRepo` signature if needed (no cache for listings)

**Checkpoint**: Listing search is fully functional — all filters, sorts, currency, gating, and new envelope work correctly.

---

## Phase 4: User Story 2 — Research a Specific Property (Priority: P1)

**Goal**: Listing detail returns all property fields, price history, SHAP top-5, comparable IDs, and zone stats summary.

**Independent Test**: `GET /v1/listings/{id}` returns a response containing non-empty `price_history` array, `shap_features` array with up to 5 items, `comparable_ids` array, and a `zone_stats` object — or empty/null equivalents for listings without score or zone.

- [X] T013 [P] [US2] Add `listingDetailPayload`, `priceHistoryItem`, `zoneSummaryStats` types to `services/api-gateway/internal/handler/common.go` per data-model.md; add `listingDetailFromResult(r *repository.ListingDetail, ...) listingDetailPayload` conversion helper
- [X] T014 [US2] Add `ListingDetail` and `ZoneStats` structs to `services/api-gateway/internal/repository/listings.go`; implement `GetListingDetail(ctx, id uuid.UUID) (*ListingDetail, error)` that:
  - Fetches the listing by ID (reuse existing SELECT)
  - Fetches `price_history` with `SELECT * FROM price_history WHERE listing_id=$1 ORDER BY recorded_at ASC`
  - Fetches comparables: `SELECT id FROM listings WHERE zone_id=$zone_id AND property_category=$cat AND asking_price_eur BETWEEN $price*0.8 AND $price*1.2 AND id!=$id AND status='active' LIMIT 5` (skip if listing has no zone_id or price)
  - Fetches zone stats from `zone_statistics` WHERE `zone_id=$zone_id` joined with `zones` for name (skip if no zone_id)
  - Runs price_history, comparables, and zone_stats queries concurrently via `errgroup.WithContext`
- [X] T015 [US2] Rewrite `ListingsHandler.Get()` in `services/api-gateway/internal/handler/listings.go` to call `GetListingDetail` and return `listingDetailPayload` (direct object, no envelope wrapper)

**Checkpoint**: Listing detail endpoint returns full nested data; empty arrays (not null) for listings with no price history or comparables.

---

## Phase 5: User Story 3 — Analyse a Market Zone (Priority: P2)

**Goal**: Zone list returns stats per zone; zone detail includes full statistics; zone analytics returns exactly 12 monthly data points.

**Independent Test**: `GET /v1/zones?country=ES&level=4` returns zones with `listing_count` and `median_price_m2_eur` populated. `GET /v1/zones/{id}/analytics` returns exactly 12 items in the `months` array regardless of listing activity gaps.

- [X] T016 [P] [US3] Add `zoneDetailPayload`, `zoneMonthlyStatPayload`, `zoneAnalyticsResponse` types to `services/api-gateway/internal/handler/common.go`; add `zoneDetailFromModel` and `zoneAnalyticsFromMonths` helpers
- [X] T017 [P] [US3] Extend `ListZones()` in `services/api-gateway/internal/repository/zones.go`:
  - Add `level *int` and `parentID *uuid.UUID` filter parameters
  - Add `LEFT JOIN zone_statistics zs ON zs.zone_id = z.id` to the query
  - Return enriched struct `ZoneWithStats` (Zone + stats fields: listing_count, median_price_m2_eur, deal_count, price_trend_pct) instead of plain `models.Zone`
  - Add `ZoneWithStats` struct to `services/api-gateway/internal/repository/zones.go`
- [X] T018 [US3] Update `GetZoneByID()` in `services/api-gateway/internal/repository/zones.go` to JOIN `zone_statistics` and return `ZoneWithStats`
- [X] T019 [US3] Rewrite `GetZoneAnalytics()` in `services/api-gateway/internal/repository/zones.go` to use the `generate_series` + `date_trunc('month', ...)` query from research.md; return `[]ZoneMonthStat` (always exactly 12 elements, zero-filled); add `ZoneMonthStat` struct; wrap with Redis cache via `c.GetOrSet` (key: `cache:zone_analytics:{zone_id}`, TTL: 5min)
- [X] T020 [US3] Update `ZonesRepo` constructor in `services/api-gateway/internal/repository/zones.go` to accept `*cache.Client`; add cache calls to `GetZoneByID` (key: `cache:zone:{id}`, TTL: 5min) and `GetZoneAnalytics`
- [X] T021 [US3] Update `ZonesHandler.List()` in `services/api-gateway/internal/handler/zones.go` to accept `level` and `parent_id` query params, pass them to the updated `ListZones`, and return `listEnvelope` with `zoneDetailPayload` items
- [X] T022 [US3] Update `ZonesHandler.Get()` in `services/api-gateway/internal/handler/zones.go` to return `zoneDetailPayload` (direct object with full stats)
- [X] T023 [US3] Rewrite `ZonesHandler.Analytics()` in `services/api-gateway/internal/handler/zones.go` to return `zoneAnalyticsResponse{ZoneID, Months[12]}` — remove `period_days` param; return 400 if zone not found
- [X] T024 [US3] Update `services/api-gateway/cmd/main.go` to pass `cacheClient` to `repository.NewZonesRepo`

**Checkpoint**: Zone list, detail, and analytics all return stats-enriched responses; analytics always has exactly 12 months.

---

## Phase 6: User Story 4 — Compare Zones Side by Side (Priority: P2)

**Goal**: `GET /v1/zones/compare?ids=a,b,c` returns side-by-side zone stats with EUR-normalised prices, supporting cross-country zones.

**Independent Test**: Calling the compare endpoint with 2 zone UUIDs from different countries returns both zones with `median_price_m2_eur` populated and `local_currency` set to each zone's home currency. Passing 6 IDs returns HTTP 400.

- [X] T025 [P] [US4] Add `zoneComparePayload` and `zoneCompareItem` types to `services/api-gateway/internal/handler/common.go`; add `zoneCompareFromItems` helper
- [X] T026 [US4] Add `CompareZones(ctx, ids []uuid.UUID) ([]ZoneCompareItem, error)` to `services/api-gateway/internal/repository/zones.go`:
  - Validate `2 <= len(ids) <= 5`; return error otherwise
  - Query: `SELECT z.*, zs.listing_count, zs.median_price_m2_eur, zs.deal_count, zs.price_trend_pct, c.currency AS local_currency FROM zones z LEFT JOIN zone_statistics zs ON zs.zone_id=z.id LEFT JOIN countries c ON c.code=z.country_code WHERE z.id = ANY($1)`
  - Add `ZoneCompareItem` struct (ZoneWithStats + LocalCurrency string)
  - Wrap with Redis cache (key: `cache:zone_compare:{sorted_ids_hash}`, TTL: 2min)
- [X] T027 [US4] Add `ZonesHandler.Compare()` to `services/api-gateway/internal/handler/zones.go`:
  - Parse `ids` query param as comma-separated UUIDs
  - Validate count (2–5); return 400 otherwise
  - Call `repo.CompareZones`; return `zoneComparePayload`
- [X] T028 [US4] Register `GET /v1/zones/compare` in `services/api-gateway/cmd/main.go` **before** `GET /v1/zones/{id}` to prevent chi routing conflict

**Checkpoint**: Zone compare returns correct multi-zone response; passing <2 or >5 IDs returns 400.

---

## Phase 7: User Story 5 — Discover Available Markets (Priority: P3)

**Goal**: `GET /v1/countries` returns all active countries with listing count, deal count, and portal count.

**Independent Test**: `GET /v1/countries` returns a JSON array where each entry has `code`, `name`, `currency`, `listing_count`, `deal_count`, and `portal_count`; only active countries appear.

- [X] T029 [P] [US5] Add `countryPayload` type to `services/api-gateway/internal/handler/common.go`; add `countryFromSummary` helper
- [X] T030 [US5] Create `services/api-gateway/internal/repository/reference.go` with:
  - `ReferenceRepo` struct holding `replica *pgxpool.Pool` and `cache *cache.Client`
  - `CountrySummary` struct (Code, Name, Currency, ListingCount, DealCount, PortalCount)
  - `NewReferenceRepo(replica *pgxpool.Pool, cache *cache.Client) *ReferenceRepo`
  - `ListCountries(ctx) ([]CountrySummary, error)`: query joining `countries`, `listings`, `portals` as described in plan.md; wrap with Redis cache (key: `cache:countries`, TTL: 15min)
- [X] T031 [US5] Create `services/api-gateway/internal/handler/reference.go` with:
  - `ReferenceHandler` struct
  - `NewReferenceHandler(repo *repository.ReferenceRepo) *ReferenceHandler`
  - `Countries(w, r)`: call `repo.ListCountries`; return `listEnvelope` (no pagination cursor, full result set) with `countryPayload` items
- [X] T032 [US5] Update `services/api-gateway/cmd/main.go`: instantiate `referenceRepo := repository.NewReferenceRepo(replicaPool, cacheClient)`; instantiate `referenceHandler := handler.NewReferenceHandler(referenceRepo)`; register `r.Get("/countries", referenceHandler.Countries)`

**Checkpoint**: `GET /v1/countries` returns active countries with accurate stats; response is cached for 15 minutes.

---

## Phase 8: User Story 6 — Monitor Data Source Health (Priority: P3)

**Goal**: `GET /v1/portals` returns all active portals with their country, enabled status, and last scrape timestamp.

**Independent Test**: `GET /v1/portals` returns a JSON array where each entry has `id`, `name`, `country`, `base_url`, `enabled: true`, and `last_scrape_at` (may be null); no disabled portals appear.

- [X] T033 [P] [US6] Add `portalPayload` type to `services/api-gateway/internal/handler/common.go`; add `portalFromModel` conversion helper that reads `last_scrape_at` from `portal.Config` JSONB (key `"last_scrape_at"`) with graceful fallback to null if absent
- [X] T034 [US6] Add `ListPortals(ctx) ([]models.Portal, error)` to `services/api-gateway/internal/repository/reference.go`: `SELECT * FROM portals WHERE enabled = true ORDER BY name ASC`; wrap with Redis cache (key: `cache:portals`, TTL: 15min)
- [X] T035 [US6] Add `Portals(w, r)` method to `services/api-gateway/internal/handler/reference.go`: call `repo.ListPortals`; return `listEnvelope` (no cursor) with `portalPayload` items
- [X] T036 [US6] Register `r.Get("/portals", referenceHandler.Portals)` in `services/api-gateway/cmd/main.go`

**Checkpoint**: `GET /v1/portals` returns active portals; `last_scrape_at` is null (not an error) when not set by the orchestrator.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Correctness hardening and lint compliance across all changes.

- [ ] T037 [P] Run `golangci-lint run ./...` from `services/api-gateway/` and fix all reported issues
- [X] T038 Audit all 8 endpoint handlers in `services/api-gateway/internal/handler/` to confirm every error path calls `writeError()` (never `respond.JSON` with an error status) and every success response uses the correct envelope shape per contracts/api.md
- [X] T039 Verify route registration order in `services/api-gateway/cmd/main.go`: `GET /zones/compare` must appear before `GET /zones/{id}` and `GET /zones/{id}/analytics`; confirm with `curl` or an `httptest` router inspection that `compare` is not swallowed by `{id}`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately; unblocks all subsequent phases
- **Phase 2 (Foundational)**: Depends on Phase 1 completion — **blocks all user story phases**
- **Phase 3 (US1)**: Depends on Phase 2 — can start once T004–T007 are complete
- **Phase 4 (US2)**: Depends on Phase 2 — can start in parallel with Phase 3 (different files)
- **Phase 5 (US3)**: Depends on Phase 2 (needs cache.Client from T006/T007)
- **Phase 6 (US4)**: Depends on Phase 5 (CompareZones reuses ZoneWithStats)
- **Phase 7 (US5)**: Depends on Phase 2 — independent of Phase 3–6
- **Phase 8 (US6)**: Depends on Phase 7 (adds to same ReferenceRepo and ReferenceHandler)
- **Phase 9 (Polish)**: Depends on all user story phases

### User Story Dependencies

- **US1 (P1)**: After Phase 2 — no story dependencies
- **US2 (P1)**: After Phase 2 — no story dependencies (different functions in listings.go)
- **US3 (P2)**: After Phase 2 — no story dependencies
- **US4 (P2)**: After Phase 5 (US3) — reuses `ZoneWithStats` struct
- **US5 (P3)**: After Phase 2 — no story dependencies
- **US6 (P3)**: After Phase 7 (US5) — adds to ReferenceRepo and ReferenceHandler created in US5

### Within Each Story

- New types in `common.go` → handler changes (can be written together since they're in the same file)
- Repository changes → handler changes → `main.go` wiring
- Commit after each phase checkpoint

### Parallel Opportunities

Within Phase 2: T004, T005, T006 can run in parallel (different files); T007 depends on T006.

Within Phase 3: T008 and T010 can start in parallel (different concerns in listings.go and common.go); T009 depends on T008; T011 depends on T009 and T010.

Within Phase 5: T016, T017, T018 can run in parallel; T019 depends on T016 (ZoneMonthStat struct); T020 depends on T019; T021-T023 depend on T017-T019.

Within Phase 7 and 8: T029 and T030 can run in parallel; T031 depends on T030; T033 and T034 can run in parallel.

---

## Parallel Example: Phase 2

```text
In parallel:
  T004 — add encodeFloatCursor/decodeFloatCursor to repository/helpers.go
  T005 — add listEnvelope helper to handler/common.go
  T006 — create cache/cache.go

Then sequentially:
  T007 — update cmd/main.go to wire cacheClient
```

## Parallel Example: User Story 3

```text
In parallel:
  T016 — add zoneDetailPayload types to common.go
  T017 — extend ListZones() in repository/zones.go
  T018 — update GetZoneByID() in repository/zones.go

Then sequentially (T019 needs ZoneMonthStat type in place):
  T019 — rewrite GetZoneAnalytics() in repository/zones.go
  T020 — update ZonesRepo constructor with cache
  T021–T023 — update handler/zones.go methods
  T024 — update cmd/main.go
```

---

## Implementation Strategy

### MVP First (User Stories 1 + 2 Only)

1. Complete Phase 1: Setup (prerequisites)
2. Complete Phase 2: Foundational (helpers, cache, wiring)
3. Complete Phase 3: US1 — listing search
4. Complete Phase 4: US2 — listing detail
5. **STOP and VALIDATE**: Both listing endpoints fully functional with gating, currency, and detail data
6. Deploy/demo if ready

### Incremental Delivery

1. Phase 1 + 2 → Foundation ready
2. Phase 3 → Listing search live (MVP!)
3. Phase 4 → Listing detail enhanced
4. Phase 5 → Zone list/detail/analytics upgraded
5. Phase 6 → Zone compare added
6. Phase 7 → Countries endpoint live
7. Phase 8 → Portals endpoint live
8. Phase 9 → Lint and audit pass

### Parallel Team Strategy

With two developers after Phase 2 is complete:
- **Dev A**: Phase 3 (US1) → Phase 4 (US2) → Phase 9
- **Dev B**: Phase 5 (US3) → Phase 6 (US4) → Phase 7 (US5) → Phase 8 (US6)

---

## Notes

- `[P]` tasks touch different files and have no incomplete-task dependencies — safe to run concurrently
- `[Story]` label enables tracing any task back to its acceptance criteria in spec.md
- All repository functions must use `r.replica` pool — never the primary pool
- The `sort_by` allowlist in `SearchListings` must be validated before string interpolation into SQL (not parameterised) to prevent SQL injection
- `GET /v1/zones/compare` route **must** be registered before `GET /v1/zones/{id}` in chi — static paths take precedence only when registered first
- `last_scrape_at` for portals lives in the `config` JSONB column (populated by the orchestrator) — parse with a fallback to null, not a hard error
- Response envelope change (`{items,cursor}` → `{data,pagination,meta}`) is intentionally breaking — pre-GA API, no shim needed
