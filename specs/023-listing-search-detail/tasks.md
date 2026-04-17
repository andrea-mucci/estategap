# Tasks: Listing Search & Detail Pages

**Input**: Design documents from `specs/023-listing-search-detail/`  
**Branch**: `023-listing-search-detail`  
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Organization**: Tasks grouped by user story — each phase is independently deliverable and testable.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no shared dependencies within phase)
- **[Story]**: Which user story this task belongs to (US1–US4)
- File paths relative to repo root

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Install new dependencies, wire adapters, and create the shared Zustand stores and API client extensions that all user stories depend on.

- [X] T001 Install `nuqs` and `yet-another-react-lightbox` in `frontend/` (`pnpm add nuqs yet-another-react-lightbox`)
- [X] T002 Add `NuqsAdapter` from `nuqs/adapters/next/app` to `frontend/src/app/[locale]/layout.tsx` wrapping existing providers
- [X] T003 [P] Create `frontend/src/stores/searchStore.ts` — Zustand store with `viewMode` ('grid'|'list'), `isSidebarOpen` (mobile), `setViewMode`, `toggleSidebar`, `closeSidebar`
- [X] T004 [P] Create `frontend/src/stores/crmStore.ts` — Zustand store with `entries: Record<string, CrmStatus>`, `setStatus(listingId, status)`, `bulkLoad(entries)` methods
- [X] T005 Extend `frontend/src/lib/api.ts` with client functions for new endpoints: `fetchSavedSearches`, `createSavedSearch`, `deleteSavedSearch`, `fetchCrmEntry`, `fetchCrmBulk`, `patchCrmStatus`, `patchCrmNotes`, `translateText`

**Checkpoint**: Dependencies installed, adapters wired, stores and API helpers available — all user story work can begin.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core hooks that are shared across multiple user stories. Must be complete before Phase 3+ work.

**⚠️ CRITICAL**: US1, US2, and US4 all depend on `useSearchParams`. US3 depends on the extended `api.ts` from Phase 1.

- [X] T006 Create `frontend/src/hooks/useSearchParams.ts` — `useQueryStates` from nuqs with typed parsers for all 14 filter fields: `country` (string, default 'ES'), `city` (string), `zone_id` (string), `property_category` (string literal union), `property_type` (string), `min_price_eur`/`max_price_eur` (integer), `min_area_m2`/`max_area_m2` (integer), `min_bedrooms` (integer), `deal_tier` (array of integer), `status` (array of string), `source_portal` (array of string), `sort_by` (string, default 'deal_score'), `sort_dir` (string, default 'desc'); export `ListingSearchParams` type
- [X] T007 Create `frontend/src/hooks/useCityAutocomplete.ts` — `useQuery` with 300ms debounce calling `GET /api/v1/zones?level=city&q={term}&country={country}`; returns `{ suggestions: string[], isLoading }` — enabled only when input length ≥ 2
- [X] T008 Create `frontend/src/hooks/useZoneOptions.ts` — wraps existing `useZoneList` hook, filters by selected country; returns `{ zones: ZoneDetail[], isLoading }`

**Checkpoint**: Foundation hooks ready — US1 and US3 can now proceed in parallel.

---

## Phase 3: User Story 1 — Advanced Filtered Property Search (Priority: P1) 🎯 MVP

**Goal**: A fully functional search page at `/search` with all 15+ filters, infinite scroll, grid/list toggle, sort, and shareable URLs.

**Independent Test**: Navigate to `/en/search?country=ES&deal_tier=1%2C2&max_price_eur=500000&sort_by=deal_score` — verify results show only Tier 1+2 listings under €500k sorted by deal score; toggle grid/list view; scroll to bottom to load next page; verify URL updates on every filter change.

### Implementation for User Story 1

