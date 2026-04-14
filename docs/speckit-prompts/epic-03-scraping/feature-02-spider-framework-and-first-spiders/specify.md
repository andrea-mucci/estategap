# Feature: Spider Framework & First Portal Spiders

## /specify prompt

```
Build the Python spider worker framework and implement the first two portal spiders (Idealista and Fotocasa for Spain).

## What
1. Spider Worker Framework (Python): base class BaseSpider with abstract methods scrape_search_page(zone, page), scrape_listing_detail(url), detect_new_listings(zone, since). NATS consumer subscribing to scraper.commands.{country}.{portal}. Dynamic spider loading from registry. gRPC client to proxy-manager for proxy assignment. Publishes raw listings to NATS raw.listings.{country}. Error handling: retry 3x with backoff, quarantine permanently failed URLs. Metrics: listings_scraped_total, scrape_errors_total, scrape_duration_seconds.

2. Idealista Spain Spider: scrapes idealista.com search pages (paginated), listing detail pages. Extracts all fields from the unified schema: price, area, rooms, bathrooms, floor, elevator, parking, terrace, orientation, condition, year built, energy cert, GPS coordinates, photos, description, agent info. Handles: mobile API reverse-engineering (JSON endpoints), HTML fallback with parsel/CSS selectors, anti-bot (Playwright for JS-rendered pages).

3. Fotocasa Spain Spider: same scope for fotocasa.es. Different HTML structure and API endpoints.

4. New listing detection: poll search results sorted by newest every 15min, compare with last-seen listing IDs (Redis set per zone), scrape only new ones.

## Acceptance Criteria
- Framework loads spiders dynamically. Adding a new spider requires only one Python file.
- Idealista spider scrapes 100+ listings with >80% data completeness (fields populated)
- Fotocasa spider same criteria
- No IP blocks during 500-request test run with proxies
- New listings detected within 15min of publication
- Raw listings published to NATS with correct schema
- Prometheus metrics visible in Grafana
```
