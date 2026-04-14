# Feature: Dashboard & Interactive Map

## /plan prompt

```
Implement with these technical decisions:

## Dashboard (app/[locale]/(protected)/dashboard/page.tsx)
- React Server Component for initial data fetch (zone stats, country summaries)
- Client components for interactive charts (Recharts) and filters
- Data fetching: TanStack Query with 60s stale time for summary cards, 5min for charts
- Country tabs: URL param ?country=ES, default to user's first country

## Map (components/map/PropertyMap.tsx)
- MapLibre GL JS with free vector tiles (OpenFreeMap or PMTiles hosted on MinIO)
- GeoJSON source for listings: fetch from API /api/v1/listings?format=geojson&country=XX&bounds=SW_LNG,SW_LAT,NE_LNG,NE_LAT (viewport-filtered)
- Clustering: maplibre native clustering (clusterRadius: 50, clusterMaxZoom: 14)
- Marker colors: data-driven styling based on deal_tier property
- Popup: on click → fetch listing detail → render mini-card in Popup component
- Zone overlay: fetch zone geometries from API, render as fill-extrusion layer with opacity 0.2
- Draw tool: @mapbox/mapbox-gl-draw (compatible with MapLibre). On draw.create → save polygon via POST /api/v1/zones with type=custom
- Performance: limit GeoJSON to viewport bounds + buffer. Re-fetch on moveend event with debounce 300ms.
```
