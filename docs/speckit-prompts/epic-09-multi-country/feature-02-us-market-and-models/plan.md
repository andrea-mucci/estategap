# Feature: US Market Spiders & Country-Specific ML Models

## /plan prompt

```
Implement with these technical decisions:

## US Spiders
- Zillow: Playwright-only (heavy JS rendering). Use stealth mode. Parse __NEXT_DATA__ JSON for listing data. Rotate residential US proxies. Rate limit: 1 req/3s.
- Redfin: JSON API endpoints (more accessible). Parse /api/home/details/... responses. Less aggressive anti-bot.
- Realtor.com: HTML + JSON-LD. Parse structured data from page source.
- All US spiders: convert sqft to m² (multiply by 0.092903), USD prices stored as-is + EUR conversion.
- US zone import: US Census Bureau TIGER/Line shapefiles for state/county/city boundaries. ZIP code boundaries from census.gov.

## Country-Specific Models (services/ml/trainer/)
- Model training loop: for each active country with > 1,000 listings → train independent model
- Country feature sets (defined in config/ml/features_{country}.yaml):
  - Base features (all countries): area_m2, bedrooms, bathrooms, floor, building_age, zone_median_price, dist_to_center, dist_to_transit, etc.
  - Spain: energy_cert_encoded, has_elevator, community_fees, orientation_encoded
  - France: dpe_rating, dvf_median_transaction_price, pièces (as feature, not just mapped)
  - UK: council_tax_band_encoded, epc_rating, leasehold_flag, land_registry_last_price
  - USA: hoa_fees, lot_size_m2, tax_assessed_value, school_rating, zestimate_reference
  - Italy: ape_rating, omi_zone_min_price, omi_zone_max_price

## Transfer Learning
- For countries with < 5,000 listings:
  1. Load Spain model weights (LightGBM .txt format)
  2. Continue training (init_model parameter) with local data
  3. Reduced learning rate (0.01) and fewer iterations (100)
  4. Evaluate: if MAPE > 20% → flag as "insufficient data", use zone-median heuristic instead
```
