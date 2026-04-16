# Functional Requirements — EstateGap

**Project:** Undervalued Property Detection & Alert System — Multi-Country Platform  
**Version:** 2.0  
**Date:** April 2026  
**Status:** Draft  
**Changelog:** v2.0 — Platform redesigned as extensible multi-country system. Added 30+ portals across 15 countries. New sections: Internationalization (§1A), Portal Registry (Appendix A), Public Data Sources (Appendix B).

---

## 1. Data Acquisition (Web Scraping)

### 1.1 Supported Sources — Launch Markets (Phase 1)

- **FR-ACQ-001** — The system shall scrape property listings from **Idealista** (idealista.com) covering residential sales in **Spain, Portugal, and Italy**.
- **FR-ACQ-002** — The system shall scrape property listings from **Fotocasa** (fotocasa.es) covering residential sales in **Spain**.

### 1.2 Supported Sources — European Expansion (Phase 2)

- **FR-ACQ-002A** — The system shall scrape property listings from **Immobiliare.it** and **Casa.it** for the **Italian** market.
- **FR-ACQ-002B** — The system shall scrape property listings from **SeLoger**, **LeBonCoin (Immobilier)**, and **Bien'ici** for the **French** market.
- **FR-ACQ-002C** — The system shall scrape property listings from **Imovirtual** for the **Portuguese** market (complementing Idealista Portugal).

### 1.3 Supported Sources — Full European Coverage (Phase 3)

- **FR-ACQ-003A** — The system shall scrape property listings from **ImmoScout24** and **Immowelt** for the **German** market.
- **FR-ACQ-003B** — The system shall scrape property listings from **Rightmove** and **Zoopla** for the **UK** market.
- **FR-ACQ-003C** — The system shall scrape property listings from **Funda** for the **Netherlands** market.
- **FR-ACQ-003D** — The system shall scrape property listings from **Hemnet** for the **Swedish** market.
- **FR-ACQ-003E** — The system shall scrape property listings from **Finn.no** for the **Norwegian** market.
- **FR-ACQ-003F** — The system shall scrape property listings from **Daft.ie** for the **Irish** market.
- **FR-ACQ-003G** — The system shall scrape property listings from **Homegate** and **ImmoScout24.ch** for the **Swiss** market.
- **FR-ACQ-003H** — The system shall scrape property listings from **ImmoScout24.at** for the **Austrian** market.
- **FR-ACQ-003I** — The system shall scrape property listings from **Spitogatos** for the **Greek** market.
- **FR-ACQ-003J** — The system shall scrape property listings from **Ingatlan.com** for the **Hungarian** market.
- **FR-ACQ-003K** — The system shall scrape property listings from **Otodom** for the **Polish** market.

### 1.4 Supported Sources — US Market (Phase 4)

- **FR-ACQ-004A** — The system shall scrape property listings from **Zillow** (zillow.com) for the **United States** market.
- **FR-ACQ-004B** — The system shall scrape property listings from **Redfin** (redfin.com) for the **United States** market.
- **FR-ACQ-004C** — The system shall scrape property listings from **Realtor.com** for the **United States** market.
- **FR-ACQ-004D** — The system shall scrape property listings from **Homes.com** for the **United States** market.
- **FR-ACQ-004E** — The system shall scrape property listings from **Trulia** (trulia.com) for the **United States** market.

### 1.5 Pluggable Adapter Architecture

- **FR-ACQ-005** — The system shall implement a **pluggable spider adapter** architecture where each portal is an independent module that conforms to a common interface (`BaseSpider`), allowing new portals to be added without modifying the core pipeline.
- **FR-ACQ-006** — Each spider adapter shall declare: portal name, country/countries served, supported property types, supported operation types (sale/rent), base URLs, and scraping capabilities (search, detail, new-listing detection).
- **FR-ACQ-007** — The system shall maintain a **Portal Registry** (configuration file or database table) listing all available spiders with their enabled/disabled status, scraping frequency, and country assignment.
- **FR-ACQ-008** — The system shall support enabling/disabling individual portals per country via the admin panel without code deployment.

### 1.6 Public Data Enrichment (Per-Country)

- **FR-ACQ-010** — The system shall enrich listing data with **country-specific public cadastral/registry data** where available (see Appendix B for full registry):
  - **Spain:** Sede Electrónica del Catastro (INSPIRE/WFS) — built area, year, cadastral reference, geometry.
  - **Italy:** Agenzia delle Entrate / Catasto via Sister platform — cadastral data.
  - **France:** DVF (Demandes de Valeurs Foncières) open dataset — actual transaction prices.
  - **Portugal:** Portal das Finanças / Cadastro Predial — limited public data.
  - **Germany:** Gutachterausschuss (Expert Committee) — Bodenrichtwerte (land value maps).
  - **UK:** HM Land Registry Price Paid Data — complete transaction history (open data).
  - **Netherlands:** Kadaster / BAG (Basisregistratie Adressen en Gebouwen) — building data.
  - **USA:** County assessor data, Zillow ZTRAX dataset, ATTOM Data, public MLS feeds.
- **FR-ACQ-011** — The system shall implement an enrichment adapter per country, conforming to a common `BaseEnricher` interface, so new public data sources can be added modularly.