- [X] T009 [P] [US1] Create `frontend/src/hooks/useInfiniteListings.ts` — `useInfiniteQuery` using `fetchListings` from `lib/api.ts`; query key includes full `ListingSearchParams`; `initialPageParam: undefined`; `getNextPageParam` reads `pagination.next_cursor` when `has_more` is true; `placeholderData: keepPreviousData`
- [X] T010 [P] [US1] Create `frontend/src/components/search/InfiniteScrollSentinel.tsx` — renders a `<div ref>` observed by `IntersectionObserver` with `rootMargin: '240px'`; calls `onVisible()` prop when intersecting; shows a `Loader2` spinner when `isLoading` prop is true
- [X] T011 [P] [US1] Create `frontend/src/components/search/ViewToggle.tsx` — two shadcn `Toggle` buttons (LayoutGrid / List icons from lucide-react); reads/writes `viewMode` from `searchStore`; accessible with `aria-label`
- [X] T012 [P] [US1] Create `frontend/src/components/search/SortDropdown.tsx` — shadcn `Select` with options: deal_score/desc (Deal Score), price/asc (Price ↑), price/desc (Price ↓), price_m2/asc (Price/m² ↑), recency/desc (Newest), days_on_market/asc (Days on Market); reads/writes `sort_by` + `sort_dir` from `useSearchParams`
- [X] T013 [P] [US1] Create `frontend/src/components/search/SearchListingCard.tsx` — card component for grid view using `ListingSummary` type; shows: first photo (or placeholder), price (formatted EUR), area m², bedrooms, city, zone name, deal score badge (color-coded by tier: T1=green, T2=blue, T3=gray, T4=red), days on market; accepts optional `crmStatus: CrmStatus` prop and renders a small badge when non-null; links to `/listing/{id}`
- [X] T014 [P] [US1] Create `frontend/src/components/search/SearchListingRow.tsx` — horizontal list row variant of the card; same data as card but in a single wide row with photo thumbnail on left; same CRM badge support and link
- [X] T015 [US1] Create `frontend/src/components/search/SearchResultsGrid.tsx` — receives `pages` (InfiniteData), renders `SearchListingCard` in a CSS grid (3 cols desktop via `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3`); appends `InfiniteScrollSentinel` at bottom; shows skeleton cards during initial load (`isLoading`); shows "No listings found" empty state when `totalCount === 0`
- [X] T016 [US1] Create `frontend/src/components/search/SearchResultsList.tsx` — same as grid but renders `SearchListingRow` in a flex-col stack; reuses `InfiniteScrollSentinel`
- [X] T017 [P] [US1] Create `frontend/src/components/search/CountryFilter.tsx` — shadcn `Select` populated from `useCountries()`; writes `country` to `useSearchParams`; also clears `city`, `zone_id` when country changes
- [X] T018 [P] [US1] Create `frontend/src/components/search/CityAutocomplete.tsx` — shadcn `Input` with a popover dropdown; uses `useCityAutocomplete(term, country)`; shows suggestions list; on select writes `city` to `useSearchParams` and clears `zone_id`; shows "No cities found" when suggestions empty
- [X] T019 [P] [US1] Create `frontend/src/components/search/ZoneSelect.tsx` — shadcn `Select` populated from `useZoneOptions(country, city)`; writes `zone_id` to `useSearchParams`; disabled when no city selected; shows zone name + listing count
- [X] T020 [P] [US1] Create `frontend/src/components/search/PropertyTypeFilter.tsx` — two shadcn `Select` components in sequence: category (residential/commercial/industrial/land) then type (populated based on category); writes `property_category` and `property_type` to `useSearchParams`
- [X] T021 [P] [US1] Create `frontend/src/components/search/PriceRangeSlider.tsx` — shadcn `Slider` dual-thumb (0–5,000,000 EUR, step 10,000); two `Input` fields for manual entry; displays formatted values (e.g., "€250k"); writes `min_price_eur` / `max_price_eur` to `useSearchParams` on `onValueCommit` (not on drag to avoid excessive URL updates)
- [X] T022 [P] [US1] Create `frontend/src/components/search/AreaRangeSlider.tsx` — same pattern as PriceRangeSlider but for area (0–1,000 m², step 5); writes `min_area_m2` / `max_area_m2`
- [X] T023 [P] [US1] Create `frontend/src/components/search/BedroomsFilter.tsx` — row of 5 shadcn `Toggle` buttons labeled "1", "2", "3", "4", "5+"; selecting one writes `min_bedrooms` (5+ writes value 5) to `useSearchParams`; only one active at a time
- [X] T024 [P] [US1] Create `frontend/src/components/search/DealTierFilter.tsx` — four shadcn `Checkbox` items labeled "T1 (Great)", "T2 (Good)", "T3 (Fair)", "T4 (Weak)" with matching tier colors; writes array to `deal_tier` in `useSearchParams`
- [X] T025 [P] [US1] Create `frontend/src/components/search/StatusFilter.tsx` — three shadcn `Checkbox` items: "Active", "Delisted", "Price Changed"; writes array to `status` in `useSearchParams`
- [X] T026 [P] [US1] Create `frontend/src/components/search/PortalFilter.tsx` — shadcn `Checkbox` list populated from distinct portals in search results meta (or hardcoded fallback list); writes array to `source_portal` in `useSearchParams`
- [X] T027 [US1] Create `frontend/src/components/search/FilterSidebar.tsx` — vertical stack of all filter components (T017–T026); includes a "Clear all filters" button that resets all `useSearchParams` fields to defaults; shows active filter count badge on the "Filters" header
- [X] T028 [US1] Create `frontend/src/components/search/FilterSidebarDrawer.tsx` — wraps `FilterSidebar` in a shadcn `Sheet` (bottom on mobile, side on tablet); triggered by a "Filters" button that is only visible below `lg` breakpoint; reads `isSidebarOpen` / `closeSidebar` from `searchStore`
- [X] T029 [US1] Create `frontend/src/components/search/SearchPage.tsx` — client component; two-column layout (`lg:grid lg:grid-cols-[280px_1fr]`): left = `FilterSidebar` (hidden on mobile, always visible on desktop), right = header bar (result count, `SortDropdown`, `ViewToggle`) + conditional `SearchResultsGrid` or `SearchResultsList` based on `viewMode`; passes filter params from `useSearchParams` to `useInfiniteListings`; renders `FilterSidebarDrawer` for mobile
- [X] T030 [US1] Update `frontend/src/app/[locale]/(protected)/search/page.tsx` — replace skeleton with `<SearchPage />`; add page `metadata` for SEO (title via `next-intl`)

