# Quickstart: Listing Search & Detail Pages

**Feature**: 023-listing-search-detail  
**Date**: 2026-04-17

## Prerequisites

- Node.js 22 + pnpm installed
- Local API gateway running on `http://localhost:8080` (or `.env.local` pointing to staging)
- Frontend `.env.local` configured (see `frontend/.env.example`)

## 1. Install New Dependencies

```bash
cd frontend
pnpm add nuqs yet-another-react-lightbox
```

Verify versions: nuqs `^2.x`, yet-another-react-lightbox `^3.x`.

## 2. Add NuqsAdapter to Root Layout

In `frontend/src/app/[locale]/layout.tsx`, wrap children with `NuqsAdapter`:

```tsx
import { NuqsAdapter } from 'nuqs/adapters/next/app'

// Wrap existing providers:
<NuqsAdapter>
  <QueryProvider>
    <AuthProvider session={session}>
      {children}
    </AuthProvider>
  </QueryProvider>
</NuqsAdapter>
```

## 3. Run the Dev Server

```bash
cd frontend
pnpm dev
```

Navigate to `http://localhost:3000/en/search` — you should see the search page (currently a skeleton).

## 4. Development Order

Implement components in this order to enable independent testing at each step:

### Step 1 — Filter state & basic results (no UI yet)

1. Create `hooks/useSearchParams.ts` with nuqs parsers
2. Create `hooks/useInfiniteListings.ts` with `useInfiniteQuery`
3. Verify: `http://localhost:3000/en/search?country=ES&deal_tier=1` fetches and logs Tier 1 listings in browser console

### Step 2 — Search page layout

1. Create `components/search/SearchPage.tsx` — two-column layout (sidebar + results)
2. Create `components/search/ViewToggle.tsx` and `components/search/SortDropdown.tsx`
3. Create `components/search/SearchListingCard.tsx` using the existing `ListingSummary` type
4. Create `components/search/InfiniteScrollSentinel.tsx` with `IntersectionObserver`
5. Update `app/[locale]/(protected)/search/page.tsx` to render `SearchPage`

### Step 3 — Filter controls

Implement in order (simplest first):
1. `CountryFilter` (Select)
2. `BedroomsFilter` (button group)
3. `DealTierFilter` (checkboxes)
4. `StatusFilter` (checkboxes)
5. `PortalFilter` (checkboxes)
6. `PriceRangeSlider` (shadcn Slider dual-thumb)
7. `AreaRangeSlider` (shadcn Slider dual-thumb)
8. `CityAutocomplete` (Input + debounced query to `/api/v1/zones?level=city&q=`)
9. `ZoneSelect` (Select, populated from `useZoneOptions`)
10. `PropertyTypeFilter` (two Selects: category → type)
11. `FilterSidebarDrawer` (mobile bottom sheet using shadcn Sheet)

### Step 4 — Saved searches

1. Create `hooks/useSavedSearches.ts` (localStorage-backed)
2. Create `components/search/SavedSearchButton.tsx`
3. Create `components/search/SavedSearchDropdown.tsx`

### Step 5 — Detail page: static sections (RSC)

1. Update `app/[locale]/(protected)/listing/[id]/page.tsx` with `createServerApiClient`
2. Create `components/listing/PhotoGallery.tsx` with yarl
3. Create `components/listing/KeyStatsBar.tsx`
4. Create `components/listing/DealScoreCard.tsx`
5. Create `components/listing/ZoneStatsCard.tsx`
6. Create `components/listing/ListingMetadata.tsx`

### Step 6 — Detail page: charts

1. Create `components/listing/ShapChart.tsx` (Recharts horizontal BarChart)
2. Create `components/listing/PriceHistoryChart.tsx` (Recharts LineChart)

### Step 7 — Detail page: interactive sections (client components)

1. Create `components/listing/ListingMiniMap.tsx` (MapLibre, dynamic import)
2. Create `components/listing/ComparableCarousel.tsx` + `ComparableCard.tsx`
3. Create `components/listing/DescriptionSection.tsx` + `hooks/useTranslate.ts`
4. Create `components/listing/CrmActions.tsx` + `hooks/useCrmStatus.ts`
5. Create `components/listing/PrivateNotes.tsx` + `hooks/usePrivateNotes.ts`

### Step 8 — CRM store + badges on search cards

1. Create `stores/crmStore.ts`
2. Update `SearchListingCard.tsx` to show CRM badge from crmStore
3. Update `hooks/useInfiniteListings.ts` to bulk-load CRM status after page load

## 5. Testing

```bash
cd frontend
pnpm test        # Vitest unit tests
pnpm typecheck   # tsc --noEmit
pnpm lint        # Next.js ESLint
```

Key test cases to write:
- `useSearchParams.ts` — verify nuqs parsers round-trip all filter types
- `useInfiniteListings.ts` — mock API, verify cursor pagination
- `ShapChart.tsx` — verify top 5 selection and correct bar colors
- `PriceHistoryChart.tsx` — verify date formatting and single-point edge case
- `CrmActions.tsx` — verify optimistic update and rollback on error
- `PrivateNotes.tsx` — verify debounce behavior (no save during typing, save after 500ms)

## 6. Environment Variables

Add to `frontend/.env.local` if not already present:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8080
```

No new env vars are needed — translation and CRM endpoints are proxied through the existing API gateway.
