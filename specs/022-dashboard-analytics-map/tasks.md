# Tasks: Dashboard Analytics & Interactive Map

**Input**: Design documents from `specs/022-dashboard-analytics-map/`
**Prerequisites**: plan.md ✅ spec.md ✅ research.md ✅ data-model.md ✅ contracts/ ✅ quickstart.md ✅

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared dependencies)
- **[Story]**: User story this task serves (US1–US6)
- All paths are relative to repository root `/root/projects/estategap/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Install packages and scaffold new files before any story work begins.

- [X] T001 Install recharts and mapbox-gl-draw packages: `cd frontend && npm install recharts @mapbox/mapbox-gl-draw @types/mapbox__mapbox-gl-draw`
- [X] T002 [P] Create frontend dashboard component directory and empty index barrel: `frontend/src/components/dashboard/`
- [X] T003 [P] Create frontend map component directory and empty index barrel: `frontend/src/components/map/`
- [X] T004 [P] Create empty backend dashboard handler file: `services/api-gateway/internal/handler/dashboard.go` (package declaration + imports only)
- [X] T005 [P] Create empty backend dashboard repository file: `services/api-gateway/internal/repository/dashboard.go` (package declaration + imports only)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: OpenAPI schema updates, coordinate extraction, TypeScript type regen, and base Zustand store. **All user stories depend on this phase.**

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T006 Add `latitude` and `longitude` nullable float fields to `ListingSummary` struct in `services/api-gateway/internal/repository/listings.go` and extract them via `ST_Y(location) AS latitude, ST_X(location) AS longitude` in the SearchListings SQL query
- [X] T007 Update `services/api-gateway/internal/handler/listings.go` to include `Latitude` and `Longitude` in the JSON response mapping for ListingSummary
- [X] T008 Add all new schemas and endpoints to `services/api-gateway/openapi.yaml`: `DashboardSummary`, `ListingsGeoJSON`, `ListingGeoFeature`, `ZoneGeometry`, `CreateCustomZoneRequest`; add `latitude`/`longitude` to `ListingSummary`; add `GET /api/v1/dashboard/summary`, `GET /api/v1/zones/{id}/geometry`, `POST /api/v1/zones`, `bounds` + `format` params to `GET /api/v1/listings` (full contract in `specs/022-dashboard-analytics-map/contracts/api-extensions.yaml`)
- [X] T009 Regenerate frontend TypeScript types after T008: `cd frontend && npm run generate-api-types` — verify `DashboardSummary`, `ListingGeoFeature`, `ZoneGeometry`, `CreateCustomZoneRequest`, `latitude`/`longitude` on `ListingSummary` appear in `frontend/src/types/api.ts`
- [X] T010 Create Zustand `dashboardStore` in `frontend/src/stores/dashboardStore.ts` with state fields `selectedCountry: string`, `mapMode: "markers" | "heatmap"`, `showZoneOverlay: boolean`, `drawingMode: boolean` and actions `setCountry`, `setMapMode`, `toggleZoneOverlay`, `setDrawingMode`
- [X] T011 [P] Create `useCountries` TanStack Query hook in `frontend/src/hooks/useCountries.ts` — `queryKey: ["countries"]`, stale 10 min, calls `GET /api/v1/countries`

**Checkpoint**: OpenAPI updated, types regenerated, store created — user story work can now proceed.

---

## Phase 3: User Story 1 — Dashboard Summary at a Glance (Priority: P1) 🎯 MVP

**Goal**: Authenticated users see four summary metric cards (total listings, new today, Tier 1 deals today, price drops 7d) and can filter the entire dashboard by country using URL-param-synced tabs.

**Independent Test**: Log in → navigate to `/en/dashboard?country=ES` → verify four cards render with numeric values, switch to `?country=FR` tab → verify all four cards update to France data.

### Backend — Dashboard Summary Endpoint

- [X] T012 Implement `GetDashboardSummary` repository function in `services/api-gateway/internal/repository/dashboard.go`: four parallel COUNT SQL queries (`total_listings`, `new_today`, `tier1_deals_today`, `price_drops_7d`) with Redis cache key `dashboard:summary:{country}` at 60s TTL; check cache before querying, populate on miss
- [X] T013 Implement `GetDashboardSummary` HTTP handler in `services/api-gateway/internal/handler/dashboard.go`: validate required `country` query param, verify country is accessible under user's subscription tier, call repository, return `DashboardSummary` JSON; return 400 on missing param, 403 on tier violation
- [X] T014 Register `GET /api/v1/dashboard/summary` route with auth middleware in the api-gateway router (check `services/api-gateway/cmd/server/main.go` or `internal/router/` for existing route registration pattern)

### Frontend — Country Tabs + Summary Cards

- [X] T015 Create `useDashboardSummary` TanStack Query hook in `frontend/src/hooks/useDashboardSummary.ts`: `queryKey: ["dashboard", "summary", country]`, stale 60s, calls `GET /api/v1/dashboard/summary?country={country}`, returns `DashboardSummary`
- [X] T016 [P] [US1] Create `CountryTabs` client component in `frontend/src/components/dashboard/CountryTabs.tsx`: calls `useCountries()`, renders shadcn-style tab strip; active tab from `useSearchParams().get("country")`; on click calls `useRouter().push()` with `?country=XX`; filters available countries by user subscription tier (free: 1 country, basic: 3, pro/global: all)
- [X] T017 [US1] Create `SummaryCards` client component in `frontend/src/components/dashboard/SummaryCards.tsx`: calls `useDashboardSummary(country)`, renders four shadcn `<Card>` components with Lucide icons (Building2 for total, TrendingUp for new today, Star for Tier1 deals, ArrowDownRight for price drops); skeleton loaders while fetching; zero values display as "0" not blank
- [X] T018 [US1] Replace `frontend/src/app/[locale]/(protected)/dashboard/page.tsx`: make it a RSC that prefetches `["dashboard", "summary", country]` and `["countries"]` via `queryClient.prefetchQuery`, wraps a new `DashboardClient` component in `<HydrationBoundary>`; reads `country` from `searchParams.country ?? "ES"`
- [X] T019 [US1] Create `DashboardClient` in `frontend/src/components/dashboard/DashboardClient.tsx`: client component that renders `<CountryTabs>` at top, then `<SummaryCards country={country} />` in `grid-cols-2 xl:grid-cols-4` layout; reads active country from `useSearchParams()`

**Checkpoint**: US1 fully functional — dashboard shows cards, country tabs update data.

---

## Phase 4: User Story 2 — Trend Charts for Zone Analysis (Priority: P2)

**Goal**: Three interactive Recharts charts below the summary cards: price/m² line chart by zone (12 months), monthly listing volume bar chart, deal score distribution histogram.

**Independent Test**: With a country selected, verify (a) line chart shows one line per zone with tooltips on hover, (b) bar chart shows monthly volumes, (c) histogram bins deal scores 0–100, (d) clicking a zone name in the legend toggles its line.

### Frontend — Zone Data Hooks

- [X] T020 [P] Create `useZoneList` TanStack Query hook in `frontend/src/hooks/useZoneList.ts`: `queryKey: ["zones", "list", country]`, stale 5 min, calls `GET /api/v1/zones?country={country}&limit=20`
- [X] T021 [P] Create `useZoneAnalytics` TanStack Query hook in `frontend/src/hooks/useZoneAnalytics.ts`: `queryKey: ["zones", zoneId, "analytics"]`, stale 5 min, calls `GET /api/v1/zones/{id}/analytics`

### Frontend — Chart Components

- [X] T022 [P] [US2] Create `PriceZoneChart` in `frontend/src/components/dashboard/PriceZoneChart.tsx`: calls `useZoneList(country)` then `useZoneAnalytics` for each zone (max 5 zones); transforms 12-month series into Recharts dataset keyed by `month`; Recharts `<ResponsiveContainer><LineChart>` with one `<Line>` per zone using a 5-color palette; `<Tooltip>` formats `${value.toLocaleString()} €/m²`; `<Legend>` with click-to-toggle; empty state when no data
- [X] T023 [P] [US2] Create `VolumeChart` in `frontend/src/components/dashboard/VolumeChart.tsx`: same zone analytics data source as T022; Recharts `<BarChart>` rendering `listing_count` per month as stacked bars; `<XAxis>` formatted `MMM YY` via `date-fns/format`; `<Tooltip>` shows count
- [X] T024 [P] [US2] Create `DealScoreHistogram` in `frontend/src/components/dashboard/DealScoreHistogram.tsx`: fetches first two pages of listings sorted by `deal_score` for `country` using `useListings` hook (existing); bins scores into 10 buckets (0–9 … 90–100) via `Array.reduce`; Recharts `<BarChart>` with bin labels on X axis; tooltip: "{n} listings"; fallback note "Based on top 200 listings" when dataset is capped
- [X] T025 [US2] Create `TrendCharts` container in `frontend/src/components/dashboard/TrendCharts.tsx`: responsive grid `grid-cols-1 xl:grid-cols-3` containing `<PriceZoneChart>`, `<VolumeChart>`, `<DealScoreHistogram>`; each chart wrapped in a shadcn `<Card>` with title
- [X] T026 [US2] Add `<TrendCharts country={country} />` below `<SummaryCards>` in `frontend/src/components/dashboard/DashboardClient.tsx`

**Checkpoint**: US2 functional — three interactive charts appear below the summary cards.

---

## Phase 5: User Story 3 — Interactive Property Map with Markers (Priority: P2)

**Goal**: MapLibre GL JS map with color-coded deal tier markers, maplibre native clustering below zoom 12, click-to-popup with mini listing card, viewport-bounded GeoJSON fetch with 300ms debounce, mobile touch support.

**Independent Test**: Load `/en/dashboard?country=ES` → scroll to map → verify green/blue/gray/red markers appear; zoom out → verify markers cluster into numbered circles; click a cluster → verify map zooms in; click a single marker → verify popup shows photo, price, deal score, address.

### Backend — Bounds-Filtered GeoJSON Listings Endpoint

- [X] T027 Add `bounds` query param parsing and `format` query param to `services/api-gateway/internal/handler/listings.go`: parse `bounds=minLng,minLat,maxLng,maxLat` (comma-separated floats, validated); when `format=geojson` build `FeatureCollection` response from results; when `format=json` (default) use existing pagination response path
- [X] T028 Add `Bounds *[4]float64` field to `ListingFilter` struct in `services/api-gateway/internal/repository/listings.go`; when non-nil append `AND ST_Intersects(location, ST_MakeEnvelope($minLng, $minLat, $maxLng, $maxLat, 4326))` WHERE clause; exclude listings with null `location` from GeoJSON results

### Frontend — Map Hooks and Components

- [X] T029 Create `useMapListings` TanStack Query hook in `frontend/src/hooks/useMapListings.ts`: `queryKey: ["listings", "map", country, bounds]`, stale 30s, `enabled: !!bounds`, calls `GET /api/v1/listings?format=geojson&country={country}&bounds={bounds}`, returns `ListingsGeoJSON`
- [X] T030 [P] [US3] Create `ListingPopup` component in `frontend/src/components/map/ListingPopup.tsx`: receives `listingId` prop; fetches listing detail via existing `useListings` hook; renders 60×60 photo thumbnail (placeholder if no URL), price formatted `€ X,XXX,XXX`, deal score badge colored by tier (green/blue/gray/red), address text; links to `/listing/{id}`; skeleton loader while fetching
- [X] T031 [P] [US3] Create `MapLayerToggle` component in `frontend/src/components/map/MapLayerToggle.tsx`: two-button toggle group "Markers" | "Heatmap"; on Markers click: `dashboardStore.setMapMode("markers")`; on Heatmap click: `dashboardStore.setMapMode("heatmap")`; reads current mode from store for active state
- [X] T032 [US3] Create `PropertyMapClient` in `frontend/src/components/map/PropertyMapClient.tsx`: initialise MapLibre GL JS map with OpenFreeMap liberty style (`https://tiles.openfreemap.org/styles/liberty`), `NavigationControl` top-right, country-centroid initial bounds lookup; add clustered GeoJSON source (`cluster: true, clusterRadius: 50, clusterMaxZoom: 14`) with id `"listings"`; add `"clusters"` circle layer (teal, size stepped by `point_count`), `"cluster-count"` symbol layer, `"unclustered-point"` circle layer with data-driven `circle-color` expression matching deal_tier (1→`#22c55e`, 2→`#3b82f6`, 3→`#9ca3af`, 4→`#ef4444`); cluster click handler: `map.easeTo` zoom-in; unclustered-point click handler: create `maplibregl.Popup`, render `<ListingPopup listingId={id}>` via `createRoot`; `moveend` handler debounced 300ms updates `bounds` state → triggers `useMapListings` refetch; `useEffect` updates source data when `useMapListings` returns new GeoJSON; reads `mapMode` from `dashboardStore`, toggles heatmap layer visibility (US6 stub); reads `showZoneOverlay` from store (US4 stub)
- [X] T033 [US3] Create `PropertyMap` server wrapper in `frontend/src/components/map/PropertyMap.tsx`: `dynamic(() => import("./PropertyMapClient"), { ssr: false, loading: () => <MapSkeleton /> })`; exports `PropertyMap` accepting `country` prop
- [X] T034 [US3] Add `<PropertyMap country={country} />` below `<TrendCharts>` in `frontend/src/components/dashboard/DashboardClient.tsx`; add `MapLayerToggle` above the map in a flex row with the map container

