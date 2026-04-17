# Data Model: Dashboard Analytics & Interactive Map

**Phase**: 1 — Design  
**Date**: 2026-04-17  
**Feature**: `specs/022-dashboard-analytics-map`

---

## New & Extended Entities

### 1. DashboardSummary (new)

Aggregated per-country metrics for the four summary cards. Computed server-side from the `listings` and `price_history` tables.

| Field | Type | Notes |
|-------|------|-------|
| `country` | `string` | ISO country code (PK for caching) |
| `total_listings` | `number` | COUNT of active listings for country |
| `new_today` | `number` | Active listings with `first_seen_at >= NOW() - 1d` |
| `tier1_deals_today` | `number` | Active listings where `deal_tier = 1` and `first_seen_at >= NOW() - 1d` |
| `price_drops_7d` | `number` | Distinct listings with a price decrease in `price_history` in last 7 days |
| `last_refreshed_at` | `string` (ISO 8601) | Timestamp of last cache refresh |

**Source**: Derived query against `listings` + `price_history` tables, cached in Redis at key `dashboard:summary:{country}` with 60s TTL.

---

### 2. ListingSummary (extended)

Two new nullable fields added to the existing `ListingSummary` schema.

| New Field | Type | Notes |
|-----------|------|-------|
| `latitude` | `number \| null` | WGS84 latitude extracted from PostGIS `location` point |
| `longitude` | `number \| null` | WGS84 longitude extracted from PostGIS `location` point |

Listings with null coordinates are valid and included in paginated responses but excluded from map rendering.

**Source**: `ST_Y(location)` / `ST_X(location)` from the `listings` table. Already stored; needs SQL extraction and OpenAPI schema addition.

---

### 3. ListingGeoFeature (new — GeoJSON shape)

A GeoJSON Feature representing a single listing for map rendering. Returned by the listings endpoint when viewport bounds are provided.

```json
{
  "type": "Feature",
  "geometry": {
    "type": "Point",
    "coordinates": [-3.7038, 40.4168]
  },
  "properties": {
    "id": "uuid",
    "deal_tier": 1,
    "deal_score": 88,
    "asking_price_eur": 275000,
    "area_m2": 90,
    "address": "Calle Gran Vía 12, Madrid",
    "photo_url": "https://cdn.../photo.jpg",
    "city": "Madrid",
    "property_type": "apartment"
  }
}
```

**Included in**: `FeatureCollection` response body when `bounds` query param is present and `format=geojson` is set on `GET /api/v1/listings`.

---

### 4. ZoneGeometry (new)

GeoJSON geometry for a zone boundary. Returned by `GET /api/v1/zones/{id}/geometry`.

| Field | Type | Notes |
|-------|------|-------|
| `zone_id` | `string` (UUID) | Zone identifier |
| `zone_name` | `string` | Human-readable zone name |
| `geometry` | GeoJSON `MultiPolygon` | Zone boundary polygon(s) in WGS84 (EPSG:4326) |
| `bbox` | `[minLng, minLat, maxLng, maxLat]` | Bounding box as flat array for MapLibre `fitBounds()` |

**Source**: `ST_AsGeoJSON(zones.geometry)` and `ST_AsGeoJSON(zones.bbox)` via PostGIS. Cached in Redis at `zone:geometry:{id}` with 5-minute TTL.

---

### 5. CustomZone (new — user-created)

A zone record created by a user via the draw tool. Stored in the existing `zones` table with a `user_id` linkage.

| Field | Type | Notes |
|-------|------|-------|
| `id` | `string` (UUID) | Generated on creation |
| `name` | `string` | User-assigned name (max 100 chars) |
| `type` | `"custom"` | Distinguishes from system-generated zones |
| `country` | `string` | ISO country code inferred from polygon centroid |
| `level` | `5` | Synthetic level for custom zones (system levels are 0–4) |
| `geometry` | GeoJSON `Polygon` | User-drawn polygon in WGS84 |
| `user_id` | `string` (UUID) | Owner of this custom zone |
| `created_at` | `string` (ISO 8601) | Creation timestamp |

