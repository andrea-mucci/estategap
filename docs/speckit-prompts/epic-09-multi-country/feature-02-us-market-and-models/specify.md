# Feature: US Market Spiders & Country-Specific ML Models

## /specify prompt

```
Implement US real estate portal spiders and train country-specific ML models for all active markets.

## What
US portal spiders:
1. Zillow (zillow.com) — US #1 portal, 345M visits. Scrape: listings with Zestimate, HOA fees, lot size (sqft), tax history. Heavy anti-bot (requires Playwright + residential proxies).
2. Redfin (redfin.com) — 93M visits. Compete Score, school ratings. More accessible than Zillow.
3. Realtor.com — 121M visits. MLS-sourced data, highly accurate. School info, crime data.

US-specific considerations:
- Prices in USD, areas in sqft (convert to m² internally)
- HOA fees as feature in ML model
- US administrative zones: state → county → city → ZIP code → neighborhood
- County assessor data integration for tax-assessed values

Country-specific ML models:
- Train separate LightGBM models for: Spain, Italy, France, UK, Netherlands, USA
- Each model uses the unified feature set + country-specific optional features
- For countries with < 5,000 listings: transfer learning from Spain model
- Evaluate: MAPE < 12% per country. Per-city metrics for major metros.

## Acceptance Criteria
- Zillow spider: 1000+ US listings (NYC metro) with >70% completeness
- Redfin spider: same criteria
- sqft→m² conversion verified correct
- HOA fees parsed and included in model features
- ML model MAPE < 12% for each country
- Scorer loads correct model per country automatically
- Transfer learning produces reasonable results for low-data countries
```