**Checkpoint**: US3 functional — map renders, markers cluster, popup works, mobile touch works.

---

## Phase 6: User Story 4 — Zone Polygon Overlay (Priority: P3)

**Goal**: Togglable zone boundary polygons on the map with hover tooltip showing zone name, median price/m², listing count, deal count.

**Independent Test**: Click "Show Zones" button → verify semi-transparent blue polygons appear on map; hover a polygon → verify tooltip shows zone name and stats; click "Hide Zones" → verify polygons disappear.

### Backend — Zone Geometry Endpoint

- [X] T035 Add `GetZoneGeometry` repository function in `services/api-gateway/internal/repository/zones.go`: `SELECT id, name, ST_AsGeoJSON(geometry)::json, ST_AsGeoJSON(bbox)::json FROM zones WHERE id=$1`; Redis cache key `zone:geometry:{id}` with 5 min TTL; returns `ZoneGeometry` struct with `ZoneID`, `ZoneName`, `Geometry` (raw JSON), `BBox [4]float64`
- [X] T036 Add `GetZoneGeometry` HTTP handler in `services/api-gateway/internal/handler/zones.go`: parse `{id}` path param (validate UUID), call repository, return `ZoneGeometry` JSON; 404 if not found
- [X] T037 Register `GET /api/v1/zones/{id}/geometry` route with auth middleware in the api-gateway router alongside existing zone routes