**Validation rules**:
- Polygon must be closed (first and last coordinates identical).
- Polygon must be valid (non-self-intersecting) — enforced via `ST_IsValid()` PostGIS check.
- Name: 1–100 characters, non-empty.
- Maximum custom zones per user: 20 (enforced by subscription tier logic, configurable).

---

### 6. ZoneAnalyticsSeries (existing — chart data shape)

Already defined in the OpenAPI spec. Used by Recharts line and bar charts. Documented here for reference.

| Field | Type | Notes |
|-------|------|-------|
| `zone_id` | `string` | Zone UUID |
| `months` | `MonthlyDataPoint[]` | 12-entry array, one per month (most recent last) |

**MonthlyDataPoint**:

| Field | Type | Notes |
|-------|------|-------|
| `month` | `string` (ISO 8601) | First day of the month, e.g., `"2025-05-01T00:00:00Z"` |
| `listing_count` | `number` | Listings active in that month |
| `median_price_m2_eur` | `number` | Median price/m² for that month |
| `deal_count` | `number` | Tier 1+2 deal count for that month |

---

## Entity Relationships

```text
User (NextAuth session)
  └─owns─► CustomZone (zones table, level=5)

Country (tab selection)
  └─scopes─► DashboardSummary
  └─scopes─► ZoneAnalyticsSeries (one series per zone in country)
  └─scopes─► ListingGeoFeature[] (viewport-filtered)

Zone (predefined system zone)
  └─has─► ZoneGeometry (polygon overlay on map)
  └─has─► ZoneAnalyticsSeries (charts)
  └─contains─► Listing[] (listings whose location intersects zone)

Listing
  └─extends─► ListingSummary (now with lat/lng)
  └─represents─► ListingGeoFeature (map marker)
```

---

## State Transitions

### Custom Zone Lifecycle

```text
DRAWING → (user completes polygon) → DRAWN → (user names + saves) → SAVED
DRAWING → (user cancels) → [discarded]
SAVED → (user deletes) → [removed from DB]
```

### Map Layer Toggle States

```text
Markers mode (default)
  ├─ zoom < 12: Clustered markers
  └─ zoom ≥ 12: Individual color-coded markers

Heatmap mode (user toggle)
  └─ All markers hidden, heatmap layer visible

Zone Overlay (independent toggle)
  ├─ ON: Zone polygons visible alongside current marker/heatmap mode
  └─ OFF: Zone polygons hidden
```

---

## Zustand Store Extensions

### New: `dashboardStore.ts`

Manages the country tab selection (synced with URL param) and the map layer toggle state.

| State Field | Type | Notes |
|-------------|------|-------|
| `selectedCountry` | `string` | ISO country code, e.g., `"ES"` |
| `mapMode` | `"markers" \| "heatmap"` | Current map visualization mode |
| `showZoneOverlay` | `boolean` | Zone polygon overlay visibility |
| `drawingMode` | `boolean` | Whether the draw tool is active |

**Actions**: `setCountry(code)`, `setMapMode(mode)`, `toggleZoneOverlay()`, `setDrawingMode(active)`

---

## TanStack Query Keys

| Hook | Query Key | Stale Time |
|------|-----------|------------|
| `useDashboardSummary(country)` | `["dashboard", "summary", country]` | 60s |
| `useZoneAnalytics(zoneId)` | `["zones", zoneId, "analytics"]` | 5min |
| `useZoneList(country)` | `["zones", "list", country]` | 5min |
| `useZoneGeometry(zoneId)` | `["zones", zoneId, "geometry"]` | 10min |
| `useMapListings(country, bounds)` | `["listings", "map", country, bounds]` | 30s |
| `useCountries()` | `["countries"]` | 10min |
