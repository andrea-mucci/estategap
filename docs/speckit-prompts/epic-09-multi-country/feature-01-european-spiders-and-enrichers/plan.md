# Feature: European Portal Spiders & Enrichment Sources

## /plan prompt

```
Implement with these technical decisions:

## Spider Implementation Pattern
Each spider follows the same structure:
- File: services/spider-workers/spiders/{country}_{portal}.py
- Class: {Portal}Spider(BaseSpider) with country, portal_name, base_url class attributes
- Methods: scrape_search_page(), scrape_listing_detail(), detect_new_listings()
- Parser: separate parser module {country}_{portal}_parser.py with field extraction functions
- Mapping: YAML config in config/mappings/{country}_{portal}.yaml defining source→unified field mapping

## Portal-Specific Notes
- Immobiliare.it: API-first approach. JSON API endpoints available. Parse immobiliare.it/api/... responses.
- SeLoger: heavy anti-bot. Playwright required. Parse JSON-LD in HTML for listing data.
- LeBonCoin: API endpoints behind authentication. HTML scraping with session management.
- Rightmove: relatively open. HTML parsing with BeautifulSoup. JSON-LD for structured data.
- Funda: strict rate limiting. Slow scraping (1 req/2s). HTML + embedded JSON data.

## Enrichment Implementation
- FranceDVFEnricher: download CSV from data.gouv.fr (bulk, ~2GB). Import to PostgreSQL table dvf_transactions. Match via PostGIS ST_DWithin(listing_location, dvf_location, 200m) + same property_type. Return: 5 nearest transactions with prices.
- UKLandRegistryEnricher: download CSV from gov.uk/government/collections/price-paid-data. Import to PostgreSQL. Match by normalized address (rapidfuzz, threshold 90%).
- ItalyOMIEnricher: scrape Agenzia delle Entrate OMI zone data (semi-annual update). Store min/max €/m² per zone. Compare listing price against OMI range.
- NetherlandsBAGEnricher: PDOK WFS API. Query by address/postcode. Returns: year_built, area, building_type, geometry.

## Zone Import
- Use GADM (gadm.org) level-2/level-3 shapefiles for each country
- Import with geopandas: gpd.read_file("gadm_XX.shp") → iterate features → INSERT INTO zones
- Map GADM admin levels to platform zone levels per country
```
