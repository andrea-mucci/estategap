# Quickstart: Dashboard Analytics & Interactive Map

**Feature**: `022-dashboard-analytics-map`  
**Date**: 2026-04-17

---

## Prerequisites

- Node 22 + `pnpm` (or `npm`) in `frontend/`
- Go 1.23 in `services/api-gateway/`
- Running PostgreSQL 16 + PostGIS 3.4 (local or forwarded via `kubectl port-forward`)
- Running Redis 7 (local or forwarded)

---

## 1. Install New Frontend Dependencies

```bash
cd frontend
npm install recharts @mapbox/mapbox-gl-draw @types/mapbox__mapbox-gl-draw
```

Verify additions in `package.json`:
```
recharts: ^2.x
@mapbox/mapbox-gl-draw: ^1.x
```

---

## 2. Regenerate API TypeScript Types

After the backend team adds the new endpoints to `services/api-gateway/openapi.yaml`, regenerate the frontend types:

```bash
cd frontend
npm run generate-api-types
# runs: openapi-typescript ../services/api-gateway/openapi.yaml -o src/types/api.ts
```

Verify new types appear in `frontend/src/types/api.ts`:
- `DashboardSummary`
- `ListingsGeoJSON` / `ListingGeoFeature`
- `ZoneGeometry`
- `CreateCustomZoneRequest`
- `latitude` / `longitude` on `ListingSummary`

---

## 3. Backend Changes (API Gateway)

Apply these changes to `services/api-gateway/`:

```bash
cd services/api-gateway
# After code changes:
go build ./...
go test ./...
```

**New files to create**:
- `internal/handler/dashboard.go` — `GetDashboardSummary` handler
- `internal/repository/dashboard.go` — Four COUNT queries + Redis caching

**Modified files**:
- `internal/handler/listings.go` — Add `bounds` + `format` query params; GeoJSON response path
- `internal/handler/zones.go` — Add `GetZoneGeometry` handler; Add `CreateCustomZone` handler
- `internal/repository/listings.go` — Add ST_MakeEnvelope bounds filter; Add ST_X/ST_Y coordinate extraction
- `internal/repository/zones.go` — Add `GetZoneGeometry()` with ST_AsGeoJSON; Add `CreateCustomZone()`
- `openapi.yaml` — Add all new endpoints and schema extensions from `contracts/api-extensions.yaml`

**New route registrations** in router setup (likely `cmd/server/main.go` or `internal/router/`):
```go
r.Get("/api/v1/dashboard/summary", h.GetDashboardSummary)
r.Get("/api/v1/zones/{id}/geometry", h.GetZoneGeometry)
r.Post("/api/v1/zones", h.CreateCustomZone)
```

---

## 4. Frontend File Structure

New files to create under `frontend/src/`:

```text
frontend/src/
├── app/[locale]/(protected)/dashboard/
│   └── page.tsx                          # REPLACE existing dashboard page
│
├── components/dashboard/
│   ├── SummaryCards.tsx                  # Four metric cards
│   ├── CountryTabs.tsx                   # Country filter tabs (synced to URL ?country=)
│   ├── TrendCharts.tsx                   # Recharts: line + bar + histogram
│   ├── PriceZoneChart.tsx                # Price/m² line chart by zone
│   ├── VolumeChart.tsx                   # Monthly listing volume bar chart
│   └── DealScoreHistogram.tsx            # Deal score distribution histogram
│
├── components/map/
│   ├── PropertyMap.tsx                   # Server-side wrapper (dynamic import guard)
│   ├── PropertyMapClient.tsx             # MapLibre GL JS client component
│   ├── ListingPopup.tsx                  # Mini listing card shown on marker click
│   ├── ZoneOverlayControl.tsx            # Toggle button for zone polygon layer
│   ├── DrawZoneControl.tsx               # Polygon draw tool + save modal
│   └── MapLayerToggle.tsx                # Markers / Heatmap toggle
│
├── hooks/
│   ├── useDashboardSummary.ts            # TanStack Query: GET /api/v1/dashboard/summary
│   ├── useZoneAnalytics.ts               # TanStack Query: GET /api/v1/zones/{id}/analytics
│   ├── useZoneList.ts                    # TanStack Query: GET /api/v1/zones?country=
│   ├── useZoneGeometry.ts                # TanStack Query: GET /api/v1/zones/{id}/geometry
│   ├── useMapListings.ts                 # TanStack Query: GET /api/v1/listings?format=geojson&bounds=
│   └── useCreateCustomZone.ts            # TanStack Mutation: POST /api/v1/zones
│
└── stores/
    └── dashboardStore.ts                 # Zustand: selectedCountry, mapMode, showZoneOverlay, drawingMode
```

---

## 5. Key Implementation Notes

### Dashboard Page Pattern