### 1.7 Scraping Scheduling & Frequency

- **FR-ACQ-020** — The system shall perform full scraping sweeps of all monitored zones at a configurable interval (default: every 6 hours).
- **FR-ACQ-021** — The system shall perform incremental "new listing detection" polls at a higher frequency (default: every 15 minutes) for priority zones.
- **FR-ACQ-022** — The system shall allow per-zone AND per-portal configuration of scraping frequency.
- **FR-ACQ-023** — The system shall support manual triggering of a scraping run for a given zone, country, or portal.
- **FR-ACQ-024** — The system shall stagger scraping jobs across portals to avoid overloading proxies and respect per-portal rate limits.

### 1.8 Anti-Bot & Resilience

- **FR-ACQ-030** — The system shall implement rotating residential proxies with **per-country geo-targeting** (e.g., Spanish proxies for Idealista, French proxies for SeLoger, US proxies for Zillow).
- **FR-ACQ-031** — The system shall implement configurable request throttling (delay between requests, concurrency limits) **per portal**, since each portal has different anti-bot sensitivity.
- **FR-ACQ-032** — The system shall detect and handle CAPTCHA challenges, rate-limit responses (429), and soft blocks (empty/redirect responses), logging them for review.
- **FR-ACQ-033** — The system shall implement automatic retries with exponential backoff on transient failures.
- **FR-ACQ-034** — The system shall rotate User-Agent strings and HTTP headers to mimic real browser traffic.
- **FR-ACQ-035** — The system shall support headless browser rendering (Playwright/Puppeteer) as a fallback for JavaScript-rendered pages.
- **FR-ACQ-036** — The system shall maintain per-portal **scraping health dashboards** showing success rates, block rates, and latency.

### 1.9 Extracted Data Fields (Unified Schema)

- **FR-ACQ-040** — For each listing, the system shall extract and normalize into a **unified cross-portal schema** (at minimum) the following fields:

| Category | Fields |
|---|---|
| **Identity** | Source portal, source listing ID, listing URL, scrape timestamp, **country code (ISO 3166-1)**, **currency (ISO 4217)** |
| **Location** | Full address, neighborhood/barrio/quartier, district/arrondissement, city, region/province/state/county, postal code, **country**, GPS coordinates (lat/lon) |
| **Pricing** | Asking price (original currency), **asking price (EUR normalized)**, price per m² / price per sqft, price history (if available), rent estimate (if listed) |
| **Physical** | Total area (m² or sqft, **with unit**), usable area, number of bedrooms, number of bathrooms, floor/story number, orientation, has elevator, has parking, has storage, has terrace/balcony, has garden, **lot size (for houses)** |
| **Condition** | Property condition (new build / good / needs renovation / to renovate), year of construction, energy certificate rating (**country-specific scale**), last renovation year |
| **Type** | Property type (flat, penthouse, duplex, studio, house, villa, chalet, townhouse, condo), furnished status |
| **Building** | Total floors in building, number of units, building age, community fees / HOA fees |
| **Listing meta** | Publication date, days on market, number of photos, has virtual tour, has video, description text (**original language**), agent/owner name, agency name, phone number |
| **Media** | URLs of all listing photos |

- **FR-ACQ-041** — The system shall normalize all extracted data into the unified schema regardless of source portal, country, or language.
- **FR-ACQ-042** — The system shall detect and reconcile duplicate listings of the same physical property across different portals **within the same country** (deduplication by address, GPS proximity, and matching characteristics).
- **FR-ACQ-043** — The system shall track price changes over time for each listing and record a complete price history.
- **FR-ACQ-044** — The system shall detect when a listing is removed (sold/delisted) and record the delisting date and final price.
- **FR-ACQ-045** — The system shall store the **original listing description in its source language** and optionally generate a machine-translated version in the user's preferred language.

---

## 1A. Internationalization & Multi-Country Support

### 1A.1 Country Management

- **FR-I18N-001** — The system shall treat **country** as a first-class entity. Each country has: a code (ISO 3166-1 alpha-2), name, default currency, default language, active portals, active enrichment sources, and active ML model.
- **FR-I18N-002** — The admin shall be able to activate/deactivate countries from the admin panel. Only active countries are scraped and scored.
- **FR-I18N-003** — The system shall support launching a new country by: (a) implementing at least one spider adapter, (b) defining initial zones, (c) optionally connecting enrichment sources, and (d) training or bootstrapping an ML model.
- **FR-I18N-004** — The system shall enforce data isolation per country for ML training (models are trained per-country, not cross-country) while sharing the same infrastructure.

### 1A.2 Currency Handling

- **FR-I18N-010** — The system shall store listing prices in their **original currency** (EUR, GBP, SEK, NOK, CHF, PLN, HUF, USD, etc.).
- **FR-I18N-011** — The system shall maintain a daily-updated exchange rate table (sourced from ECB or Open Exchange Rates API) and compute EUR-equivalent prices for cross-country comparison.
- **FR-I18N-012** — The user-facing application shall display prices in the user's preferred currency, with the original currency shown as secondary.

### 1A.3 Unit Handling

