# Feature: Listings & Zones API

## /specify prompt

```
Implement the REST API endpoints for listing search, listing detail, zones, countries, and portals.

## What
1. GET /api/v1/listings — Paginated search with 20+ filters: country, city, zone_id, property_category, property_type, min/max price (EUR or original currency), min/max area, bedrooms, bathrooms, deal_tier, status, source portal. Sort by: deal_score, price, price_m2, recency, days_on_market. Cursor-based pagination. Optional ?currency= param for price conversion. Subscription tier gating (free = listings > 48h old).
2. GET /api/v1/listings/{id} — Full detail: all fields, price_history, deal score + confidence, SHAP top 5, comparable listing IDs, zone stats summary.
3. GET /api/v1/zones — List by country, level, parent_id. Summary stats per zone.
4. GET /api/v1/zones/{id} — Detail with full stats.
5. GET /api/v1/zones/{id}/analytics — 12-month time series: price/m², volume, deal frequency.
6. GET /api/v1/zones/compare?ids=a,b,c — Side-by-side comparison (up to 5 zones, cross-country).
7. GET /api/v1/countries — Active countries with summary stats (listing count, deal count, portal count).
8. GET /api/v1/portals — Active portals with health metrics.

## Acceptance Criteria
- Listing search responds in < 500ms for 100k listings with complex filters
- Cursor pagination works correctly (no skipped/duplicate results)
- Currency conversion returns correct values with X-Currency and X-Exchange-Rate-Date headers
- Free tier users see only listings older than 48 hours
- Zone analytics returns 12 data points (monthly) for the past year
- Cross-country zone comparison works correctly with currency normalization
```
