# Research: Dashboard Analytics & Interactive Map

**Phase**: 0 — Research  
**Date**: 2026-04-17  
**Feature**: `specs/022-dashboard-analytics-map`

---

## 1. Recharts for Trend Charts

**Decision**: Use Recharts (latest v2.x) for all dashboard charts.

**Rationale**: Recharts is a React-native charting library built on D3, with composable APIs that fit naturally into the existing Next.js 15 / Tailwind CSS 4 stack. It supports all three required chart types (LineChart, BarChart, custom histogram via BarChart with binning). Has first-class TypeScript support and responsive containers.

**Alternatives considered**:
- Chart.js + react-chartjs-2: More manual DOM manipulation, less idiomatic React composition.
- Tremor charts: Abstraction layer adds opinionated styling that conflicts with the existing shadcn/ui design system.
- Visx (Airbnb): Too low-level; requires manual axis, tooltip, and legend implementation.

**Installation**: `recharts` package — not yet in frontend/package.json. Must be added.

---

## 2. @mapbox/mapbox-gl-draw Compatibility with MapLibre GL JS

**Decision**: Use `@mapbox/mapbox-gl-draw` v1.x for the polygon draw tool. Pin to version compatible with MapLibre GL JS 4.x.

**Rationale**: `@mapbox/mapbox-gl-draw` is the de-facto standard draw library and has documented compatibility with MapLibre GL JS. It exposes a `draw.create` event containing polygon GeoJSON coordinates on save, which maps directly to the POST /api/v1/zones request payload.

**Key compatibility notes**:
- MapLibre GL JS v4.x dropped the `mapboxgl` global; `mapbox-gl-draw` must be instantiated after the map is fully loaded.
- The draw control is attached via `map.addControl(new MapboxDraw({ ... }))`.
- On `draw.create` event: coordinates extracted from `event.features[0].geometry.coordinates[0]` and POSTed to the zones endpoint.
- The `displayControlsDefault: false` + `controls: { polygon: true, trash: true }` config is used for a minimal toolbar.

**Alternatives considered**:
- `maplibre-gl-draw`: Fork in early development; less community support and fewer active maintainers.
- Custom polygon drawing with click handlers: Significantly more complex mouse/touch state management; draw library handles edge cases (double-click to close, snap to first point, etc.).

**Installation**: `@mapbox/mapbox-gl-draw` and `@types/mapbox__mapbox-gl-draw` — not yet installed. Must be added.

---

## 3. Vector Tiles for Base Map

**Decision**: Use OpenFreeMap vector tiles (`https://tiles.openfreemap.org/styles/liberty`) as the map base style.

**Rationale**: OpenFreeMap provides free, open-licensed vector tiles based on OpenStreetMap data with zero API key requirement. The "liberty" style uses Maplibre-native GL expressions and renders well at all zoom levels. This is production-ready and avoids the Mapbox token requirement (MapLibre already used in the codebase, but the current base map is the demo tile set `demotiles.maplibre.org/style.json` which is not suitable for production).

**Alternatives considered**:
- PMTiles hosted on MinIO: Requires operational setup (tile generation, MinIO serving, TileJSON configuration). Good for self-hosted sovereignty, but adds infra complexity out of scope for this feature. Noted as future upgrade path.
- Protomaps CDN: Another valid zero-config option, but OpenFreeMap has more complete coverage and better styling.
- Mapbox GL tiles: Requires Mapbox account and token; conflicts with the open-source-first MapLibre choice.

---

## 4. Viewport-Bounded GeoJSON Listing Fetch

**Decision**: Add `bounds` query parameter to `GET /api/v1/listings` in the API gateway. The parameter accepts `SW_LNG,SW_LAT,NE_LNG,NE_LAT` (comma-separated floats). The backend adds a PostGIS `ST_MakeEnvelope` filter on the `location` geometry column.

**Rationale**: Fetching all listings for a country (potentially 50k+) as GeoJSON is prohibitive. Viewport-bounded queries constrain the response to what is currently visible + a 20% buffer. Combined with maplibre native clustering, this enables smooth performance even for dense markets.

**Key implementation details**:
- PostGIS query: `WHERE ST_Intersects(location, ST_MakeEnvelope($minLng, $minLat, $maxLng, $maxLat, 4326))`
- Bounds param format (same as Mapbox conventions): `bounds=minLng,minLat,maxLng,maxLat`
- Buffer: Apply 10–20% geographic buffer on the backend to avoid marker pop-in at edges.
- GeoJSON response format: `{ "type": "FeatureCollection", "features": [...] }` where each feature is `{ "type": "Feature", "geometry": { "type": "Point", "coordinates": [lng, lat] }, "properties": { "id": "...", "deal_tier": 1, "price_eur": 250000, "deal_score": 85, "address": "...", "photo_url": "..." } }`.
- Listing records that have NULL `location` are excluded from the GeoJSON response.

**Alternatives considered**:
- Separate `/api/v1/listings/geojson` endpoint: Creates an endpoint maintenance burden; the bounds param is cleaner and additive.
- Tile server (MVT): Optimal for very large datasets but requires a tile-serving infrastructure layer. Out of scope for this feature iteration.

---

## 5. Dashboard Summary Stats API

