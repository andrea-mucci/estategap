# Implementation Plan: Listing Search & Detail Pages

**Branch**: `023-listing-search-detail` | **Date**: 2026-04-17 | **Spec**: [spec.md](./spec.md)  
**Input**: Feature specification from `specs/023-listing-search-detail/spec.md`

## Summary

Build a full-featured listing search page (`/search`) with 15+ URL-synced filters, infinite scroll, grid/list toggle, and saved searches — plus a listing detail page (`/listing/[id]`) with photo gallery, AI deal score with SHAP explanation, price history chart, comparables carousel, mini-map with POIs, translation, CRM pipeline actions, and auto-saving private notes. Both pages integrate with the existing Go API gateway (`/api/v1/listings`), extend the MapLibre map infrastructure, and follow the Next.js 15 App Router / TanStack Query / Zustand patterns already established in the codebase.

## Technical Context

**Language/Version**: TypeScript 5.5 (strict mode) / Node.js 22  
**Primary Dependencies**: Next.js 15 (App Router, RSC), TanStack Query v5, nuqs (new — URL state), shadcn/ui, Recharts 2.x, MapLibre GL JS 4.x, yet-another-react-lightbox (new), Zustand 5, react-hook-form + Zod, next-intl  
**Storage**: No direct DB access — TanStack Query cache (server state), Zustand (UI state), localStorage (saved searches fallback)  
**Testing**: Vitest + React Testing Library  
**Target Platform**: Web (Next.js 15 SSR + CSR, responsive: desktop + mobile)  
**Project Type**: Frontend feature within existing Next.js 15 monorepo  
**Performance Goals**: Initial search results < 2s; filter update < 500ms; detail page SSR < 3s  
**Constraints**: Must use existing MapLibre setup; no new backend services in this feature; API types from OpenAPI codegen must not be manually modified  
**Scale/Scope**: 2 pages, ~25 new components, ~8 new hooks, 2 new Zustand slices

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Polyglot Service Architecture | ✅ PASS | Frontend-only feature. Go API gateway unchanged. No new services. |
| II. Event-Driven Communication | ✅ PASS | No inter-service communication. Frontend calls API Gateway via REST (the only approved external interface for clients). |
| III. Country-First Data Sovereignty | ✅ PASS | Country filter is first-class in ListingsQuery. All display uses EUR-normalized prices alongside original currency. |
| IV. ML-Powered Intelligence | ✅ PASS | SHAP explanation chart surfaces ML reasoning to users. Deal score badge uses existing scoring. |
| V. Code Quality Discipline | ✅ PASS | TypeScript strict mode. TanStack Query for server state. Zustand for client state. React Hook Form + Zod for filter validation. next-intl for all user-facing strings. |
| VI. Security & Ethical Scraping | ✅ PASS | JWT auth via NextAuth (existing). Translation API key proxied through Go gateway — not exposed to client. |
| VII. Kubernetes-Native Deployment | ✅ PASS | Frontend is an existing containerized service. No new Dockerfiles or Helm changes needed. |

**Constitution Check Result**: ALL GATES PASS — proceed to Phase 0.

## Project Structure

### Documentation (this feature)

