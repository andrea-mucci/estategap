# Feature: Listings Search & Detail Pages

## /plan prompt

```
Implement with these technical decisions:

## Search Page (app/[locale]/(protected)/search/page.tsx)
- Filter state in URL search params (nuqs library for type-safe URL state)
- Sidebar: shadcn form components (Select, Slider, Checkbox, Input with autocomplete)
- City autocomplete: debounced API call to /api/v1/zones?level=city&q=search_term
- Results: TanStack Query with keepPreviousData for smooth pagination
- Infinite scroll: IntersectionObserver on sentinel element → fetch next page
- View toggle: grid (3 columns desktop, 1 mobile) vs list (full width rows)
- Saved searches: localStorage for quick access + API persistence for cross-device

## Detail Page (app/[locale]/(protected)/listing/[id]/page.tsx)
- React Server Component: fetch listing detail on server (SSR for SEO)
- Photo gallery: yet-another-react-lightbox (mobile swipe support)
- SHAP chart: Recharts horizontal BarChart. Positive values green (right), negative red (left). Labels from shap_features JSONB.
- Price history: Recharts LineChart with data from price_history array. X-axis: date, Y-axis: price.
- Comparables: horizontal scroll cards with mini listing info. Link to their detail pages.
- Mini-map: MapLibre with single marker + POI markers (metro icon, school icon, park icon). Fetched from zone POI data.
- Translate: onClick → POST /api/v1/translate {text, target_lang}. API calls DeepL, caches result. Show loading spinner during translation.
- CRM actions: shadcn ToggleGroup buttons. PATCH /api/v1/listings/{id}/status {status: "favorite"}. Optimistic update via TanStack Query.
- Notes: shadcn Textarea with auto-save debounce (500ms). PATCH /api/v1/listings/{id}/notes.
```