**Checkpoint**: Full search page with all 15+ filters working, URL-synced, infinite scroll, grid/list toggle — US1 independently testable.

---

## Phase 4: User Story 3 — Listing Detail Page with Full Analysis (Priority: P1)

**Goal**: A complete listing detail page at `/listing/[id]` with photo gallery, AI analysis, charts, map, translation, CRM actions, and private notes.

**Independent Test**: Navigate to `/en/listing/{id}` for a listing with full data — verify all sections render: gallery opens lightbox on click, SHAP chart shows 5 colored bars, price history chart shows all data points, comparable carousel scrolls, mini-map shows listing marker + POIs, translate button replaces text, CRM buttons toggle and persist, notes auto-save after typing.

### Implementation for User Story 3

- [X] T031 [P] [US3] Create `frontend/src/hooks/useListingDetail.ts` — `useQuery` wrapping `fetchListingDetail(token, id)`; query key `['listing', id]`; staleTime 120s (detail data changes rarely)
- [X] T032 [P] [US3] Create `frontend/src/hooks/useComparables.ts` — accepts `comparableIds: string[]`; uses `useQueries` to fetch each comparable's `ListingSummary` in parallel via `fetchListingDetail`; returns `{ comparables: ListingDetail[], isLoading }`; skips if `comparableIds` is empty
- [X] T033 [P] [US3] Create `frontend/src/hooks/useTranslate.ts` — `useMutation` calling `translateText(token, text, targetLang)`; derives `targetLang` from `useLocale()` mapped via `LOCALE_TO_DEEPL` constant; manages `translatedText` state; `onError` shows shadcn `toast` error; export `LOCALE_TO_DEEPL` map for all 10 supported locales
- [X] T034 [P] [US3] Create `frontend/src/hooks/useCrmStatus.ts` — `useQuery` for `fetchCrmEntry(token, listingId)` + `useMutation` for `patchCrmStatus`; optimistic update: snapshot cache in `onMutate`, update immediately, revert in `onError`, invalidate in `onSettled`; also calls `crmStore.setStatus` after successful mutation so search card badges update
- [X] T035 [P] [US3] Create `frontend/src/hooks/usePrivateNotes.ts` — manages local `notes` string state; `useMutation` for `patchCrmNotes`; `saveStatus` state: `'idle' | 'saving' | 'saved' | 'error'`; triggers mutation via `useDebouncedCallback(500)`; resets `saveStatus` to `'saved'` on success, `'error'` on failure
- [X] T036 [P] [US3] Create `frontend/src/components/listing/PhotoGallery.tsx` — displays first photo as hero image (click to open lightbox); renders `<Lightbox>` from `yet-another-react-lightbox` with `Thumbnails` and `Zoom` plugins; `slides` from `photo_urls`; shows placeholder image when `photo_urls` is empty; uses `next/image` for the hero with `priority`
- [X] T037 [P] [US3] Create `frontend/src/components/listing/KeyStatsBar.tsx` — horizontal bar showing: formatted price (EUR + original currency if different), area m², bedrooms count, floor number; deal score badge with tier color (T1=green-500, T2=blue-500, T3=gray-400, T4=red-500) showing numeric score and tier label; uses shadcn `Badge`
- [X] T038 [P] [US3] Create `frontend/src/components/listing/DealScoreCard.tsx` — shadcn `Card` with: estimated fair price (bold, EUR formatted), confidence range ("€Xk – €Xk"), percentage gap between asking and estimated ("X% below estimate" in green or "X% above estimate" in red), deal tier badge; shows "Analysis unavailable" when `estimated_price` is null
- [X] T039 [P] [US3] Create `frontend/src/components/listing/ShapChart.tsx` — Recharts `BarChart` with `layout="vertical"`; selects top 5 features by `Math.abs(value)` from `shap_features`; maps feature keys to human-readable labels via `SHAP_LABELS` constant; `Cell` fill: `#22c55e` for positive, `#ef4444` for negative; `ReferenceLine` at x=0; `ResponsiveContainer` width 100%; shows "No analysis available" when `shap_features` is null/empty; export `SHAP_LABELS` map
- [X] T040 [P] [US3] Create `frontend/src/components/listing/PriceHistoryChart.tsx` — Recharts `LineChart` with `price_history` array; X-axis: date formatted with `date-fns` `format(date, 'MMM yy')`; Y-axis: price formatted as "€Xk"; `Tooltip` shows exact price and date; single dot rendered for single-point history; shows "No price history" empty state when array is empty; `ResponsiveContainer`
- [X] T041 [US3] Create `frontend/src/components/listing/ComparableCard.tsx` — mini card showing: small photo thumbnail, formatted price, area m², deal score badge; links to `/listing/{comparable.id}`; uses `next/link`
- [X] T042 [US3] Create `frontend/src/components/listing/ComparableCarousel.tsx` — horizontal scrollable flex row of `ComparableCard` components; uses `useComparables(comparable_ids)` hook; shows skeleton cards while loading; hides section when `comparable_ids` is empty; scroll snap on mobile
- [X] T043 [P] [US3] Create `frontend/src/components/listing/ZoneStatsCard.tsx` — shadcn `Card` with `zone_stats` data: zone name, median price/m² (formatted), listing count, deal count, price trend percentage (with ↑ green / ↓ red arrow icon); shows "Zone data unavailable" when `zone_stats` is null
- [X] T044 [US3] Create `frontend/src/components/listing/ListingMiniMap.tsx` — dynamic import (`ssr: false`) client component; initializes `maplibregl.Map` in `useEffect` centered on `[lng, lat]` at zoom 14; adds listing marker (red pin); accepts `pois: POI[]` prop and renders metro (🚇), school (🏫), park (🌳) markers with distinct SVG icons via `maplibregl.Marker`; cleanup on unmount; shows "Map unavailable" when lat/lng is null; height fixed at 280px
- [X] T045 [P] [US3] Create `frontend/src/components/listing/DescriptionSection.tsx` — displays description text; "Translate" button calls `useTranslate` mutation; button shows `Loader2` spinner when `isPending`; replaces text with `translatedText` on success; button label changes to "Show Original" to toggle back; hides button when listing language matches user locale
- [X] T046 [P] [US3] Create `frontend/src/components/listing/ListingMetadata.tsx` — table/dl of metadata: source portal name, published date (formatted with `date-fns`), days on market, external link to `source_url` (opens in new tab with `rel="noopener noreferrer"`); uses `CalendarDays`, `Clock`, `ExternalLink` icons from lucide-react
- [X] T047 [US3] Create `frontend/src/components/listing/CrmActions.tsx` — shadcn `ToggleGroup` with 5 buttons: Favorite (Heart), Contacted (Phone), Visited (Home), Offer Made (FileText), Discard (X); reads current status from `useCrmStatus(listingId)`; on click calls mutation with new status (or null to deactivate current); active button highlighted per tier color; shows loading state during mutation
- [X] T048 [US3] Create `frontend/src/components/listing/PrivateNotes.tsx` — shadcn `Textarea` (resize-none, min-height 120px) with placeholder "Add private notes..."; reads initial value from `useCrmStatus` notes; uses `usePrivateNotes` hook; shows save status indicator: idle=nothing, saving=`Loader2` + "Saving...", saved=`Check` + "Saved", error=`AlertCircle` + "Save failed" (all from lucide-react + shadcn `Badge`)
- [X] T049 [US3] Create `frontend/src/components/listing/ListingDetailPage.tsx` — client wrapper component that orchestrates all interactive sections; receives `ListingDetail` as prop (fetched server-side); renders section layout: PhotoGallery → KeyStatsBar → [DealScoreCard + ShapChart side-by-side on desktop] → PriceHistoryChart → ComparableCarousel → [ZoneStatsCard + ListingMiniMap side-by-side on desktop] → DescriptionSection → ListingMetadata → CrmActions → PrivateNotes
- [X] T050 [US3] Replace `frontend/src/app/[locale]/(protected)/listing/[id]/page.tsx` with RSC — use `createServerApiClient()` to fetch `ListingDetail` server-side; pass as prop to `ListingDetailPage`; add `generateMetadata` export using listing title + city + price for SEO; return `notFound()` on 404

