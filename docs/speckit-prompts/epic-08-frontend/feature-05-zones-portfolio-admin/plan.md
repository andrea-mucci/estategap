# Feature: Zones Analytics, Portfolio Tracker & Admin Panel

## /plan prompt

```
Implement with these technical decisions:

## Zone Analytics (app/[locale]/(protected)/zones/[id]/page.tsx)
- Server component fetches zone detail + analytics from API
- Charts: Recharts LineChart (price trend), BarChart (volume), Histogram (price distribution using d3-array bin())
- Comparison: multi-select combobox for zones. Fetch analytics for each. Render as overlaid charts (same X axis, different colored lines).
- Currency: all prices displayed in user's preferred currency via conversion middleware

## Portfolio (app/[locale]/(protected)/portfolio/page.tsx)
- CRUD via API: POST/GET/PUT/DELETE /api/v1/portfolio/properties
- Property form: address (geocoded), purchase_price + currency, purchase_date, monthly_rental_income
- Current value: fetched from ml-scorer on-demand (or cached estimate if listing still in DB)
- Calculations: gain_loss = current_value - purchase_price (currency-adjusted), yield = (annual_rental / purchase_price) * 100
- Summary cards: total invested, total current value, total gain/loss, average yield. All in user's preferred currency.

## Admin (app/[locale]/(protected)/admin/page.tsx)
- Admin route guard: middleware checks user.role === 'admin'
- Scraping tab: fetch from internal API /admin/scraping/stats → table with portal, country, last_scrape, success_rate, listings_24h, blocks_24h
- ML tab: fetch model_versions from API → table with version, country, mape, mae, r2, trained_at, is_active. "Retrain Now" button → POST /admin/ml/retrain → creates K8s Job
- Users tab: paginated user list with search, tier filter. Click → user detail with activity log.
- Countries tab: list of countries with toggle switch for enabled/disabled. Portal config editor (JSON).
- System tab: fetch from Prometheus API → NATS consumer lag, DB connection pool stats, Redis memory usage.
```