- **FR-I18N-020** — The system shall store property areas in their **source unit** (m² for Europe, sqft for US).
- **FR-I18N-021** — The system shall normalize all areas to m² internally for model training, while displaying in the user's preferred unit.
- **FR-I18N-022** — The system shall handle country-specific measurement conventions (e.g., "pièces" in France ≠ "bedrooms"; Japanese tsubo; UK "reception rooms").

### 1A.4 Language & Localization

- **FR-I18N-030** — The user-facing web application shall support **at minimum** these UI languages: English, Spanish, French, Italian, German, Portuguese.
- **FR-I18N-031** — Listing descriptions shall be stored in their original language. The system shall offer on-demand machine translation (via API) to the user's preferred language.
- **FR-I18N-032** — Zone names, property types, and condition labels shall use a **canonical taxonomy** internally (in English) mapped to localized display names per language.
- **FR-I18N-033** — Email/Telegram/WhatsApp alert templates shall be available in the user's preferred language.

### 1A.5 Country-Specific Feature Mapping

- **FR-I18N-040** — The system shall maintain a **feature mapping table** per country that translates portal-specific field names into the unified schema. Examples:
  - France: "nombre de pièces" → bedrooms (minus 1, since pièces includes living room)
  - Italy: "classe energetica" → energy_certificate
  - UK: "council tax band" → council_tax_band (UK-specific field)
  - US: "HOA fees" → community_fees
  - Germany: "Kaltmiete" vs "Warmmiete" → rent_cold / rent_warm
- **FR-I18N-041** — The unified schema shall support **country-specific optional fields** that only apply to certain markets (e.g., council tax band for UK, HOA for US, DPE for France, APE for Italy).

---

## 2. Data Storage & Management

### 2.1 Database

- **FR-DAT-001** — The system shall store all scraped listing data in a relational database (PostgreSQL with PostGIS extension for spatial queries).
- **FR-DAT-002** — The system shall maintain a full audit trail of every data point change (price changes, description edits, status changes) with timestamps.
- **FR-DAT-003** — The system shall store computed zone-level statistics (median price/m², average days on market, listing volume) as materialized views refreshed on each scraping cycle.
- **FR-DAT-004** — The listings table shall be **partitioned by country** (first level) and optionally by city (second level) for query performance.

### 2.2 Zone Definition

- **FR-DAT-010** — The system shall support defining geographic zones at multiple granularity levels per country:
  - **Spain:** comunidad autónoma → provincia → municipio → distrito → barrio → código postal
  - **France:** région → département → commune → arrondissement → quartier → code postal
  - **Italy:** regione → provincia → comune → municipio → CAP
  - **Germany:** Bundesland → Kreis → Gemeinde → Stadtteil → PLZ
  - **UK:** region → county → district → ward → postcode
  - **Netherlands:** provincie → gemeente → wijk → buurt → postcode
  - **USA:** state → county → city → ZIP code → neighborhood
- **FR-DAT-011** — The system shall allow users to draw custom zones on a map and save them as named areas for monitoring, regardless of country.
- **FR-DAT-012** — The system shall auto-classify each listing into its corresponding zones using its GPS coordinates.
- **FR-DAT-013** — The system shall load administrative boundary polygons from open data sources (OpenStreetMap, GADM, Eurostat NUTS) per country.

### 2.3 Public Data Enrichment

- **FR-DAT-020** — The system shall cross-reference listing addresses with the **country-specific cadastral/public registry** (where available) to obtain: official area, year of construction, building type, and parcel geometry.
- **FR-DAT-021** — The system shall flag discrepancies between portal-reported area and official area (potential red flag or opportunity).
- **FR-DAT-022** — For countries with public transaction data (France DVF, UK Land Registry, Netherlands Kadaster), the system shall import historical sale prices to improve model training.

---

## 3. Valuation Model (Undervalued Property Detection)

### 3.1 Price Estimation Model

- **FR-MOD-001** — The system shall train a machine learning model (e.g., Gradient Boosting / XGBoost / LightGBM) to estimate the fair market price of a property based on its features and location.
- **FR-MOD-002** — The model shall use at minimum the following feature categories:
  - **Spatial:** GPS coordinates, zone, distance to metro/transit, distance to city center, distance to coast/green areas, neighborhood median income.
  - **Physical:** Built area (m²), usable area, bedrooms, bathrooms, floor number, has elevator, has parking, has terrace, orientation.
  - **Condition:** Year of construction, renovation state, energy certificate rating.
  - **Contextual:** Building total floors, community fees, property type.
  - **Temporal:** Month/quarter of listing (seasonality).
- **FR-MOD-003** — The system shall calculate a **"Deal Score"** for each listing, defined as the percentage deviation between the asking price and the model's estimated fair price: `deal_score = (estimated_price - asking_price) / estimated_price * 100`.
- **FR-MOD-004** — A positive deal score indicates an undervalued property. The system shall classify deals into tiers:
  - **Tier 1 — Hot Deal:** deal_score ≥ 20% (significantly undervalued)
  - **Tier 2 — Good Deal:** 10% ≤ deal_score < 20%
  - **Tier 3 — Fair Price:** -5% ≤ deal_score < 10%
  - **Tier 4 — Overpriced:** deal_score < -5%
