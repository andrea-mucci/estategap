# Research: Listing Search & Detail Pages

**Phase**: 0 — Research  
**Date**: 2026-04-17  
**Feature**: 023-listing-search-detail

## 1. URL State Management with nuqs

**Decision**: Use `nuqs` v2 for type-safe URL search param management on the search page.

**Rationale**: The search page requires 15+ filter params in the URL for shareability. Native `useSearchParams()` + `useRouter()` requires manual string serialization/deserialization for every param type (booleans, arrays, numbers). nuqs provides: typed parsers per field (parseAsInteger, parseAsArrayOf, parseAsString), shallow routing (no server round-trip on filter change), and React 19 / Next.js 15 compatibility with the App Router. The existing codebase uses raw `searchParams.get()` only for simple single-value cases (country tab on dashboard) — nuqs is justified by the complexity of 15+ typed params.

**Alternatives Considered**:
- Native `useSearchParams` + manual serialization: Viable but error-prone at scale; every param needs custom encode/decode logic.
- Zustand + next/navigation: Clean state but breaks shareability — URL and Zustand diverge on direct navigation.

**Install**: `pnpm add nuqs` in `frontend/`

**Key usage pattern**:
```ts
const [country, setCountry] = useQueryState('country', parseAsString.withDefault('ES'))
const [dealTier, setDealTier] = useQueryState('deal_tier', parseAsArrayOf(parseAsInteger))
const [minPrice, setMinPrice] = useQueryState('min_price', parseAsInteger)
```

nuqs `NuqsAdapter` must be added to the root layout (Next.js App Router adapter is built-in).

---

## 2. Photo Gallery with yet-another-react-lightbox

**Decision**: Use `yet-another-react-lightbox` (yarl) v3 for the listing photo gallery.

**Rationale**: yarl is the most actively maintained React lightbox library with first-class mobile swipe support (via the `Zoom` and touch gesture plugins), keyboard navigation, and SSR compatibility. It supports: `slides` array of image URLs, `index` controlled state, `thumbnails` plugin for bottom strip, `Zoom` plugin for pinch-to-zoom on mobile, and `Captions` plugin. Bundle size is ~15KB gzipped.

**Alternatives Considered**:
- `react-image-gallery`: Older API, less active maintenance, no swipe-first design.
- Custom CSS scroll + modal: Too much custom code for edge cases (keyboard nav, focus trap, accessibility).
- `swiper`: Heavy (full carousel library) for a use case that only needs lightbox.

**Install**: `pnpm add yet-another-react-lightbox` in `frontend/`

**Key usage pattern**:
```tsx
import Lightbox from "yet-another-react-lightbox";
import Thumbnails from "yet-another-react-lightbox/plugins/thumbnails";
import Zoom from "yet-another-react-lightbox/plugins/zoom";

<Lightbox
  open={open}
  close={() => setOpen(false)}
  index={currentIndex}
  slides={photos.map(url => ({ src: url }))}
  plugins={[Thumbnails, Zoom]}
/>
```

---

## 3. TanStack Query v5 Infinite Scroll Pattern

**Decision**: Use `useInfiniteQuery` with `getNextPageParam` from cursor-based pagination. Append sentinel `IntersectionObserver` to trigger `fetchNextPage`.

**Rationale**: TanStack Query v5 changed the API: `keepPreviousData` → `placeholderData: keepPreviousData`. The existing `useListings` hook uses v5 correctly. For infinite scroll, `useInfiniteQuery` is the correct primitive — it manages page accumulation, loading states per page, and `hasNextPage`.

**Backend cursor**: The `ListingsResponse.pagination` field has `next_cursor` (string) and `has_more` (boolean). Pass `cursor` param to each subsequent page.