**Checkpoint**: Full listing detail page with all sections operational — US3 independently testable.

---

## Phase 5: User Story 2 — Saved Search CRUD (Priority: P2)

**Goal**: Users can save the current filter state with a name, load saved searches to restore all filters, and delete saved searches. Persists across devices via API (localStorage fallback).

**Independent Test**: Apply filters on search page → click "Save Search" → enter name → verify it appears in dropdown → refresh page → load saved search → verify all filters restored → delete saved search → verify it's removed.

### Implementation for User Story 2

- [X] T051 [US2] Create `frontend/src/hooks/useSavedSearches.ts` — `useQuery` for `fetchSavedSearches`; `useMutation` for create (optimistic add to list) and delete (optimistic remove); localStorage read/write in `onError` fallback; `SavedSearch` type from `data-model.md`; localStorage key `estategap_saved_searches`; query key `['saved-searches']`
- [X] T052 [US2] Create `frontend/src/components/search/SavedSearchButton.tsx` — shadcn `Button` with `Bookmark` icon labeled "Save Search"; opens a shadcn `Dialog` with an `Input` for the search name and a "Save" confirm button; on confirm calls `useSavedSearches().createSavedSearch({ name, filters: currentParams })` where `currentParams` comes from `useSearchParams`; disables save button when name is empty
- [X] T053 [US2] Create `frontend/src/components/search/SavedSearchDropdown.tsx` — shadcn `DropdownMenu` triggered by a "Saved" button with `BookmarkCheck` icon; lists all saved searches by name with a delete button (trash icon) per item; clicking an item calls `useSearchParams.setParams(savedSearch.filters)` to restore all filters at once; shows "No saved searches" empty state; shows count badge on trigger when searches exist
- [X] T054 [US2] Integrate saved search components into `frontend/src/components/search/SearchPage.tsx` — add `SavedSearchButton` and `SavedSearchDropdown` to the results header bar next to `SortDropdown` and `ViewToggle`