### Frontend — Zone Overlay

- [X] T038 Create `useZoneGeometry` TanStack Query hook in `frontend/src/hooks/useZoneGeometry.ts`: `queryKey: ["zones", zoneId, "geometry"]`, stale 10 min, `enabled` param (boolean), calls `GET /api/v1/zones/{id}/geometry`, returns `ZoneGeometry`
- [X] T039 [US4] Create `ZoneOverlayControl` component in `frontend/src/components/map/ZoneOverlayControl.tsx`: toggle button (`<Button variant="outline" size="sm">`) labelled "Zones"; on click calls `dashboardStore.toggleZoneOverlay()`; reads `showZoneOverlay` from store for active/inactive state; fetches zones via `useZoneList(country)`, then each geometry via `useZoneGeometry(zone.id, showZoneOverlay)`; when overlay turns on: add `fill` layers `"zone-fill-{id}"` (fill-color `#3b82f6`, fill-opacity 0.15) and `line` layers `"zone-border-{id}"` to map ref; add `mousemove` tooltip showing `zone.name`, `median_price_m2_eur`, `listing_count`, `deal_count`; when overlay turns off: remove all `zone-fill-*` and `zone-border-*` layers
- [X] T040 [US4] Integrate `ZoneOverlayControl` into `PropertyMapClient.tsx`: expose map ref to overlay control; add `<ZoneOverlayControl mapRef={mapRef} country={country} />` in the map controls row alongside `MapLayerToggle`

