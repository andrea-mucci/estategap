# Feature: Enricher & Change Detector

## /specify prompt

```
Build the enrichment service (cadastral data + POI distances) and the change detection service.

## What
1. Enricher (Python): pluggable enrichment with BaseEnricher interface. Launch implementation: SpainCatastroEnricher (calls Catastro INSPIRE WFS for cadastral reference, official area, year, building geometry. Flags area discrepancy >10%). POI distance calculator: computes Haversine distance to nearest metro station, city center, coastline, green area using OpenStreetMap Overpass API or pre-loaded POI database. Updates listing in DB. Publishes to enriched.listings NATS stream.

2. Change Detector (Python): runs after each scraping cycle. Compares current listing data with previous snapshot. Detects: price drops (>0 change → insert price_history row), delistings (listing not seen in latest scrape → set delisted_at), re-listings (previously delisted listing reappears), description changes. Publishes price drops to price.changes NATS stream for alert engine consumption.

## Acceptance Criteria
- 80%+ Madrid listings enriched with Catastro data
- Area discrepancy flag correctly set when portal area differs >10% from official
- POI distances within ±200m of Google Maps verified for 10 samples
- Price drop of €10k detected and recorded in price_history
- Delisting detected within one scraping cycle
- No false positives on unchanged listings
- Enrichment respects API rate limits (1 req/s for Catastro)
```