**Checkpoint**: Full saved search CRUD functional with URL restoration — US2 independently testable.

---

## Phase 6: User Story 4 — CRM Status Visible on Search Cards (Priority: P2)

**Goal**: CRM pipeline status set on the detail page appears as a visual badge on listing cards in search results, enabling at-a-glance triage.

**Independent Test**: Set CRM status "Favorite" on a listing detail page → navigate back to search → verify the listing card shows a "Favorite" badge → set "Discard" → verify card updates badge.

### Implementation for User Story 4

- [X] T055 [US4] Update `frontend/src/hooks/useInfiniteListings.ts` — after each page loads, extract listing IDs from results and call `fetchCrmBulk(token, ids)` then dispatch `crmStore.bulkLoad(entries)` to populate the CRM store; use `onSuccess` callback on the `useInfiniteQuery`
- [X] T056 [P] [US4] Update `frontend/src/components/search/SearchListingCard.tsx` — read `crmStatus` from `crmStore.entries[listing.id]`; render a small status badge in the card's top-right corner when non-null: Favorite=Heart (red), Contacted=Phone (blue), Visited=Home (green), Offer=FileText (yellow), Discard=X (gray); use `title` attribute for accessibility
- [X] T057 [P] [US4] Update `frontend/src/components/search/SearchListingRow.tsx` — same CRM badge integration as T056 for the list view row

