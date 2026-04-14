# Feature: European Portal Spiders & Enrichment Sources

## /specify prompt

```
Implement spiders for the top European real estate portals and country-specific data enrichment sources.

## What
New portal spiders (each following BaseSpider interface):
1. Immobiliare.it (Italy) — Italy's #1 portal. 55M monthly visits. Italian field mapping.
2. Idealista IT (Italy) — Idealista's Italian version. Shared codebase with Spain spider, country-specific config.
3. SeLoger (France) — France's leading portal. 18M visits. French field mapping (pièces → bedrooms).
4. LeBonCoin Immobilier (France) — Classifieds giant. 40M RE visits. Both professional and private listings.
5. Bien'ici (France) — Challenger portal. 10M visits. 3D mapping technology.
6. Rightmove (UK) — UK's largest portal. 135M visits. GBP prices, council tax band, EPC rating, leasehold/freehold.
7. Funda (Netherlands) — Dutch market leader. 34M visits. EUR prices, BAG building data.

New enrichment sources:
1. France DVF: import open transaction data from data.gouv.fr (all sales since 2014). Match by address.
2. UK Land Registry: import Price Paid Data (open CSV, all transactions since 1995). Match by address.
3. Italy OMI: Agenzia delle Entrate reference prices per zone (min/max €/m²).
4. Netherlands BAG: building register (year, area, address, geometry) via PDOK API.

Administrative zone imports (OpenStreetMap/GADM) for: Italy, France, UK, Netherlands.

## Acceptance Criteria
- Each spider scrapes 1000+ listings with >75% data completeness
- Country-specific field mappings correct (pièces, council tax, leasehold, etc.)
- Currency handling correct (GBP for UK, EUR for others)
- France DVF: 60%+ Paris listings enriched with nearby transaction prices
- UK Land Registry: 70%+ London listings matched with transaction history
- Zone hierarchies browsable for each new country
```
