# Feature: Enricher & Change Detector

## /plan prompt

```
Implement with these technical decisions:

## Enricher (services/pipeline/enricher/)
- BaseEnricher interface: enrich(listing: NormalizedListing) → EnrichmentResult
- Plugin registry: dict mapping country → list[EnricherClass]
- SpainCatastroEnricher: calls Catastro WFS endpoint via httpx. Parse GML/XML response. Extract: cadastral_ref, built_area, year_built, building_geometry (WKT). Rate limit: asyncio.Semaphore(1) for 1 req/s.
- POI distance calculator: load POI data from OpenStreetMap (pre-downloaded PBF file parsed with osmium, stored in PostGIS table). For each listing: query nearest POI per category using PostGIS ST_Distance.
- Pre-load POI for active countries: metro stations, train stations, airports, parks (leisure=park), beaches (natural=beach).
- Fallback: if no pre-loaded POI data, use Overpass API with 5s cache per zone.

## Change Detector (services/pipeline/change_detector/)
- Triggered by scrape-orchestrator via NATS event scraper.cycle.completed.{country}.{portal}
- Query: SELECT id, asking_price, status FROM listings WHERE source = $1 AND country = $2 AND status = 'active'
- Compare with scraped listing IDs from current cycle (passed in event or queried from DB by last_seen_at)
- Price change: if asking_price differs → INSERT INTO price_history, UPDATE listing asking_price
- Delisting: if listing not in current scrape → UPDATE status = 'delisted', delisted_at = NOW()
- Re-listing: if previously delisted listing found in scrape → UPDATE status = 'active', delisted_at = NULL
- Publish price drops to price.changes NATS stream with: listing_id, old_price, new_price, drop_percentage
```