**Checkpoint**: CRM badges appear on search cards without additional API calls — US4 independently testable.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: i18n string coverage, mobile experience, loading states, error boundaries, and final quality checks.

- [X] T058 [P] Add i18n message keys to `frontend/src/messages/en.json` (and stub keys in all 9 other locale files) for all new UI strings: filter labels, empty states, save search dialog, CRM button labels, translate button, notes placeholder, SHAP feature labels, error messages
- [X] T059 [P] Add skeleton loading states to `SearchListingCard.tsx` and `SearchListingRow.tsx` using shadcn `Skeleton` — shown when `isLoading` is true on the initial query (before first page arrives)
- [X] T060 [P] Add `ErrorBoundary` wrapper to `frontend/src/components/listing/ShapChart.tsx` and `PriceHistoryChart.tsx` — catches render errors in chart data and shows "Chart unavailable" fallback instead of crashing the detail page
- [X] T061 [P] Verify and test `FilterSidebarDrawer.tsx` on mobile — open/close animation, scroll within drawer, "Apply" button that closes drawer after filter selection on small screens
- [X] T062 [P] Add `loading.tsx` to `frontend/src/app/[locale]/(protected)/search/` — Next.js route segment loading UI showing a skeleton search layout (sidebar skeleton + 6 card skeletons)
- [X] T063 [P] Add `loading.tsx` to `frontend/src/app/[locale]/(protected)/listing/[id]/` — skeleton layout matching the detail page structure (hero image skeleton, stats bar skeleton, two chart skeletons)
- [X] T064 [P] Add `error.tsx` to `frontend/src/app/[locale]/(protected)/listing/[id]/` — client error boundary with "Listing not found" message and back-to-search link for 404s
- [ ] T065 Run `pnpm typecheck` in `frontend/` and fix all TypeScript errors — ensure strict mode compliance across all new files
- [ ] T066 Run `pnpm lint` in `frontend/` and fix all ESLint errors — ensure no unused imports, missing keys, or accessibility violations

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 1 (Setup)           → no dependencies — start immediately
Phase 2 (Foundational)    → depends on Phase 1 (needs nuqs installed for useSearchParams)
Phase 3 (US1 — Search)    → depends on Phase 2 (uses useSearchParams hook)
Phase 4 (US3 — Detail)    → depends on Phase 1 (uses extended api.ts) — CAN run in parallel with Phase 3
Phase 5 (US2 — Saved)     → depends on Phase 3 (integrates into SearchPage)
Phase 6 (US4 — CRM badges)→ depends on Phase 3 (updates search cards) and Phase 4 (CRM status mutations)
Phase 7 (Polish)           → depends on Phase 3, 4, 5, 6 being complete
```

### User Story Dependencies

- **US1 (P1 — Search page)**: Starts after Phase 2. No dependency on US3.
- **US3 (P1 — Detail page)**: Starts after Phase 1. No dependency on US1.
- **US2 (P2 — Saved searches)**: Starts after US1 completes (integrates into SearchPage component).
- **US4 (P2 — CRM badges)**: Starts after both US1 and US3 are complete (needs search cards + CRM mutations).

### Within Each Phase

- All tasks marked `[P]` within a phase can be executed in parallel (they target different files)
- Non-`[P]` tasks within a phase depend on the `[P]` tasks in that phase completing first
- T029 (SearchPage assembly) depends on T009–T028 being done
- T049 (ListingDetailPage assembly) depends on T031–T048 being done
- T054 (SavedSearch integration) depends on T051–T053 being done

---

## Parallel Execution Examples

### Phase 3 (US1) — All filter components run in parallel

```
Parallel batch A (T011, T012, T013, T014 — UI primitives):
  Task: "Create ViewToggle.tsx in frontend/src/components/search/"
  Task: "Create SortDropdown.tsx in frontend/src/components/search/"
  Task: "Create SearchListingCard.tsx in frontend/src/components/search/"
  Task: "Create SearchListingRow.tsx in frontend/src/components/search/"

