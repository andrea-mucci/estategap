# Feature: Spider Framework & First Portal Spiders

## /plan prompt

```
Implement with these technical decisions:

## Framework (services/spider-workers/)
- BaseSpider abstract class in spiders/base.py
- Spider registry: dict mapping (country, portal) → SpiderClass. Auto-discovered via __init_subclass__ or explicit registration.
- NATS consumer: async, uses nats-py. Subscribes to scraper.commands.>. Routes to correct spider based on message payload.
- Proxy integration: gRPC call to proxy-manager before each request batch. Sticky session for paginated crawls.
- HTTP client: httpx with configurable timeout (30s), custom headers (User-Agent rotation from list of 50+), proxy injection.
- Playwright fallback: launch browser only when httpx gets blocked (403/captcha). Use stealth plugin.
- Output: RawListing Pydantic model → JSON → publish to NATS

## Idealista Spider (spiders/es_idealista.py)
- Strategy 1 (primary): reverse-engineer Idealista mobile API. Endpoints return JSON with all listing data. Requires specific headers (User-Agent mimicking Android/iOS app, custom auth tokens).
- Strategy 2 (fallback): HTML scraping with parsel. CSS selectors for: .item-info-container (listings), .info-features (details), .price-features__container (price).
- Pagination: increment ?pagina= parameter. Stop when no results.
- Detail page: extract all fields, GPS from meta tags or embedded JSON-LD.
- Photos: extract from img[src*="img3.idealista.com"] elements.

## Fotocasa Spider (spiders/es_fotocasa.py)
- Similar approach. Fotocasa uses React SSR with embedded JSON state (__NEXT_DATA__).
- Extract listing data from JSON embedded in HTML rather than parsing DOM.
- Different field names: map to unified schema in parser.

## Anti-Bot Strategy
- Request delay: random 2-5s between requests (configurable per portal)
- Concurrency: max 3 concurrent requests per portal per worker
- Session rotation: new proxy every 10 requests
- Captcha detection: if response contains captcha markers → switch to Playwright → solve with delay → extract data
```