**Checkpoint**: US4 functional — zone polygons toggle on/off with hover stats.

---

## Phase 7: User Story 5 — Custom Zone Drawing Tool (Priority: P3)

**Goal**: Users draw a polygon on the map, name it, save it via POST /api/v1/zones, and see it in their zone list.

**Independent Test**: Activate draw tool → click 4+ points on map → double-click to close polygon → enter name "Test Zone" → save → verify zone appears in zone list and persists after page reload.

### Backend — Custom Zone Creation

- [X] T041 Add `CreateCustomZone` repository function in `services/api-gateway/internal/repository/zones.go`: accept `CreateCustomZoneRequest` + `userID string`; validate polygon via `SELECT ST_IsValid(ST_GeomFromGeoJSON($1))`; check user custom zone count (`SELECT COUNT(*) FROM zones WHERE user_id=$1 AND level=5`) against max-20 limit; INSERT into zones with `level=5`, `user_id`, `ST_GeomFromGeoJSON(geometry)`, generated UUID; return created `ZoneDetail`
- [X] T042 Add `CreateCustomZone` HTTP handler in `services/api-gateway/internal/handler/zones.go`: decode JSON body into `CreateCustomZoneRequest`; validate required fields (name 1–100 chars, type="custom", country, geometry); extract `userID` from JWT claims; call repository; return 201 with `ZoneDetail`; 400 on validation errors; 422 on invalid polygon; 429 on zone limit exceeded
- [X] T043 Register `POST /api/v1/zones` route with auth middleware in the api-gateway router