**Pattern**:
```ts
const { data, fetchNextPage, hasNextPage, isFetchingNextPage } = useInfiniteQuery({
  queryKey: ['listings', filters],
  queryFn: ({ pageParam }) => fetchListings(token, { ...filters, cursor: pageParam }),
  initialPageParam: undefined,
  getNextPageParam: (lastPage) =>
    lastPage.pagination.has_more ? lastPage.pagination.next_cursor : undefined,
  placeholderData: keepPreviousData,
})
```

**Sentinel pattern**:
```ts
const sentinelRef = useRef<HTMLDivElement>(null)
useEffect(() => {
  const observer = new IntersectionObserver(
    ([entry]) => { if (entry.isIntersecting && hasNextPage) fetchNextPage() },
    { rootMargin: '240px' }
  )
  if (sentinelRef.current) observer.observe(sentinelRef.current)
  return () => observer.disconnect()
}, [hasNextPage, fetchNextPage])
```

---

## 4. SHAP Chart with Recharts

**Decision**: Use Recharts `BarChart` in horizontal layout (layout="vertical") with custom cell colors.

**Rationale**: Recharts is already installed (v2.15.0). A horizontal bar chart directly maps SHAP values: positive values extend right (green), negative values extend left (red). The `Cell` component allows per-bar color based on value sign. `ReferenceLine` at x=0 provides the zero baseline.

**Data shape from API** (`shap_features` JSONB):
```ts
// Expected structure (to confirm with backend)
type ShapFeature = { feature: string; value: number; label: string }
// e.g. { feature: "area_m2", value: 12500, label: "Area (m²)" }
```

**Chart pattern**:
```tsx
<BarChart data={shapData} layout="vertical">
  <XAxis type="number" />
  <YAxis type="category" dataKey="label" width={120} />
  <ReferenceLine x={0} stroke="#666" />
  <Bar dataKey="value">
    {shapData.map((entry, i) => (
      <Cell key={i} fill={entry.value >= 0 ? '#22c55e' : '#ef4444'} />
    ))}
  </Bar>
</BarChart>
```

**Top 5 features**: Sort by `Math.abs(value)` descending, take first 5.

---

## 5. Recharts Price History LineChart

**Decision**: Use Recharts `LineChart` with `date-fns` for date formatting.

**Rationale**: Recharts is already installed. `price_history` is an array of `{date: string, price_eur: number}` from the `ListingDetail` type. `date-fns` is already installed (v4.1.0).

**Pattern**:
```tsx
<LineChart data={priceHistory}>
  <XAxis dataKey="date" tickFormatter={(d) => format(new Date(d), 'MMM yy')} />
  <YAxis tickFormatter={(v) => `€${(v/1000).toFixed(0)}k`} />
  <Tooltip formatter={(v) => `€${v.toLocaleString()}`} />
  <Line type="monotone" dataKey="price_eur" stroke="#3b82f6" dot={{ r: 4 }} />
</LineChart>
```

---

## 6. MapLibre Mini-Map for Detail Page

**Decision**: Reuse the existing MapLibre GL JS v4.7.1 setup. Create a new `ListingMiniMap` client component (dynamic import, `ssr: false`).

**Rationale**: The existing `PropertyMapClient.tsx` and `MapViewClient.tsx` demonstrate the correct pattern: dynamic import with `ssr: false`, map initialized in `useEffect` with `maplibregl.Map`, cleanup on unmount. The mini-map is simpler — single fixed marker + POI markers, no clustering.

**POI data**: The `ZoneDetail` type doesn't explicitly list POIs. The plan assumes POIs are available via `zone_stats` on `ListingDetail` or a separate `/api/v1/zones/{id}/pois` endpoint. This needs backend confirmation. **Fallback**: If POI data isn't available, the mini-map shows only the listing marker until the POI endpoint is added.

**POI icon approach**: Use Lucide React icons converted to SVG data URLs, or MapLibre `addImage` with custom SVG for metro (🚇), school (🏫), park (🌳) icons.

---

## 7. Saved Searches Storage Strategy

**Decision**: Dual-write — `localStorage` as primary fallback, API persistence for cross-device sync.

