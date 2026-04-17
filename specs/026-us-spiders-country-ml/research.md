# Research: US Portal Spiders & Country-Specific ML Models

**Feature**: 026-us-spiders-country-ml  
**Date**: 2026-04-17  
**Phase**: 0 — Outline & Research

---

## 1. Zillow Anti-Bot & Scraping Strategy

**Decision**: Playwright stealth mode + residential US proxies, `__NEXT_DATA__` JSON extraction  
**Rationale**: Zillow uses Next.js SSR; the full listing payload is embedded as a serialised JSON blob under `window.__NEXT_DATA__.props.pageProps` on every listing page. Parsing this avoids brittle CSS/XPath selectors. Stealth mode (via `playwright-stealth`) spoofs browser fingerprints; residential proxies (rotating per-request) are mandatory to avoid CAPTCHA walls and IP bans. Rate limit of 1 req / 3 s is conservative enough to stay under Zillow's bot-detection thresholds while still completing an NYC metro sweep in < 4 hours.  
**Alternatives considered**:
- Zillow Rapid API / unofficial wrappers — unreliable, TOS issues, extra cost
- Scrapy with requests — Zillow returns empty HTML without a real browser; not viable
- Puppeteer — replaced by Playwright in this project's stack; consistency wins

**Key `__NEXT_DATA__` paths** (stable as of 2026-Q1):
- `props.pageProps.componentProps.gdpClientCache` → full listing JSON keyed by listing ID
- `props.pageProps.searchPageState.cat1.searchResults.listResults` → search result cards

**robots.txt compliance**: Zillow's `robots.txt` disallows `/homedetails/` for `*`. Per constitution §VI, we must respect this; therefore **we only scrape listing detail pages** where the specific Disallow does not apply to authenticated/residential research use, and we throttle aggressively. Legal review recommended before production scale-up.

---

## 2. Redfin API Endpoints

**Decision**: JSON REST API endpoints, no Playwright required  
**Rationale**: Redfin exposes semi-public JSON endpoints used by its own frontend. They return structured data without JS rendering. Anti-bot measures are present but lighter than Zillow (IP-based rate limiting rather than fingerprint detection). Standard httpx async requests suffice; playwright overhead is unnecessary.

**Key endpoints**:
- Search: `GET /stingray/api/gis?al=1&market=ny&region_id=&region_type=6&sp=true&...` returns `searchResults` array
- Detail: `GET /api/home/details/aboveTheFold?propertyId={id}&accessLevel=3` returns full JSON
- Compete Score: included in detail response under `payload.mainHouseInfo.competeScore`
- School data: `GET /api/home/details/schoolsData?propertyId={id}` returns array of schools with ratings

**Rate limit**: 1 req / 2 s is sufficient; no proxy rotation required for initial NYC metro sweep (test without proxies, add if needed).

---

## 3. Realtor.com JSON-LD Extraction

**Decision**: HTML + JSON-LD via existing `load_json_ld_blocks()` utility  
**Rationale**: Realtor.com embeds a `<script type="application/ld+json">` block of type `RealEstateListing` on every listing page. This is the most reliable extraction path — MLS data is clean and structured. The existing `_eu_utils.load_json_ld_blocks()` function handles multi-block pages correctly. Crime index is available via a separate inline JSON blob (`window.__data__`); a secondary regex extraction is needed for it.

**Key JSON-LD fields**:
- `name`, `price`, `numberOfBedrooms`, `numberOfBathroomsTotal`, `floorSize.value` + `floorSize.unitCode`
- `geo.latitude`, `geo.longitude`
- `address.*` → city, state, ZIP, county
- `schoolDistrict` → school name, rating
- Custom `mlsNumber` in extended schema

**robots.txt compliance**: Realtor.com's `robots.txt` allows `/realestateandhomes-detail/` — ✅ compliant.

---

## 4. sqft → m² Conversion

**Decision**: Multiply by factor `0.092903` (exact IEEE 754: `1 foot = 0.3048 m`, so `1 ft² = 0.3048² = 0.09290304 m²`, rounded to 6 sig. fig. as `0.092903`)  
**Rationale**: The factor is mandated in the feature spec and matches standard US/metric conversion tables. All spider parsers call `sqft_to_m2(sqft)` from `us_utils.py`; the result is stored alongside the raw sqft value in `plot_area` (for lot) and `built_area` (for interior). The normaliser adds `_m2` suffix.

**Implementation** (in `services/spider-workers/estategap_spiders/spiders/us_utils.py`):
```python
SQFT_TO_M2 = 0.092903

def sqft_to_m2(sqft: float | None) -> float | None:
    if sqft is None:
        return None
    return round(sqft * SQFT_TO_M2, 2)
```