### Frontend — Draw Tool

- [X] T044 Create `useCreateCustomZone` TanStack mutation hook in `frontend/src/hooks/useCreateCustomZone.ts`: `useMutation` posting to `POST /api/v1/zones`; on success: invalidate `["zones", "list", country]`; on success also show toast notification "Zone saved successfully"
- [X] T045 [US5] Create `DrawZoneControl` component in `frontend/src/components/map/DrawZoneControl.tsx`: "Draw Zone" button; on click: initialise `@mapbox/mapbox-gl-draw` instance with `{ displayControlsDefault: false, controls: { polygon: true, trash: true } }`, `map.addControl(drawInstance)`, call `dashboardStore.setDrawingMode(true)`; listen for `draw.create` event: extract polygon coordinates from `event.features[0].geometry`; show shadcn `<Dialog>` with a `<Input>` name field (Zod validation: min 1, max 100 chars) + Save/Cancel buttons; on save: call `useCreateCustomZone` mutation with `{ name, type: "custom", country, geometry: polygon }`; on cancel or after save: `draw.deleteAll()`, `map.removeControl(drawInstance)`, `dashboardStore.setDrawingMode(false)`
- [X] T046 [US5] Integrate `DrawZoneControl` into `PropertyMapClient.tsx` map controls row; pass `mapRef` and `country` props; disable "Draw Zone" button when `drawingMode` is already true

**Checkpoint**: US5 functional — polygon drawn, named, saved, persists across reload.

---

## Phase 8: User Story 6 — Heatmap Layer (Priority: P3)

**Goal**: Alternative map visualization mode showing deal density heatmap; toggled from the MapLayerToggle component.

**Independent Test**: Click "Heatmap" in layer toggle → verify individual markers disappear and heatmap layer shows warmer colors in high-deal areas → click "Markers" → verify heatmap disappears and markers return.

- [X] T047 [US6] Add heatmap layer logic to `PropertyMapClient.tsx`: when `mapMode` changes to `"heatmap"`, set `"unclustered-point"` and `"clusters"` and `"cluster-count"` layer visibility to `"none"`; add a MapLibre `heatmap` layer id `"listings-heat"` on source `"listings"` with `heatmap-weight` driven by `["get", "deal_score"]` normalised 0–1 (÷ 100), `heatmap-color` ramp blue→green→yellow→orange→red, `heatmap-radius` 20px; when `mapMode` changes back to `"markers"`, remove `"listings-heat"` layer and restore visibility of marker layers

**Checkpoint**: US6 functional — heatmap toggles correctly with no regressions on marker mode.

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Responsive layout, loading states, type safety, and E2E validation.

- [X] T048 [P] Add responsive CSS to `DashboardClient.tsx`: on mobile (`<768px`) map takes full viewport height (`h-screen`), charts stack single-column, country tabs scroll horizontally with `overflow-x-auto`; on desktop maintain two-column chart grid and map below tabs
- [X] T049 [P] Add skeleton loaders in `SummaryCards.tsx` (four `<Skeleton>` placeholders while `useDashboardSummary` is loading), `TrendCharts.tsx` (chart-height skeletons), and `PropertyMap.tsx` (map placeholder div with spinner)
- [ ] T050 [P] Run TypeScript strict type check and fix all errors: `cd frontend && npm run type-check`
- [ ] T051 [P] Run Go build and tests for api-gateway: `cd services/api-gateway && go build ./... && go test ./internal/handler/... ./internal/repository/...`
- [ ] T052 E2E validation per quickstart.md: verify dashboard loads < 3s (Chrome DevTools network tab), country tab switch < 1s, 50k-marker map renders without frame drops, popup shows correct data, custom zone persists after reload, heatmap toggles cleanly, zone overlay hover tooltip shows stats, mobile pinch-to-zoom and tap work

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately; T002–T005 run in parallel
- **Phase 2 (Foundational)**: Depends on Phase 1; T006→T007→T008→T009 sequential (openapi → code → regen → types); T010 + T011 parallel after T009
- **Phases 3–8 (User Stories)**: All depend on Phase 2 completion
  - US1 (Phase 3) and US2 (Phase 4) can proceed in parallel after Phase 2
  - US3 (Phase 5) can proceed in parallel with US1/US2 after Phase 2
  - US4 (Phase 6) and US5 (Phase 7) depend on US3 map infrastructure (T032 map client)
  - US6 (Phase 8) depends on US3 map infrastructure (T032 map client)