- **FR-MOD-005** — The system shall provide a **confidence interval** (e.g., 90%) for each price estimate, so the user understands prediction uncertainty.

### 3.2 Multi-Country Model Strategy

- **FR-MOD-006** — The system shall train **independent models per country** (and optionally per major metro area within a country) to capture local market dynamics.
- **FR-MOD-007** — All models shall use the same unified feature schema, but country-specific optional features shall be included only for the relevant country's model.
- **FR-MOD-008** — For new countries with limited data (<5,000 listings), the system shall support a **transfer learning** approach: fine-tuning a base model trained on a mature market (e.g., Spain) with the new country's data.
- **FR-MOD-009** — The system shall track model performance metrics (MAE, MAPE, R²) **per country** and per major city, displayed on the admin dashboard.

### 3.3 Model Training & Retraining

- **FR-MOD-010** — The system shall initially train the model on historical sold-listing data (with known final prices) and/or the accumulated scraped data.
- **FR-MOD-011** — The system shall retrain the model automatically on a configurable schedule (default: weekly), incorporating newly collected data.
- **FR-MOD-012** — The system shall maintain model versioning and store performance metrics (MAE, MAPE, R²) for each trained model.
- **FR-MOD-013** — The system shall support A/B testing of different model architectures or feature sets.
- **FR-MOD-014** — The system shall train separate sub-models per major city/region if data volume is sufficient, to capture local market dynamics.

### 3.4 Anomaly & Opportunity Detection

- **FR-MOD-020** — The system shall flag listings where the price drops significantly (>5%) within a short time window (configurable, default 7 days) as "price drop alerts."
- **FR-MOD-021** — The system shall detect listings that have been on the market for an unusually long time relative to the zone average (>2× median days on market) and flag them as "stale listings" — potential negotiation opportunities.
- **FR-MOD-022** — The system shall detect newly listed properties that score as Tier 1 or Tier 2 deals and prioritize them for immediate alerting.
- **FR-MOD-023** — The system shall detect "area/price mismatch" — properties whose m² is significantly larger than comparables at a similar price point, indicating potential undervaluation.
- **FR-MOD-024** — The system shall identify listings with missing or incomplete information (e.g., no photos, vague description) as potential hidden gems often overlooked by other buyers.

### 3.5 Explainability

- **FR-MOD-030** — The system shall provide per-listing feature-importance explanations (e.g., SHAP values) showing which factors contributed to the estimated price and deal score.
- **FR-MOD-031** — The system shall show comparable properties ("comps") — the N most similar recently sold or listed properties in the same zone — alongside each deal analysis.

---

## 4. Alerting System

### 4.1 Alert Configuration

- **FR-ALT-001** — Users shall be able to define alert rules based on: **country**, zone(s), property type, min/max price, min/max area, min deal score tier, specific features (e.g., has elevator, max floor), and max days on market.
- **FR-ALT-002** — Users shall be able to create multiple independent alert profiles (e.g., "investment flats Madrid Centro", "renovation opportunities Paris 18e", "beach houses Algarve").
- **FR-ALT-003** — Users shall be able to set alert priority: instant (real-time), hourly digest, daily digest.
- **FR-ALT-004** — Users shall be able to set alert language: alerts are delivered in the user's preferred language.

### 4.2 Notification Channels

- **FR-ALT-010** — The system shall send alerts via **email** with a summary card (photo, price, deal score, link to the portal listing, link to internal analysis).
- **FR-ALT-011** — The system shall send alerts via **push notification** (mobile app or web push).
- **FR-ALT-012** — The system shall send alerts via **Telegram bot** with inline preview.
- **FR-ALT-013** — The system shall send alerts via **WhatsApp** (using the Business API or similar integration).
- **FR-ALT-014** — The system shall send alerts via **webhook** (for advanced users to integrate with their own systems, Zapier, n8n, etc.).

### 4.3 Alert Content

