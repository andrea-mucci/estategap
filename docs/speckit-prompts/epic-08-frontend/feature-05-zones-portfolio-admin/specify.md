# Feature: Zones Analytics, Portfolio Tracker & Admin Panel

## /specify prompt

```
Build the zone analytics page, portfolio tracker, and admin panel.

## What
1. Zone Analytics (/zones/[id]): metrics display (median price/m², 12-month trend, volume, avg days on market, inventory, deal frequency). Price distribution histogram. Zone comparison tool: select up to 5 zones (cross-country), side-by-side table + overlay charts.

2. Portfolio Tracker (/portfolio): add owned properties (manual entry: address, purchase price, date, rental income). Dashboard: total invested, current estimated value (from ML model), unrealized gain/loss, rental yield. Multi-currency support.

3. Admin Panel (/admin, admin-only): tabs for Scraping Health (per portal/country), ML Models (MAPE per country, model history, manual retrain trigger), Users (list with tier, activity), Countries (enable/disable, portal config), System (NATS queue depths, DB size, Redis stats).

## Acceptance Criteria
- Zone analytics shows accurate data with interactive charts
- Cross-country zone comparison normalizes currencies to user's preference
- Portfolio: CRUD for properties, correct ROI calculation with currency conversion
- Admin: all metrics display correctly, manual retrain triggers K8s CronJob
- Admin access enforced (non-admin users get 403)
```