- **Phase 9 (Polish)**: Depends on all desired user stories complete; T048–T051 run in parallel

### User Story Dependencies

- **US1 (P1)**: After Phase 2 — no other story dependencies
- **US2 (P2)**: After Phase 2 — no other story dependencies (zone analytics endpoint already exists in backend)
- **US3 (P2)**: After Phase 2 — no other story dependencies; **US4/US5/US6 all depend on US3 (T032)**
- **US4 (P3)**: After US3 T032 (PropertyMapClient must exist to integrate zone layers)
- **US5 (P3)**: After US3 T032 (PropertyMapClient must exist to add draw control)
- **US6 (P3)**: After US3 T032 (PropertyMapClient must exist to add heatmap layer)

### Within Each Phase

- Backend repository → backend handler → route registration (sequential within each story)
- Store/hooks → components → page integration (sequential within each story)
- Parallel opportunities within a story: repository and handler can be written together; chart components T022/T023/T024 are all fully parallel

---

## Parallel Opportunities Per User Story

### US1 (Phase 3 parallelism)
```
Parallel: T012 (repo) + T015 (hook)
Then parallel: T013 (handler) + T016 (CountryTabs) + T017 (SummaryCards)
Then: T014 (route) → T018 (page RSC) → T019 (DashboardClient)
```

### US2 (Phase 4 parallelism)
```
Parallel: T020 (useZoneList) + T021 (useZoneAnalytics) — both are hooks, no code deps
Then parallel: T022 (PriceZoneChart) + T023 (VolumeChart) + T024 (DealScoreHistogram)
Then: T025 (TrendCharts) → T026 (add to DashboardClient)
```

### US3 (Phase 5 parallelism)
```
Parallel: T027 (handler bounds) + T028 (repo bounds) + T029 (hook)
Parallel: T030 (ListingPopup) + T031 (MapLayerToggle)
Then: T032 (PropertyMapClient) → T033 (wrapper) → T034 (add to DashboardClient)
```

### US4 (Phase 6 parallelism)
```
Parallel: T035 (repo geometry) + T036 (handler geometry) + T038 (hook)
Then: T037 (route) → T039 (ZoneOverlayControl) → T040 (integrate into map)
```

### US5 (Phase 7 parallelism)
```
Parallel: T041 (repo) + T044 (mutation hook)
Then: T042 (handler) → T043 (route) → T045 (DrawZoneControl) → T046 (integrate)
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: US1 (T012–T019)
4. **STOP and VALIDATE**: Navigate to `/en/dashboard?country=ES` — four cards render with data, tabs switch correctly
5. Demo-ready minimal dashboard

### Incremental Delivery

1. Phase 1 + Phase 2 → Foundation ready
2. Phase 3 (US1) → Test independently → **MVP Dashboard** ✅
3. Phase 4 (US2) → Test independently → **Dashboard + Charts** ✅
4. Phase 5 (US3) → Test independently → **Dashboard + Charts + Map** ✅
5. Phases 6–8 (US4/US5/US6) → Test independently → **Full Feature** ✅
6. Phase 9 → Polish → Ship

### Parallel Team Strategy

With 2+ developers after Phase 2 completes:
- **Developer A**: US1 (Phase 3) + US2 (Phase 4) — pure frontend, no new backend needed for US2
- **Developer B**: US3 backend (T027–T028) + US3 frontend (T029–T034) — map infrastructure
- Once T032 lands: **Dev A or C** picks up US4 + US5 + US6 using the map client

---

## Notes

- `[P]` tasks touch different files with no shared incomplete dependencies — safe to implement concurrently
- `[Story]` label maps every task to its user story for precise traceability
- Each user story phase produces an independently testable dashboard increment
- All backend routes require JWT Bearer auth (use existing auth middleware pattern from other handlers)
- The `@mapbox/mapbox-gl-draw` package requires MapLibre GL JS map to be fully loaded (`map.on("load", ...)`) before attaching the control
- `PropertyMapClient` must be a Client Component (`"use client"`) and must NOT be server-rendered (enforced by the `dynamic(..., { ssr: false })` wrapper in `PropertyMap.tsx`)
- After T046 completes (DrawZoneControl), test polygon saving with both valid and self-intersecting polygons to confirm the 422 error path from T041
