# Feature: Normalizer & Deduplicator

## /specify prompt

```
Build the data pipeline services that transform raw scraped data into normalized, deduplicated listings.

## What
1. Normalizer (Python): NATS consumer on raw.listings.*. For each raw listing: (a) map portal-specific field names to unified schema using per-portal mapping config, (b) normalize currency to EUR using exchange_rates table, (c) normalize area to m², (d) map property type to canonical taxonomy, (e) validate all fields with Pydantic (reject invalid data to quarantine), (f) compute data_completeness score (% fields populated), (g) write to PostgreSQL listings table, (h) publish to NATS normalized.listings.

2. Deduplicator (Python): NATS consumer on normalized.listings. Three-stage matching: (a) PostGIS ST_DWithin(location, 50m) for GPS proximity candidates, (b) feature similarity check (area ±10%, same room count, same type), (c) rapidfuzz Levenshtein on normalized address (threshold >85%). Matching listings get the same canonical_id. Both source records kept. Publishes to next queue.

## Acceptance Criteria
- Idealista raw listing → correct normalized row in DB with all fields mapped
- Currency conversion accurate (verified against ECB rates)
- sqft correctly converted to m² for US listings
- France "pièces" correctly mapped to bedrooms (pièces - 1)
- Invalid listings (price=0, no location) quarantined, not in DB
- Two identical listings from Idealista + Fotocasa merged under same canonical_id
- False positive dedup rate < 5% on 1000-listing test set
- Pipeline throughput: 100 listings/second sustained
```