**Decision**: Add `GET /api/v1/dashboard/summary?country=XX` endpoint to the API gateway. Returns aggregated stats for the summary cards.

**Rationale**: The existing `GET /api/v1/listings` endpoint returns paginated listing items, not aggregated metrics. Computing "total listings", "new today", "Tier 1 deals today", and "recent price drops" requires COUNT queries with different filter predicates. Combining these into one endpoint minimizes round trips and enables server-side caching in Redis (TTL: 60 seconds per country).

**Response shape**:
```json
{
  "country": "ES",
  "total_listings": 12847,
  "new_today": 342,
  "tier1_deals_today": 18,
  "price_drops_7d": 204,
  "last_refreshed_at": "2026-04-17T10:30:00Z"
}
```

**SQL approach**:
- `total_listings`: `SELECT COUNT(*) FROM listings WHERE country=$1 AND status='active'`
- `new_today`: `SELECT COUNT(*) FROM listings WHERE country=$1 AND status='active' AND first_seen_at >= NOW() - INTERVAL '1 day'`
- `tier1_deals_today`: `SELECT COUNT(*) FROM listings WHERE country=$1 AND deal_tier=1 AND first_seen_at >= NOW() - INTERVAL '1 day'`
- `price_drops_7d`: `SELECT COUNT(DISTINCT listing_id) FROM price_history WHERE country=$1 AND change_type='price_change' AND new_price_eur < old_price_eur AND recorded_at >= NOW() - INTERVAL '7 days'`

**Caching**: Redis key `dashboard:summary:{country}` with 60s TTL.

---

## 6. Zone Geometry Endpoint

**Decision**: Add `GET /api/v1/zones/{id}/geometry` endpoint returning the zone's GeoJSON polygon.

**Rationale**: The existing `GET /api/v1/zones/{id}` endpoint returns zone stats but not the geometry. Map rendering requires GeoJSON. A separate endpoint for geometry avoids polluting the zone list responses with large geometry payloads.

**Response shape**:
```json
{
  "zone_id": "uuid",
  "zone_name": "Salamanca",
  "geometry": {
    "type": "MultiPolygon",
    "coordinates": [...]
  },
  "bbox": [minLng, minLat, maxLng, maxLat]
}
```

**SQL approach**:
```sql
SELECT id, name, ST_AsGeoJSON(geometry)::json AS geometry, ST_AsGeoJSON(bbox)::json AS bbox
FROM zones
WHERE id = $1
```

**Caching**: Redis key `zone:geometry:{id}` with 5-minute TTL (geometry rarely changes).

---

## 7. Custom Zone POST Endpoint

**Decision**: Add `POST /api/v1/zones` endpoint with `type=custom` body parameter for user-created zones.

**Rationale**: The existing zones table supports custom/user-created zones via the `parent_id` / `level` hierarchy but has no API endpoint for creation. The draw tool needs a backend to persist polygons.

**Request body**:
```json
{
  "name": "My Zone",
  "type": "custom",
  "country": "ES",
  "geometry": {
    "type": "Polygon",
    "coordinates": [[[lng, lat], ...]]
  }
}
```

**Authorization**: Requires authenticated user. Zone is created with `user_id` set to the requesting user. Only `custom` type zones can be created by regular users; internal zone levels (0–4) are admin-only.

---

## 8. Listing Coordinates in API Response

**Decision**: Add `latitude` and `longitude` fields (nullable floats) to `ListingSummary` schema in the OpenAPI spec, populated from the PostGIS `location` point column.

**Rationale**: The current `ListingSummary` schema does not expose coordinates. The existing `MapViewClient.tsx` workaround reads from a `ListingCard` type in the chat module that has `longitude`/`latitude` fields. For the map, coordinates need to be in the standard listing response.

**SQL extraction**: `ST_X(location) AS longitude, ST_Y(location) AS latitude`

**Note**: Both fields are nullable. Listings without a geocoded address will have null coordinates and must be excluded from map rendering.

---

## 9. Recharts Histogram Implementation

**Decision**: Implement the deal score histogram by bucketing `deal_score` values into bins of 10 (0-9, 10-19, ..., 90-100) client-side, then rendering with `<BarChart>`.

**Rationale**: The API does not provide a pre-computed distribution. The listings endpoint with `sort_by=deal_score` returns up to 100 items per page; multiple pages can be fetched on initial load (up to 500-1000 items) and binned client-side using a simple array reduce. This avoids a new backend endpoint and is acceptable for visual accuracy.

**Fallback**: If the user has a large dataset (>1000 listings for a country), the histogram shows approximate distribution from the first two pages with a note "Based on top 200 listings by deal score".

---

## 10. Mobile Map Interaction

**Decision**: MapLibre GL JS natively supports touch gestures (pinch-to-zoom, drag-to-pan) with no additional configuration. The draw tool requires an explicit touch-events configuration.

**Rationale**: MapLibre GL JS is designed with mobile support in mind and handles touch events out of the box. `@mapbox/mapbox-gl-draw` v1.4+ has touch event support for drawing polygons on mobile.

**Responsive layout**:
- On mobile (<768px): Map takes full viewport height; charts collapse to single-column stacked layout; country tabs scroll horizontally.
- On desktop: Map is half-page in a two-column split with the chart panel.