```typescript
// app/[locale]/(protected)/dashboard/page.tsx
// RSC: prefetch summary + countries for initial render
export default async function DashboardPage({ searchParams }: { searchParams: { country?: string } }) {
  const session = await requireSession();
  const country = searchParams.country ?? "ES";

  const queryClient = new QueryClient();
  await queryClient.prefetchQuery({
    queryKey: ["dashboard", "summary", country],
    queryFn: () => fetchDashboardSummary(session.accessToken, country),
  });
  await queryClient.prefetchQuery({
    queryKey: ["countries"],
    queryFn: () => fetchCountries(session.accessToken),
  });

  return (
    <HydrationBoundary state={dehydrate(queryClient)}>
      <DashboardClient country={country} />
    </HydrationBoundary>
  );
}
```

### Map Component Pattern

```typescript
// components/map/PropertyMap.tsx
// Dynamic import to prevent SSR of MapLibre GL JS
import dynamic from "next/dynamic";

const PropertyMapClient = dynamic(
  () => import("./PropertyMapClient"),
  { ssr: false, loading: () => <MapSkeleton /> }
);

export function PropertyMap({ country }: { country: string }) {
  return <PropertyMapClient country={country} />;
}
```

### Viewport Fetch with Debounce

```typescript
// In PropertyMapClient.tsx
const [bounds, setBounds] = useState<string | null>(null);

useEffect(() => {
  if (!map) return;
  const onMoveEnd = debounce(() => {
    const b = map.getBounds();
    setBounds(`${b.getWest()},${b.getSouth()},${b.getEast()},${b.getNorth()}`);
  }, 300);
  map.on("moveend", onMoveEnd);
  return () => map.off("moveend", onMoveEnd);
}, [map]);

const { data: geojson } = useMapListings(country, bounds);

// Update source when data changes:
useEffect(() => {
  if (!map || !geojson) return;
  const source = map.getSource("listings") as maplibregl.GeoJSONSource;
  source?.setData(geojson);
}, [map, geojson]);
```

### Deal Tier Marker Colors

```typescript
// MapLibre data-driven expression for circle-color:
"circle-color": [
  "match",
  ["get", "deal_tier"],
  1, "#22c55e",   // green-500 — Tier 1
  2, "#3b82f6",   // blue-500  — Tier 2
  3, "#9ca3af",   // gray-400  — Tier 3
  4, "#ef4444",   // red-500   — Tier 4
  "#9ca3af"       // fallback  — gray
]
```

### MapLibre Clustering Config

```typescript
map.addSource("listings", {
  type: "geojson",
  data: { type: "FeatureCollection", features: [] },
  cluster: true,
  clusterRadius: 50,
  clusterMaxZoom: 14,  // Stop clustering above zoom 14 (≈street level)
});

// Cluster circle layer
map.addLayer({
  id: "clusters",
  type: "circle",
  source: "listings",
  filter: ["has", "point_count"],
  paint: {
    "circle-color": "#0f766e",
    "circle-radius": ["step", ["get", "point_count"], 15, 10, 20, 50, 25],
  },
});

// Cluster count label
map.addLayer({
  id: "cluster-count",
  type: "symbol",
  source: "listings",
  filter: ["has", "point_count"],
  layout: { "text-field": "{point_count_abbreviated}", "text-size": 12 },
  paint: { "text-color": "#fff" },
});

// Individual marker layer (unclustered)
map.addLayer({
  id: "unclustered-point",
  type: "circle",
  source: "listings",
  filter: ["!", ["has", "point_count"]],
  paint: {
    "circle-color": ["match", ["get", "deal_tier"], 1, "#22c55e", 2, "#3b82f6", 3, "#9ca3af", 4, "#ef4444", "#9ca3af"],
    "circle-radius": 7,
    "circle-stroke-width": 1.5,
    "circle-stroke-color": "#fff",
  },
});
```

---

## 6. Running Locally

```bash
# Start the API gateway
cd services/api-gateway
go run ./cmd/server

# Start the frontend dev server
cd frontend
npm run dev

# Navigate to dashboard
open http://localhost:3000/en/dashboard?country=ES
```

Expected behavior:
- Dashboard loads with summary cards (may show zeros if DB is empty)
- Country tabs appear for countries returned by `/api/v1/countries`
- Map renders with OpenFreeMap tiles
- Markers appear as colored circles once listing data is in DB

---

## 7. Testing

```bash
# Frontend tests
cd frontend
npm test                     # Vitest unit tests
npm run type-check           # TypeScript strict check

# API gateway tests
cd services/api-gateway
go test ./internal/handler/... -v -run TestDashboard
go test ./internal/handler/... -v -run TestZoneGeometry
go test ./internal/handler/... -v -run TestCreateCustomZone
go test ./internal/repository/... -v -run TestBoundsFilter
```

Key test scenarios:
- `useDashboardSummary` hook returns correct data and refetches after 60s
- `useMapListings` fires on moveend with 300ms debounce
- Marker color matches `deal_tier` property (unit test on layer paint expression)
- Custom zone save sends correct POST body and shows zone in list
- Zone polygon toggle shows/hides fill layer
