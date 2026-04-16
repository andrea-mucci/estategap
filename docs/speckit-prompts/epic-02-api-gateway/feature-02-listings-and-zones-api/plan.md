# Feature: Listings & Zones API

## /plan prompt

```
Implement the listings and zones API with these technical decisions:

## Query Strategy
- All read queries go to the PostgreSQL read replica via a separate pgx pool
- Listing search: build dynamic SQL with parameterized filters. Use PostGIS ST_Within for zone filtering. Cursor pagination using (deal_score, id) or (created_at, id) composite cursor.
- Zone stats: read from materialized view zone_statistics for fast responses
- Zone analytics: aggregate from price_history with date_trunc('month', recorded_at)
- Currency conversion: join with exchange_rates table, multiply in SQL

## Caching (Redis)
- Zone statistics: cache per zone_id with TTL 5min
- Top deals: cache per country with TTL 1min
- Country summaries: cache with TTL 15min
- Cache key pattern: "cache:{entity}:{id}:{hash_of_params}"

## Subscription Gating
- Middleware checks user tier from JWT claims
- Free tier: add WHERE first_seen_at < NOW() - INTERVAL '48 hours' to listing queries
- Basic: no delay, but limited countries (checked against user's allowed countries list)
- Pro+: full access

## Response Format
- Envelope: { "data": [...], "pagination": { "next_cursor": "...", "has_more": true }, "meta": { "total_count": 1234, "currency": "EUR" } }
- Listing summary (search results): subset of fields (id, source, address, city, country, price, price_eur, price_m2, area, rooms, type, deal_score, deal_tier, photo_url, days_on_market)
- Listing detail: all fields + nested price_history, shap_features, comparables
```