```text
specs/023-listing-search-detail/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 research output
├── data-model.md        # Phase 1 data model
├── quickstart.md        # Phase 1 quickstart guide
├── contracts/           # Phase 1 API contracts
│   ├── saved-searches.md
│   ├── crm.md
│   └── translate.md
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── app/[locale]/(protected)/
│   │   ├── search/
│   │   │   └── page.tsx                    # Search page (client shell + SSR initial data)
│   │   └── listing/[id]/
│   │       └── page.tsx                    # Detail page (RSC — SSR fetch)
│   ├── components/
│   │   ├── search/
│   │   │   ├── SearchPage.tsx              # Client shell orchestrating sidebar + results
│   │   │   ├── FilterSidebar.tsx           # All filter controls
│   │   │   ├── FilterSidebarDrawer.tsx     # Mobile bottom-sheet wrapper
│   │   │   ├── CountryFilter.tsx           # Country Select
│   │   │   ├── CityAutocomplete.tsx        # Debounced city search input
│   │   │   ├── ZoneSelect.tsx              # Hierarchical zone select
│   │   │   ├── PropertyTypeFilter.tsx      # Category + type select
│   │   │   ├── PriceRangeSlider.tsx        # Dual range slider
│   │   │   ├── AreaRangeSlider.tsx         # Dual range slider
│   │   │   ├── BedroomsFilter.tsx          # Button group (1-5+)
│   │   │   ├── DealTierFilter.tsx          # Multi-select checkboxes
│   │   │   ├── StatusFilter.tsx            # Multi-select checkboxes
│   │   │   ├── PortalFilter.tsx            # Multi-select checkboxes
│   │   │   ├── SortDropdown.tsx            # Sort order select
│   │   │   ├── ViewToggle.tsx              # Grid vs list toggle
│   │   │   ├── SearchResultsGrid.tsx       # Card grid + infinite scroll
│   │   │   ├── SearchResultsList.tsx       # List rows + infinite scroll
│   │   │   ├── SearchListingCard.tsx       # Card in grid view (with CRM badge)
│   │   │   ├── SearchListingRow.tsx        # Row in list view (with CRM badge)
│   │   │   ├── InfiniteScrollSentinel.tsx  # IntersectionObserver sentinel
│   │   │   ├── SavedSearchButton.tsx       # Save current search
│   │   │   └── SavedSearchDropdown.tsx     # Load/delete saved searches
│   │   └── listing/
│   │       ├── ListingDetailPage.tsx       # Client wrapper (for interactive sections)
│   │       ├── PhotoGallery.tsx            # yet-another-react-lightbox gallery
│   │       ├── KeyStatsBar.tsx             # Price, area, rooms, floor, score badge
│   │       ├── DealScoreCard.tsx           # Estimated price, confidence range, tier
│   │       ├── ShapChart.tsx               # Recharts horizontal BarChart
│   │       ├── PriceHistoryChart.tsx       # Recharts LineChart
│   │       ├── ComparableCarousel.tsx      # Horizontally scrollable cards
│   │       ├── ComparableCard.tsx          # Mini card linking to detail page
│   │       ├── ZoneStatsCard.tsx           # Zone median, count, trend
│   │       ├── ListingMiniMap.tsx          # MapLibre single marker + POIs
│   │       ├── DescriptionSection.tsx      # Original text + translate button
│   │       ├── ListingMetadata.tsx         # Portal, published date, DOM, source link
│   │       ├── CrmActions.tsx              # shadcn ToggleGroup buttons
│   │       └── PrivateNotes.tsx            # Textarea with debounced auto-save
│   ├── hooks/
│   │   ├── useSearchParams.ts              # nuqs-backed typed search params hook
│   │   ├── useInfiniteListings.ts          # useInfiniteQuery for search page
│   │   ├── useCityAutocomplete.ts          # Debounced city query hook
│   │   ├── useZoneOptions.ts               # Zone list for selected country/city
│   │   ├── useSavedSearches.ts             # CRUD for saved searches (API + localStorage)
│   │   ├── useListingDetail.ts             # Query for single listing detail
│   │   ├── useComparables.ts               # Fetch comparable listings by IDs
│   │   ├── useTranslate.ts                 # Mutation for translation API
│   │   ├── useCrmStatus.ts                 # Query + optimistic mutation for CRM status
│   │   └── usePrivateNotes.ts              # Debounced auto-save mutation for notes
│   ├── stores/
│   │   ├── searchStore.ts                  # UI state: viewMode, sidebar open on mobile
│   │   └── crmStore.ts                     # Local CRM status cache (for card badges)
│   └── lib/
│       └── api.ts                          # Extend with: savedSearches, crm, translate endpoints
```

**Structure Decision**: Extends the existing `frontend/` Next.js 15 App Router structure. New components are placed under `components/search/` and `components/listing/` following the established component colocation pattern. New hooks extend the existing `hooks/` directory. The detail page RSC fetches data server-side for SEO; interactive client components are separated into `ListingDetailPage.tsx`.

## Complexity Tracking

> No Constitution Check violations. Table omitted.