**Rationale**: The saved searches API endpoint doesn't exist yet. `localStorage` provides immediate functionality. When the API is available, `useSavedSearches` reads from API first (with TanStack Query), writes to both API and localStorage. If API fails, localStorage version is shown. This approach matches the user story requirement for cross-device persistence without blocking on backend work.

**localStorage key**: `estategap_saved_searches` (array of `SavedSearch` objects).

**TanStack Query keys**: `['saved-searches']` — invalidated on create/delete.

---

## 8. CRM Optimistic Updates

**Decision**: Use TanStack Query `useMutation` with `onMutate` / `onError` / `onSettled` for optimistic updates.

**Rationale**: CRM status must reflect immediately on click (SC-007: < 100ms). TanStack Query's optimistic update pattern: snapshot current data in `onMutate`, update cache immediately, revert on error in `onError`, revalidate in `onSettled`. The `crmStore` (Zustand) holds a local map of `listingId → CRMStatus` populated from query results, enabling search result cards to display CRM badges without re-fetching the full listing list.

**API endpoints needed** (new backend work):
- `PATCH /api/v1/listings/{id}/status` — body: `{ status: "favorite" | "contacted" | "visited" | "offer" | "discard" | null }`
- `PATCH /api/v1/listings/{id}/notes` — body: `{ notes: string }`
- `GET /api/v1/listings/{id}/crm` — returns `{ status, notes, updated_at }`

---

## 9. Translation via DeepL Proxy

**Decision**: Translation calls `POST /api/v1/translate` on the Go API gateway. The gateway proxies to DeepL API. Target language is derived from `navigator.language` (browser locale), mapped to DeepL language codes.

**Locale → DeepL mapping**: `en → EN-GB`, `es → ES`, `fr → FR`, `de → DE`, `it → IT`, `pt → PT-PT`, `nl → NL`, `pl → PL`, `sv → SV`, `el → EL`.

**Caching**: The Go gateway caches translations in Redis (key: `translate:{hash(text+lang)}`). Frontend does not cache translations — relies on gateway TTL.

**Loading state**: `useTranslate` mutation exposes `isPending` → show shadcn `Skeleton` over description text or a spinner inline with the button.

---

## 10. Dual-Range Slider

**Decision**: Build a custom dual-range slider using two overlapping HTML `<input type="range">` elements styled with Tailwind, or use `@radix-ui/react-slider` (already available via shadcn).

**Rationale**: shadcn's `Slider` component wraps `@radix-ui/react-slider` which supports `min`, `max`, `step`, and multi-thumb (array value). This is already in the project — no new dependency needed.

**Pattern**:
```tsx
<Slider
  min={0} max={5000000} step={10000}
  value={[minPrice, maxPrice]}
  onValueChange={([min, max]) => { setMinPrice(min); setMaxPrice(max) }}
/>
```

---

## 11. nuqs NuqsAdapter Setup

**Decision**: Add `<NuqsAdapter>` to `frontend/src/app/[locale]/layout.tsx` (the root layout), wrapping children alongside the existing `QueryProvider` and `AuthProvider`.

**Rationale**: nuqs requires an adapter for Next.js App Router. The `NuqsAdapter` from `nuqs/adapters/next/app` must wrap the component tree. It doesn't affect non-search pages.

```tsx
import { NuqsAdapter } from 'nuqs/adapters/next/app'

// In layout.tsx:
<NuqsAdapter>
  <QueryProvider>
    <AuthProvider>
      {children}
    </AuthProvider>
  </QueryProvider>
</NuqsAdapter>
```

---

## Summary of New Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `nuqs` | ^2.x | Type-safe URL search params |
| `yet-another-react-lightbox` | ^3.x | Photo gallery lightbox with swipe |

All other required libraries (Recharts, MapLibre, TanStack Query, Zustand, shadcn/ui, react-hook-form, Zod, date-fns) are **already installed**.
