# Data Model: Listing Search & Detail Pages

**Phase**: 1 — Design  
**Date**: 2026-04-17  
**Feature**: 023-listing-search-detail

## Overview

This feature is entirely frontend-facing. No new database tables are introduced. All data shapes are derived from the existing OpenAPI-generated `types/api.ts` and three new API endpoint contracts (saved searches, CRM, translate) that will be added to the Go API gateway.

---

## 1. Search Filter Params (`ListingSearchParams`)

The canonical type for URL-serialized filter state. Maps 1:1 to the existing `ListingsQuery` from `types/api.ts` plus sort params.

```ts
// Derived from existing ListingsQuery — no changes to generated types
interface ListingSearchParams {
  country: string           // default: 'ES'
  city?: string             // free text, used for autocomplete
  zone_id?: string          // UUID
  property_category?: 'residential' | 'commercial' | 'industrial' | 'land'
  property_type?: string    // sub-type within category
  min_price_eur?: number
  max_price_eur?: number
  min_area_m2?: number
  max_area_m2?: number
  min_bedrooms?: number     // 1-5, where 5 means "5+"
  deal_tier?: number[]      // [1, 2, 3, 4] multi-select
  status?: ('active' | 'delisted' | 'price_changed')[]
  source_portal?: string[]  // portal slugs
  sort_by?: 'deal_score' | 'price' | 'price_m2' | 'recency' | 'days_on_market'
  sort_dir?: 'asc' | 'desc'
  // pagination managed by useInfiniteQuery — not in URL params
}
```

**nuqs parsers** (in `hooks/useSearchParams.ts`):
```ts
const searchParamsParsers = {
  country: parseAsString.withDefault('ES'),
  city: parseAsString,
  zone_id: parseAsString,
  property_category: parseAsStringLiteral(['residential', 'commercial', 'industrial', 'land'] as const),
  min_price_eur: parseAsInteger,
  max_price_eur: parseAsInteger,
  min_area_m2: parseAsInteger,
  max_area_m2: parseAsInteger,
  min_bedrooms: parseAsInteger,
  deal_tier: parseAsArrayOf(parseAsInteger),
  status: parseAsArrayOf(parseAsString),
  source_portal: parseAsArrayOf(parseAsString),
  sort_by: parseAsString.withDefault('deal_score'),
  sort_dir: parseAsString.withDefault('desc'),
}
```

---

## 2. Saved Search

New entity — persisted server-side via new API endpoint, with `localStorage` fallback.

```ts
interface SavedSearch {
  id: string                    // UUID (server-generated) or nanoid (localStorage)
  name: string                  // user-provided label
  filters: ListingSearchParams  // snapshot of filter state at save time
  created_at: string            // ISO 8601
  updated_at: string            // ISO 8601
}
```

**localStorage schema** (`estategap_saved_searches`): `SavedSearch[]`

---

## 3. CRM Entry

New entity — per-user, per-listing pipeline state.

```ts
type CrmStatus = 'favorite' | 'contacted' | 'visited' | 'offer' | 'discard' | null

interface CrmEntry {
  listing_id: string    // UUID
  status: CrmStatus     // null = no CRM action taken
  notes: string         // private notes text, empty string if none
  updated_at: string    // ISO 8601
}
```

---

## 4. SHAP Feature (from existing `ListingDetail.shap_features`)

The `shap_features` field is a JSONB object. Based on ML feature naming conventions:

```ts
// Inferred structure from ML scorer (feature-015)
interface ShapFeatures {
  [featureKey: string]: number  // raw SHAP value
  // e.g. { "area_m2": 12500, "distance_metro_m": -8200, "floor": 3100, ... }
}
```

The frontend maps feature keys to human-readable labels:

```ts
const SHAP_LABELS: Record<string, string> = {
  area_m2: 'Area (m²)',
  price_per_m2: 'Price per m²',
  distance_metro_m: 'Metro distance',
  distance_school_m: 'School distance',
  distance_park_m: 'Park distance',
  floor_number: 'Floor',
  year_built: 'Year built',
  bedrooms: 'Bedrooms',
  bathrooms: 'Bathrooms',
  zone_median_price: 'Zone median price',
  // ... extended as more features are confirmed
}
```

**Top 5 selection**: Sort by `Math.abs(value)` descending, take first 5 entries.

**Chart data shape**:
```ts
interface ShapChartPoint {
  label: string    // human-readable from SHAP_LABELS
  value: number    // raw SHAP EUR value
}
```

---

## 5. Price History (from existing `ListingDetail.price_history`)

```ts
// From generated types/api.ts — confirmed existing
interface PriceHistoryPoint {
  date: string       // ISO 8601 date string, e.g. "2025-11-15"
  price_eur: number  // price at that date in EUR
}
```

---

## 6. Zone Statistics (from existing `ListingDetail.zone_stats`)

```ts
// From ZoneDetail — confirmed existing
interface ZoneStats {
  zone_id: string
  zone_name: string
  median_price_m2_eur: number
  listing_count: number
  deal_count: number
  price_trend_pct: number   // percentage change, positive = rising
}
```

---

## 7. POI (Points of Interest for Mini-Map)

POI data is expected from the zone. Exact structure needs backend confirmation.

```ts
// Assumed structure — confirm with /api/v1/zones/{id} response
interface POI {
  name: string
  lat: number
  lng: number
  type: 'metro' | 'school' | 'park'
}
```

If `ListingDetail.zone_stats` does not include POIs, a separate GET to `/api/v1/zones/{zone_id}/pois` will be used (new endpoint). Fallback: mini-map shows only the listing marker if POIs are unavailable.

---

## 8. CRM Store (Zustand — client-side cache)

```ts
// stores/crmStore.ts
interface CrmStore {
  entries: Record<string, CrmStatus>  // listingId → CRMStatus
  setStatus: (listingId: string, status: CrmStatus) => void
  bulkLoad: (entries: CrmEntry[]) => void  // called after listings query
}
```

The search results page bulk-loads CRM status for all visible listing IDs after the initial listings query resolves, enabling badge display on cards without per-card requests.

---

## 9. Search UI Store (Zustand — client-side UI state)

```ts
// stores/searchStore.ts
interface SearchStore {
  viewMode: 'grid' | 'list'
  isSidebarOpen: boolean   // mobile drawer state
  setViewMode: (mode: 'grid' | 'list') => void
  toggleSidebar: () => void
  closeSidebar: () => void
}
```

---

## State Flow Diagram

```
URL Search Params (nuqs)
    ↓
useSearchParams.ts (typed parsers)
    ↓
useInfiniteListings.ts (TanStack Query)
    ↓
GET /api/v1/listings?{params}&cursor=...
    ↓
ListingSummary[] (existing type)
    ↓
SearchResultsGrid / SearchResultsList
    + CRM badges from crmStore.entries

----

RSC: /listing/[id]/page.tsx
    ↓
createServerApiClient() → GET /api/v1/listings/{id}
    ↓
ListingDetail (existing type)
    ↓
ListingDetailPage (client wrapper)
    ├── PhotoGallery (yarl)
    ├── KeyStatsBar
    ├── DealScoreCard
    ├── ShapChart (Recharts — from shap_features)
    ├── PriceHistoryChart (Recharts — from price_history)
    ├── ComparableCarousel (useComparables hook)
    ├── ZoneStatsCard (from zone_stats)
    ├── ListingMiniMap (MapLibre — from lat/lng + POIs)
    ├── DescriptionSection (useTranslate mutation)
    ├── ListingMetadata
    ├── CrmActions (useCrmStatus mutation)
    └── PrivateNotes (usePrivateNotes debounced mutation)
```