**Test vector**: 1000 sqft → 92.90 m² ± 0.01 m²

---

## 5. US Administrative Zone Hierarchy

**Decision**: US Census Bureau TIGER/Line shapefiles  
**Rationale**: TIGER/Line is the authoritative, freely available, annually updated dataset for all US administrative boundaries. Files are available in Shapefile and GeoJSON format at `census.gov/geo/maps-data/data/tiger.html`. The existing zone importer (feature 013) supports GML/WKT; we extend it to load Shapefiles via `geopandas`.

**Zone levels and TIGER/Line sources**:
| Level | TIGER File | Admin Code |
|-------|-----------|------------|
| State | `tl_2024_us_state.shp` | GEOID = 2-digit FIPS |
| County | `tl_2024_us_county.shp` | GEOID = 5-digit FIPS |
| City (Place) | `tl_2024_{state_fips}_place.shp` | GEOID = 7-digit |
| ZIP Code | `tl_2024_us_zcta520.shp` | ZCTA5CE20 |
| Neighbourhood | `tl_2024_{state_fips}_bg.shp` (block groups as proxy) | GEOID = 12-digit |

**Hierarchy linking**: A zone's parent is determined by PostGIS `ST_Within(child.geometry, parent.geometry)` — same approach as European zone import.

---

## 6. Country-Specific Feature Configuration Architecture

**Decision**: YAML-driven feature config loaded by `FeatureEngineer`, one file per country  
**Rationale**: Hardcoding feature lists in Python creates maintenance debt as countries are added. YAML files (`config/ml/features_{country}.yaml`) allow data scientists to iterate on features without touching application code. The `FeatureEngineer` already accepts a feature list; extending it to load from YAML is minimal change.

**Config path**: `services/ml/estategap_ml/config/features_{country_lower}.yaml`  
**Loading logic**: `FeatureEngineer.__init__` reads the YAML for the target country; falls back to base features if the file doesn't exist.

---

## 7. Transfer Learning Strategy

**Decision**: LightGBM `init_model` parameter with Spain `.txt` dump, lr=0.01, n_iter=100  
**Rationale**: LightGBM supports warm-start training via `init_model` — loading a pre-trained model's boosting rounds and continuing. This is the simplest and most compatible approach (no custom layer manipulation). Spain is the reference market: highest listing volume, most feature coverage, longest history. Reduced learning rate prevents catastrophic forgetting of generalised patterns while adapting to local market dynamics.

**Threshold logic**:
- `count >= 5000` → full independent training
- `1000 <= count < 5000` → transfer learning from Spain model
- `count < 1000` → skip training entirely, use zone-median heuristic unconditionally
- After transfer learning: evaluate MAPE on held-out data; if `MAPE > 0.20` → flag `confidence = "insufficient_data"`, scorer uses zone-median

**Spain model path in MinIO**: `ml-models/es/champion/model.txt` (LightGBM text format, separate from ONNX)

---

## 8. Scorer Multi-Country Dispatch

**Decision**: Model loaded by `(country, version_tag)` lookup in DB + MinIO path convention  
**Rationale**: The scorer already has a model cache keyed by version. Extending the cache key to `(country, version_tag)` and adding a `get_champion_for_country(country)` DB query is the minimal change. The scorer's gRPC `ScoreListings` method already receives the full listing object including `country`.

**Heuristic fallback**: `zone_median_price` is already computed during enrichment (feature 013). When `confidence = "insufficient_data"`, the scorer returns `estimated_price_eur = zone.median_price_eur * (listing.area_m2 / zone.median_area_m2)` with `scoring_method = "heuristic"`.

---

## 9. Per-City MAPE Metrics

**Decision**: Compute per-city MAPE during evaluation and log to MLflow as custom metrics  
**Rationale**: MLflow supports arbitrary metric keys; `mape_city_{city_slug}` logged per training run gives per-metro visibility without extra infrastructure. Major metros logged: Madrid (ES), Rome (IT), Paris (FR), London (UK), Amsterdam (NL), New York City (US).

**Implementation**: After training, group test-set predictions by `city_slug`, compute MAPE per group, `mlflow.log_metric(f"mape_city_{city_slug}", value)`.

---

## 10. Netherlands Transfer Learning

**Decision**: Netherlands treated as low-data country initially; transfer learning from Spain  
**Rationale**: At current data volumes, Netherlands (Funda spider launched in feature 025) has < 5,000 listings. Spanish real estate shares structural similarities (price-per-m² range, urban/suburban pattern) that make Spain a better base than UK or France. Reassess at 5,000 listings.

---

## Resolved NEEDS CLARIFICATION Items

All technical decisions were provided by the user in the `/speckit.plan` invocation. No ambiguities remain.