- **FR-ALT-020** — Each alert shall include: property thumbnail, address, asking price (**in user's preferred currency**), estimated fair price, deal score and tier, key features (m²/sqft, rooms, floor, condition), days on market, direct link to the source listing, and a link to the internal detailed analysis page.
- **FR-ALT-021** — Digest alerts (hourly/daily) shall include a ranked summary of all qualifying new deals, sorted by deal score descending, **grouped by country if the user monitors multiple countries**.

### 4.4 Alert Deduplication

- **FR-ALT-030** — The system shall not re-send an alert for the same property unless there is a material change (price drop, status change).
- **FR-ALT-031** — The system shall track which alerts have been sent, opened, and acted upon (clicked) per user.

---

## 5. User-Facing Web Application

### 5.1 Dashboard

- **FR-APP-001** — The system shall provide a web dashboard showing a real-time overview of: total monitored listings, new listings today, top deals by score, recent price drops, and zone-level heatmaps.
- **FR-APP-002** — The dashboard shall display an interactive map (Mapbox/Leaflet) with listings plotted as color-coded pins by deal tier. **The map shall support pan/zoom across all active countries.**
- **FR-APP-003** — The dashboard shall show trend charts: average price/m² over time by zone, listing volume over time, days on market trends.
- **FR-APP-004** — The dashboard shall allow **filtering by country** as a top-level navigation element.

### 5.2 Listing Search & Filtering

- **FR-APP-010** — Users shall be able to search and filter listings by: **country**, zone, price range, area range, number of rooms, property type, deal score tier, listing status (active/delisted/price changed), days on market, source portal, and any extracted feature.
- **FR-APP-011** — Users shall be able to sort results by: deal score, price, price/m², recency, days on market.
- **FR-APP-012** — Users shall be able to save search filters as reusable "saved searches."

### 5.3 Listing Detail View

- **FR-APP-020** — The listing detail page shall display: all extracted data fields, photo gallery, deal score with confidence interval, SHAP-based explainability breakdown, price history chart, comparable properties, zone statistics, cadastral information (if available), and direct link to the source listing.
- **FR-APP-021** — The listing detail page shall show a mini-map with the property location and nearby POIs (metro, schools, supermarkets).
- **FR-APP-022** — Users shall be able to add private notes to any listing.
- **FR-APP-023** — Users shall be able to mark listings as "favorite", "contacted", "visited", "offer made", "discarded" (a simple CRM pipeline).
- **FR-APP-024** — The listing description shall be shown in original language with a **"Translate" button** that triggers machine translation to the user's language.

### 5.4 Zone Analytics

- **FR-APP-030** — The system shall provide a zone analytics page showing per-zone: median price/m², price trend (12 months), listing volume, average days on market, inventory levels, price distribution histogram, and deal frequency.
- **FR-APP-031** — The system shall provide a zone comparison tool to compare up to 5 zones side-by-side on key metrics — **including cross-country comparisons** (e.g., Madrid Centro vs. Milan Centro vs. Paris 11e).
- **FR-APP-032** — The system shall generate a "Zone Investment Score" that combines affordability, price trend momentum, deal frequency, and liquidity into a single index.

### 5.5 Portfolio Tracker (Personal Use Mode)

- **FR-APP-040** — The system shall allow the operator (personal use) to track owned properties with purchase price, current estimated value, rental income, and ROI calculations.
- **FR-APP-041** — The system shall display a portfolio summary with total invested capital, total estimated value, unrealized gain/loss, and rental yield — **with multi-currency support**.

---

## 6. Subscription & Monetization (Premium Alerts Mode)

### 6.1 User Management

- **FR-SUB-001** — The system shall support user registration and authentication (email + password, Google OAuth).
- **FR-SUB-002** — The system shall support the following subscription tiers:
  - **Free:** Access to listings older than 48 hours, basic search, limited zone analytics, 1 country, no alerts.
  - **Basic (€19/month):** Real-time listing access, 3 alert profiles, email + Telegram notifications, 5 zones, **1 country**.
  - **Pro (€49/month):** Everything in Basic + unlimited alert profiles, all notification channels, unlimited zones, **up to 3 countries**, deal score explainability, comparable properties, portfolio tracker.
  - **Global (€89/month):** Everything in Pro + **all countries**, cross-country comparison tools, API access (limited).
  - **API (€149/month):** Everything in Global + full RESTful API access with higher rate limits for programmatic consumption.
- **FR-SUB-003** — Pricing tiers and feature gates shall be configurable by the system administrator.

### 6.2 Payment

- **FR-SUB-010** — The system shall integrate with **Stripe** for subscription billing (recurring monthly/annual payments).
- **FR-SUB-011** — The system shall support 14-day free trial for Basic, Pro, and Global tiers.
- **FR-SUB-012** — The system shall handle subscription upgrades, downgrades, cancellations, and billing retries.
- **FR-SUB-013** — The system shall support **regional pricing** (e.g., lower price points for Eastern European markets) configurable per country.

### 6.3 Feature Gating

- **FR-SUB-020** — The system shall enforce feature access based on subscription tier (e.g., free users see delayed data, deal scores hidden behind paywall, country access limited by tier).
- **FR-SUB-021** — The system shall display "upgrade prompts" when a free or Basic user attempts to access a higher-tier feature.

---

## 7. API (Programmatic Access)

- **FR-API-001** — The system shall expose a RESTful API with the following endpoints:
  - `GET /countries` — List active countries with summary stats.
  - `GET /listings` — Search and filter listings (paginated), **filterable by country**.
  - `GET /listings/{id}` — Get full listing detail with deal analysis.
  - `GET /zones` — List monitored zones with summary stats, **filterable by country**.
  - `GET /zones/{id}/analytics` — Get zone-level analytics and trends.
  - `GET /alerts` — List triggered alerts for the authenticated user.
  - `POST /alerts/rules` — Create/update alert rules.
  - `GET /model/estimate` — Get a price estimate for a set of property features (on-demand valuation).
  - `GET /portals` — List available portals and their status per country.
- **FR-API-002** — The API shall require authentication via API key (Bearer token).
- **FR-API-003** — The API shall enforce rate limits per subscription tier.
- **FR-API-004** — The API shall return data in JSON format and follow RESTful conventions.
- **FR-API-005** — The API shall provide OpenAPI/Swagger documentation.
- **FR-API-006** — The API shall support **currency conversion** via a query parameter (`?currency=USD`).

---

## 8. Administration & Operations

### 8.1 Admin Panel

- **FR-ADM-001** — The system shall provide an admin panel for the operator to: monitor scraping job status and health **per portal and per country**, view error logs, manage zones, retrain models manually, view user/subscriber metrics, and manage subscriptions.
- **FR-ADM-002** — The admin panel shall display scraping statistics: total listings scraped, success rate, errors by source, average scrape latency, proxy health — **broken down by country and portal**.
- **FR-ADM-003** — The admin panel shall display model performance metrics: current MAE, MAPE, R² **per country** and per zone, model version history.
- **FR-ADM-004** — The admin panel shall provide a **Country Management** screen where the operator can: add a new country, assign portals, configure enrichment sources, and trigger initial data collection.
- **FR-ADM-005** — The admin panel shall provide a **Portal Health** screen showing per-portal: last successful scrape, error rate (24h), listings collected (24h), proxy usage, and anti-bot block rate.

### 8.2 Monitoring & Observability

- **FR-ADM-010** — The system shall implement health checks for all services (scraper, model, API, database, notification services).
- **FR-ADM-011** — The system shall send operational alerts (to the operator) when: scraping fails for >2 consecutive cycles, model accuracy degrades below threshold, API error rate exceeds 5%, database storage exceeds 80%.
- **FR-ADM-012** — The system shall log all operations with structured logging (JSON) for ingestion into a log aggregation system.

---

## 9. Data Quality & Integrity

- **FR-DQ-001** — The system shall validate all scraped data against expected ranges (e.g., price > 0, area > 5m², floor ≤ 50) **with country-specific thresholds** (e.g., US prices in USD, not EUR).
- **FR-DQ-002** — The system shall detect and flag listings that appear to be duplicates posted by the same agency at slightly different prices.
- **FR-DQ-003** — The system shall detect "fake" or "bait" listings (abnormally low price for the zone, no photos, generic description) and exclude them from model training data.
- **FR-DQ-004** — The system shall maintain a "blacklist" of known fake listing patterns and agency accounts **per portal**.
- **FR-DQ-005** — The system shall compute a **data completeness score** per listing (percentage of fields populated) and use it as a weighting factor in model training.

---

## 10. Legal & Compliance

- **FR-LEG-001** — The system shall comply with **GDPR** (for EU countries) and relevant local data protection laws (CCPA for US): personal data (agent names, phone numbers) shall be stored with appropriate consent mechanisms and deletion capabilities.
- **FR-LEG-002** — The system shall respect `robots.txt` directives and implement scraping rates that do not constitute denial-of-service.
- **FR-LEG-003** — The system shall include a clear Terms of Service and Privacy Policy for subscribed users, **available in all supported UI languages**.
- **FR-LEG-004** — The system shall provide a mechanism for data subjects (agents, owners) to request removal of their contact information.
- **FR-LEG-005** — The system shall store scraped data as factual market data (prices, features) and avoid reproducing copyrighted description text verbatim in user-facing interfaces.
- **FR-LEG-006** — The system shall comply with the **EU Digital Services Act** where applicable.
- **FR-LEG-007** — The system shall maintain documentation of legal basis per country for scraping public listing data.

---

## 11. Performance & Scalability Requirements

- **FR-PER-001** — The system shall process a full scraping cycle of 500,000+ listings per country within 6 hours.
- **FR-PER-002** — Incremental new-listing detection shall complete within 5 minutes per zone.
- **FR-PER-003** — Deal score computation for a new listing shall complete within 10 seconds of ingestion.
- **FR-PER-004** — Real-time alerts for Tier 1 deals shall be dispatched within 2 minutes of the listing being detected.
- **FR-PER-005** — The web dashboard shall load initial data within 3 seconds.
- **FR-PER-006** — The API shall respond to search queries within 500ms (p95).
- **FR-PER-007** — The system shall support horizontal scaling of scraping workers **per country** to handle additional portals or higher frequencies.
- **FR-PER-008** — The system shall support at least **5 concurrent countries** in Phase 3 and **15 countries** at full scale.

---

## Appendix A: Portal Registry by Country

### Southern Europe (Launch Markets)

| Country | Portal | URL | Monthly Visits | Type | Priority |
|---|---|---|---|---|---|
| 🇪🇸 Spain | **Idealista** | idealista.com | ~55M | Vertical RE | P0 (launch) |
| 🇪🇸 Spain | **Fotocasa** | fotocasa.es | ~12M | Vertical RE | P0 (launch) |
| 🇪🇸 Spain | Pisos.com | pisos.com | ~9M | Vertical RE | P2 |
| 🇪🇸 Spain | Habitaclia | habitaclia.com | ~5M | Vertical RE | P3 |
| 🇪🇸 Spain | Milanuncios | milanuncios.com | ~8M (RE section) | Horizontal classifieds | P3 |
| 🇮🇹 Italy | **Immobiliare.it** | immobiliare.it | ~55M | Vertical RE | P1 |
| 🇮🇹 Italy | **Idealista IT** | idealista.it | ~15M | Vertical RE | P1 |
| 🇮🇹 Italy | Casa.it | casa.it | ~8M | Vertical RE | P2 |
| 🇮🇹 Italy | Subito.it | subito.it | ~5M (RE section) | Horizontal classifieds | P3 |
| 🇵🇹 Portugal | **Idealista PT** | idealista.pt | ~12M | Vertical RE | P1 |
| 🇵🇹 Portugal | **Imovirtual** | imovirtual.com | ~5M | Vertical RE | P1 |
| 🇵🇹 Portugal | Supercasa | supercasa.pt | ~3M | Vertical RE | P2 |

### France

| Country | Portal | URL | Monthly Visits | Type | Priority |
|---|---|---|---|---|---|
| 🇫🇷 France | **SeLoger** | seloger.com | ~18M | Vertical RE | P1 |
| 🇫🇷 France | **LeBonCoin** (Immobilier) | leboncoin.fr | ~90M (total, ~40M RE) | Horizontal classifieds | P1 |
| 🇫🇷 France | **Bien'ici** | bienici.com | ~10M | Vertical RE | P1 |
| 🇫🇷 France | Logic-Immo | logic-immo.com | ~5M | Vertical RE | P2 |
| 🇫🇷 France | PAP | pap.fr | ~4M | P2P (no agency) | P2 |

### DACH (Germany, Austria, Switzerland)

| Country | Portal | URL | Monthly Visits | Type | Priority |
|---|---|---|---|---|---|
| 🇩🇪 Germany | **ImmoScout24** | immobilienscout24.de | ~40M | Vertical RE | P2 |
| 🇩🇪 Germany | **Immowelt** | immowelt.de | ~12M | Vertical RE | P2 |
| 🇩🇪 Germany | WG-Gesucht | wg-gesucht.de | ~8M | Shared housing | P3 |
| 🇦🇹 Austria | **ImmoScout24.at** | immobilienscout24.at | ~5M | Vertical RE | P3 |
| 🇦🇹 Austria | willhaben.at | willhaben.at | ~10M (RE section) | Horizontal classifieds | P3 |
| 🇨🇭 Switzerland | **Homegate** | homegate.ch | ~6M | Vertical RE | P3 |
| 🇨🇭 Switzerland | ImmoScout24.ch | immoscout24.ch | ~5M | Vertical RE | P3 |

### UK & Ireland

| Country | Portal | URL | Monthly Visits | Type | Priority |
|---|---|---|---|---|---|
| 🇬🇧 UK | **Rightmove** | rightmove.co.uk | ~135M | Vertical RE | P2 |
| 🇬🇧 UK | **Zoopla** | zoopla.co.uk | ~40M | Vertical RE | P2 |
| 🇬🇧 UK | OnTheMarket | onthemarket.com | ~15M | Vertical RE | P3 |
| 🇮🇪 Ireland | **Daft.ie** | daft.ie | ~5M | Vertical RE | P3 |
| 🇮🇪 Ireland | MyHome.ie | myhome.ie | ~3M | Vertical RE | P3 |

### Nordics

| Country | Portal | URL | Monthly Visits | Type | Priority |
|---|---|---|---|---|---|
| 🇸🇪 Sweden | **Hemnet** | hemnet.se | ~20M | Vertical RE | P3 |
| 🇳🇴 Norway | **Finn.no** | finn.no | ~15M (RE section) | Horizontal classifieds | P3 |
| 🇫🇮 Finland | **Etuovi** | etuovi.com | ~4M | Vertical RE | P3 |
| 🇩🇰 Denmark | **Boligsiden** | boligsiden.dk | ~5M | Vertical RE | P3 |

### Benelux

| Country | Portal | URL | Monthly Visits | Type | Priority |
|---|---|---|---|---|---|
| 🇳🇱 Netherlands | **Funda** | funda.nl | ~34M | Vertical RE | P2 |
| 🇳🇱 Netherlands | Pararius | pararius.nl | ~4M | Rental-focused | P3 |
| 🇧🇪 Belgium | **Immoweb** | immoweb.be | ~10M | Vertical RE | P3 |
| 🇧🇪 Belgium | Zimmo | zimmo.be | ~3M | Vertical RE | P3 |

### Eastern Europe

| Country | Portal | URL | Monthly Visits | Type | Priority |
|---|---|---|---|---|---|
| 🇵🇱 Poland | **Otodom** | otodom.pl | ~12M | Vertical RE | P3 |
| 🇭🇺 Hungary | **Ingatlan.com** | ingatlan.com | ~8M | Vertical RE | P3 |
| 🇨🇿 Czechia | **Sreality** | sreality.cz | ~6M | Vertical RE | P3 |
| 🇷🇴 Romania | **OLX Imobiliare** | olx.ro | ~5M (RE section) | Horizontal classifieds | P3 |
| 🇬🇷 Greece | **Spitogatos** | spitogatos.gr | ~5M | Vertical RE | P3 |

### United States

| Country | Portal | URL | Monthly Visits | Type | Priority |
|---|---|---|---|---|---|
| 🇺🇸 USA | **Zillow** | zillow.com | ~345M | Vertical RE | P2 |
| 🇺🇸 USA | **Realtor.com** | realtor.com | ~121M | Vertical RE (MLS) | P2 |
| 🇺🇸 USA | **Redfin** | redfin.com | ~93M | Brokerage + portal | P2 |
| 🇺🇸 USA | **Homes.com** | homes.com | ~48M | Vertical RE | P3 |
| 🇺🇸 USA | **Trulia** | trulia.com | ~29M | Vertical RE (Zillow Group) | P3 |

**Priority Legend:**
- **P0** — Launch (MVP). First portals implemented.
- **P1** — Early expansion. High-value European markets with strong data availability.
- **P2** — Core expansion. Major markets with large listing volumes.
- **P3** — Full coverage. Added for completeness as demand grows.

---

## Appendix B: Public Data Sources by Country

| Country | Source | Data Available | Access | Cost |
|---|---|---|---|---|
| 🇪🇸 Spain | Catastro (INSPIRE WFS) | Cadastral ref, built area, year, geometry | Public API | Free |
| 🇪🇸 Spain | INE | Demographics, income by zone | Open data | Free |
| 🇪🇸 Spain | Ministerio de Transportes | Official transaction prices (quarterly) | CSV download | Free |
| 🇫🇷 France | DVF (data.gouv.fr) | **All property transactions since 2014** (price, area, type, address) | Open data | Free |
| 🇫🇷 France | INSEE | Demographics, income, population | Open data | Free |
| 🇮🇹 Italy | Agenzia delle Entrate (OMI) | Zone-level reference prices (min/max €/m²) | Semi-public | Free |
| 🇮🇹 Italy | ISTAT | Demographics, income | Open data | Free |
| 🇵🇹 Portugal | INE Portugal | Transaction price index, demographics | Open data | Free |
| 🇩🇪 Germany | Gutachterausschuss | Bodenrichtwerte (land reference values) | Per-municipality, some open | Varies |
| 🇩🇪 Germany | Destatis | Demographics, construction permits | Open data | Free |
| 🇬🇧 UK | HM Land Registry | **All transactions since 1995** (price, address, type, new/old) | Open data | Free |
| 🇬🇧 UK | EPC Register | Energy Performance Certificates | Open data | Free |
| 🇬🇧 UK | ONS | Demographics, income, house price index | Open data | Free |
| 🇳🇱 Netherlands | Kadaster | Transaction data (limited public) | Semi-public | Paid |
| 🇳🇱 Netherlands | BAG | All buildings: year, area, address, geometry | Open data | Free |
| 🇸🇪 Sweden | Lantmäteriet | Transaction prices | Public (some fees) | Partial |
| 🇺🇸 USA | County Assessor Data | Tax assessments, property characteristics | Per-county APIs | Free–Paid |
| 🇺🇸 USA | Census Bureau (ACS) | Demographics, income, housing stats | Open data | Free |
| 🇺🇸 USA | FHFA HPI | House Price Index by metro area | Open data | Free |

---

## Appendix C: Deal Score Calculation Example

```
Property: Flat in Malasaña, Madrid (Spain)
  - 75 m², 2 bedrooms, 3rd floor with elevator, good condition, built 1965
  - Asking price: €280,000 (€3,733/m²)

Model estimate: €340,000 (€4,533/m²)
Confidence interval (90%): €310,000 — €370,000

Deal Score = (340,000 - 280,000) / 340,000 × 100 = 17.6%
Tier: Good Deal (Tier 2)

Top SHAP factors:
  + Zone median is €4,800/m² → pushes estimate up
  + Elevator on 3rd floor → pushes estimate up
  - Built 1965, no recent renovation → pushes estimate down
  - No parking → pushes estimate down
```

## Appendix D: Alert Rule Example (JSON)

```json
{
  "name": "Southern Europe investment flats",
  "countries": ["ES", "IT", "PT"],
  "zones": ["madrid-centro", "milano-centro", "lisboa-alfama"],
  "filters": {
    "property_type": ["flat", "penthouse"],
    "min_area_m2": 50,
    "max_price_eur": 400000,
    "min_deal_score_tier": 2,
    "has_elevator": true
  },
  "notifications": {
    "channels": ["email", "telegram"],
    "frequency": "instant",
    "language": "es"
  }
}
```

## Appendix E: Extensibility Checklist — Adding a New Country

To add a new country to the platform, the following steps are required:

1. **Spider Adapter:** Implement at least one `BaseSpider` for the country's dominant portal. Define field mappings from portal HTML/API to unified schema.
2. **Feature Mapping:** Create the country-specific feature mapping table (e.g., how "pièces" maps to bedrooms in France).
3. **Zone Hierarchy:** Import administrative boundary polygons (from OSM/GADM/Eurostat) and define the zone hierarchy.
4. **Proxy Configuration:** Add geo-targeted proxy pool for the country.
5. **Enrichment (optional):** Implement `BaseEnricher` adapter if public cadastral/transaction data exists.
6. **ML Model Bootstrap:** Either (a) collect 5,000+ listings and train a country-specific model, or (b) use transfer learning from an existing model.
7. **Currency & Units:** Add currency code and conversion rate; configure area unit (m² vs sqft).
8. **UI Localization:** Add translated zone names and feature labels. Optionally add UI language.
9. **Legal Review:** Document the legal basis for scraping in this jurisdiction.
10. **Activate:** Enable the country via the admin panel. Scraping begins on the next cycle.

**Estimated effort per new country: 1–3 weeks** (depending on portal complexity and data source availability).