Parallel batch B (T017–T026 — all filter controls):
  Task: "Create CountryFilter.tsx"
  Task: "Create CityAutocomplete.tsx"
  Task: "Create ZoneSelect.tsx"
  Task: "Create PropertyTypeFilter.tsx"
  Task: "Create PriceRangeSlider.tsx"
  Task: "Create AreaRangeSlider.tsx"
  Task: "Create BedroomsFilter.tsx"
  Task: "Create DealTierFilter.tsx"
  Task: "Create StatusFilter.tsx"
  Task: "Create PortalFilter.tsx"

Sequential: T027 (FilterSidebar) → T028 (FilterSidebarDrawer) → T029 (SearchPage) → T030 (page.tsx)
```

### Phase 4 (US3) — All leaf components run in parallel

```
Parallel batch A (T031–T035 — all hooks):
  Task: "Create useListingDetail.ts"
  Task: "Create useComparables.ts"
  Task: "Create useTranslate.ts"
  Task: "Create useCrmStatus.ts"
  Task: "Create usePrivateNotes.ts"

Parallel batch B (T036–T040, T043, T045, T046 — independent components):
  Task: "Create PhotoGallery.tsx"
  Task: "Create KeyStatsBar.tsx"
  Task: "Create DealScoreCard.tsx"
  Task: "Create ShapChart.tsx"
  Task: "Create PriceHistoryChart.tsx"
  Task: "Create ZoneStatsCard.tsx"
  Task: "Create DescriptionSection.tsx"
  Task: "Create ListingMetadata.tsx"

Sequential: T041→T042 (ComparableCard→Carousel), T044 (MiniMap), T047 (CrmActions), T048 (PrivateNotes)
Then: T049 (ListingDetailPage assembly) → T050 (page.tsx RSC)
```

---

## Implementation Strategy

### MVP First (US1 — Search Page Only)

1. Complete **Phase 1**: Install deps, wire adapters, create stores, extend api.ts
2. Complete **Phase 2**: `useSearchParams`, `useCityAutocomplete`, `useZoneOptions`
3. Complete **Phase 3**: Full search page with all filters and infinite scroll
4. **STOP and VALIDATE**: Verify all 15+ filters work, URL syncs, infinite scroll loads pages
5. This alone is a shippable feature

### Incremental Delivery

1. Phase 1 + 2 → Foundation ready
2. Phase 3 → Search page live (MVP)
3. Phase 4 → Detail page live (both P1 stories complete)
4. Phase 5 → Saved searches (P2 add-on)
5. Phase 6 → CRM badges on cards (P2 add-on)
6. Phase 7 → Polish & quality

### Parallel Team Strategy

With two developers after Phase 1+2:
- **Developer A**: Phase 3 (US1 — search page)
- **Developer B**: Phase 4 (US3 — detail page)
Both can proceed simultaneously as they touch entirely different files.

---

## Notes

- `[P]` tasks target different files with no intra-phase file conflicts
- `[US*]` labels map to spec.md user stories for traceability
- No test tasks generated — tests not explicitly requested in spec
- `yet-another-react-lightbox` and `nuqs` are the only new dependencies (T001)
- All existing hooks (`useZoneList`, `useCountries`, `useZoneAnalytics`) are reused as-is
- `lib/api.ts` is extended (T005) but the `fetchListings` / `fetchListingDetail` functions are not modified
- The existing `ListingDetailView.tsx` component in `components/listings/` is superseded by `ListingDetailPage.tsx` in `components/listing/` — can be removed in Phase 7 cleanup (T065/T066)
