# Research: EU Portals & Enrichment

**Feature**: 025-eu-portals-enrichment  
**Phase**: 0 — Outline & Research  
**Date**: 2026-04-17

---

## 1. Spider Implementation Strategy per Portal

### Decision: Immobiliare.it — API-first with HTML fallback

- **Decision**: Primary strategy uses the Immobiliare.it JSON REST API (`/api/search/` endpoint), identical to the Idealista Spain pattern. HTML fallback with `parsel.Selector` for detail pages where the API doesn't return full field sets.
- **Rationale**: Immobiliare.it exposes a documented mobile/partner API that returns structured JSON with all listing fields (prezzo, superficie, locali, piano, ascensore, anno_costruzione, classe_energetica, coordinate). API responses are significantly faster and more reliable than HTML parsing.
- **Key mapping**: `prezzo` → asking_price, `superficie` → built_area_m2, `locali` → bedrooms, `bagni` → bathrooms, `piano` → floor_number, `anno_costruzione` → year_built, `classe_energetica` → energy_rating.
- **Alternatives considered**: Full HTML scraping (rejected — slower, fragile, higher bot-detection risk); Scrapy with Playwright (rejected — API approach makes browser automation unnecessary).

### Decision: Idealista IT — country-specific config, shared BaseSpider pattern

- **Decision**: Create `it_idealista.py` as a new file (not a fork of `es_idealista.py`), inheriting `BaseSpider`, with `COUNTRY = "IT"` and `PORTAL = "idealista"`. The Idealista API endpoint changes from `/3.5/es/` to `/3.5/it/`, and the bearer token is country-specific.
- **Rationale**: Sharing the exact same API SDK pattern avoids code divergence. A separate Python file is required because `COUNTRY` is a class variable; monkey-patching the Spanish spider would break the auto-registry keyed by `(country, portal)`.
- **Key mapping**: Identical to `es_idealista.yaml` for common fields; Italian-specific additions: `tipologiaImmobile`, `statoImmobile`, `riscaldamento` (heating type).
- **Alternatives considered**: Subclassing `IdealistaSpider` from Spain — rejected, would create import coupling between country spiders.

### Decision: SeLoger — Playwright mandatory

- **Decision**: Full Playwright-based scraping (no `httpx` direct approach). Extract JSON-LD blocks (`<script type="application/ld+json">`) from rendered HTML for listing data. Session cookie management handled by Playwright context persistence.
- **Rationale**: SeLoger applies aggressive bot detection (TLS fingerprinting, JS challenges). `playwright-stealth` plugin suppresses automation signals. JSON-LD structured data on SeLoger pages contains all key listing fields in a standardized format (schema.org RealEstateListing).
- **Key mapping**: JSON-LD `numberOfRooms` → bedrooms (this is the pièces field exposed via schema.org), `floorSize.value` → built_area_m2, `offers.price` → asking_price, `address` → address fields, `energyEfficiencyScaleMin` → energy_rating (DPE label A–G).
- **Alternatives considered**: Direct API reverse-engineering (rejected — authentication scheme changes frequently); headless HTML with requests-html (rejected — insufficient bot evasion).

### Decision: LeBonCoin — Playwright + session management

- **Decision**: Playwright-based scraping with persistent session cookies. HTML extraction using `parsel` after page render. Distinguish professional vs. private listings via the `pro` attribute on listing cards.
- **Rationale**: LeBonCoin uses Cloudflare and fingerprinting. Playwright with `playwright-stealth` and rotating residential proxies passes these checks. The `pro` boolean in listing JSON payload cleanly identifies seller type.
- **Key mapping**: `price.value` → asking_price, `attributes.rooms_count` → bedrooms, `attributes.square` → built_area_m2, `attributes.real_estate_type` → property_type, `location.lng/lat` → coordinates, `owner.type` → seller_type (pro/private).
- **Alternatives considered**: LeBonCoin unofficial API (rejected — requires device fingerprint auth).

### Decision: Bien'ici — HTML + embedded JSON

- **Decision**: Standard `httpx` requests (no Playwright needed). Extract `window.__PRELOADED_STATE__` JavaScript variable from HTML `<script>` tags using regex; parse as JSON.
- **Rationale**: Bien'ici has lighter bot protection than SeLoger/LeBonCoin. The preloaded state pattern (same as Fotocasa's `__NEXT_DATA__`) provides all listing fields in a structured JSON object without full JS execution.
- **Key mapping**: `bien.prixAffiche` → asking_price, `bien.nbPieces` → bedrooms (French pièces), `bien.surfaceTotal` → built_area_m2, `bien.typeBien` → property_type, `bien.dpe.classe` → energy_rating.
- **Alternatives considered**: Playwright (rejected — unnecessary overhead for lighter bot detection).

### Decision: Rightmove — BeautifulSoup + JSON-LD

- **Decision**: `httpx` requests + BeautifulSoup for HTML parsing. JSON-LD blocks (`<script type="application/ld+json">`) for structured listing data. Additional CSS selectors for UK-specific fields not in JSON-LD.
- **Rationale**: Rightmove is relatively scraper-friendly (no aggressive bot detection) and injects schema.org JSON-LD with core listing fields. CSS selectors target council tax band, EPC rating, and tenure (leasehold/freehold) from dedicated page sections.
- **Key mapping**: JSON-LD `offers.price` → asking_price (GBP), `numberOfRooms` → bedrooms, `floorSize.value` → built_area_m2. CSS selectors: `.dp-council-tax` → council_tax_band, `.dp-epc-rating` → epc_rating, `.dp-tenure` → tenure.
- **Currency**: `currency_field: GBP`. The normalization pipeline converts GBP → EUR using the existing exchange rate service (extended in feature 024).
- **Alternatives considered**: Rightmove unofficial API (rejected — CAPTCHA-gated, unreliable).

### Decision: Funda — HTML + embedded JSON, strict rate limiting

- **Decision**: `httpx` requests with 2-second enforced delay between requests (asyncio.sleep). Extract `window.__NUXT__` or `<script id="nuxt-data">` embedded JSON from HTML.
- **Rationale**: Funda rate-limits aggressively (429 responses after ~30 requests/minute). The 1 req/2s policy stays well within safe limits. Nuxt.js embedded data provides full listing fields without JS execution.
- **Rate limiting**: Spider config sets `request_min_delay: 2.0, request_max_delay: 2.5` for Funda specifically (overrides default 2-5s config via per-portal config).
- **Key mapping**: `price.amount` → asking_price (EUR), `livingArea` → built_area_m2, `numberOfRooms` → bedrooms, `constructionYear` → year_built, `energyLabel` → energy_rating, `address` → address fields, `latitude/longitude` → coordinates.
- **BAG integration**: Funda includes `bag_id` in listing JSON; pass this to `NetherlandsBAGEnricher` as a direct lookup key (faster than address matching).
- **Alternatives considered**: Funda API partner access (not available for scraping use case).

---

## 2. Enrichment Source Implementation

### Decision: FranceDVFEnricher — bulk CSV import + PostGIS spatial match

- **Decision**: Download the annual DVF CSV files from `data.gouv.fr` (~2GB/year cumulative since 2014). Import to a dedicated `dvf_transactions` PostgreSQL table with a PostGIS POINT geometry column. Match listings via `ST_DWithin(listing_geom, dvf_geom, 200)` (200m radius) + `property_type` filter. Return the 5 most recent transactions within range.
- **Table schema**:
  ```sql
  dvf_transactions (
    id            BIGSERIAL PRIMARY KEY,
    date_mutation DATE,
    valeur_fonciere NUMERIC(14,2),  -- sale price EUR
    type_local    VARCHAR(50),       -- property type
    surface_reelle_bati NUMERIC(8,2),
    adresse_full  TEXT,
    geom          GEOMETRY(POINT, 4326),
    postal_code   VARCHAR(10),
    commune       VARCHAR(150)
  )
  CREATE INDEX dvf_geom_idx ON dvf_transactions USING GIST(geom);
  ```
- **Match query**:
  ```sql
  SELECT date_mutation, valeur_fonciere, surface_reelle_bati, type_local
  FROM dvf_transactions
  WHERE ST_DWithin(geom::geography, ST_SetSRID(ST_MakePoint($lon, $lat), 4326)::geography, 200)
    AND type_local = $property_type
  ORDER BY date_mutation DESC
  LIMIT 5
  ```
- **Import script**: `scripts/import_dvf.py` — downloads CSV per year from data.gouv.fr API, geocodes addresses via BAN (Base Adresse Nationale) API, bulk-inserts via asyncpg `copy_records_to_table`.
- **Rationale**: PostGIS spatial index makes the 200m radius search fast even on 30M+ rows. Bulk import (not real-time scraping) avoids rate limits on the source.
- **Alternatives considered**: API-based DVF query (rejected — no public API for spatial queries on DVF data); address string matching (rejected — French address normalization is complex, spatial match is more reliable).

### Decision: UKLandRegistryEnricher — CSV import + rapidfuzz address matching

- **Decision**: Download Price Paid Data complete CSV from gov.uk (updated monthly). Import to `uk_price_paid` PostgreSQL table. Match by normalized address using `rapidfuzz.fuzz.token_sort_ratio` threshold ≥90. Fall back to postcode + price range if address similarity is 80–90%.
- **Table schema**:
  ```sql
  uk_price_paid (
    id              BIGSERIAL PRIMARY KEY,
    transaction_uid UUID,
    price_gbp       INTEGER,
    date_transfer   DATE,
    postcode        VARCHAR(8),
    property_type   CHAR(1),  -- D/S/T/F/O
    old_new         CHAR(1),  -- Y=new, N=established
    tenure          CHAR(1),  -- F=freehold, L=leasehold
    paon            TEXT,     -- primary address object name
    saon            TEXT,     -- secondary address object name
    street          TEXT,
    locality        TEXT,
    town_city       TEXT,
    district        TEXT,
    county          TEXT,
    address_full    TEXT GENERATED ALWAYS AS (...)
  )
  CREATE INDEX uk_pp_postcode_idx ON uk_price_paid (postcode);
  ```
- **Match logic**:
  1. Filter by postcode match (index scan)
  2. Apply rapidfuzz `token_sort_ratio` on normalized address vs. listing address
  3. Accept matches ≥90 similarity; return all matches with date and price
- **Import script**: `scripts/import_uk_land_registry.py` — downloads PP Complete CSV (~5GB), streams through csv.reader, bulk-inserts via asyncpg.
- **Rationale**: rapidfuzz is 10-20x faster than pure-Python difflib and handles common UK address variations (abbreviations, ordering). Postcode pre-filter dramatically reduces the candidate set before fuzzy match.
- **Alternatives considered**: Full geocoding + spatial match (rejected — UK Land Registry data lacks coordinates; geocoding 30M addresses is prohibitively expensive); Elasticsearch fuzzy search (rejected — adds infrastructure dependency).

### Decision: ItalyOMIEnricher — semi-annual OMI zone scrape + zone-level price bands

- **Decision**: Parse OMI (Osservatorio Mercato Immobiliare) open data from Agenzia delle Entrate website. Data is published as downloadable CSV/XLS per semester. Import to `omi_zones` table keyed by OMI zone code. Enrich listings by matching their PostGIS coordinates against OMI zone polygons, then attaching min/max €/m² for the relevant property type.
- **Table schema**:
  ```sql
  omi_zones (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    zona_omi     VARCHAR(20),      -- OMI zone code (e.g., "A1", "B3")
    comune_istat VARCHAR(10),      -- ISTAT municipality code
    period       VARCHAR(10),      -- "2024-H1", "2024-H2"
    tipologia    VARCHAR(50),      -- property type (abitazioni civili, etc.)
    price_min    NUMERIC(10,2),    -- €/m² minimum
    price_max    NUMERIC(10,2),    -- €/m² maximum
    geometry     GEOMETRY(MULTIPOLYGON, 4326)
  )
  CREATE INDEX omi_zones_geom_idx ON omi_zones USING GIST(geometry);
  ```
- **Enricher output**: `omi_zone_code`, `omi_price_min_eur_m2`, `omi_price_max_eur_m2`, `omi_period`, `price_vs_omi` (ratio: listing €/m² ÷ OMI midpoint).
- **Refresh**: Semi-annual; OMI enricher checks if data is older than 180 days and triggers a re-import.
- **Rationale**: OMI data is the official Italian government reference for property valuations, used by banks and notaries. Comparing listing prices against OMI ranges provides a deal-quality signal complementary to the ML score.
- **Alternatives considered**: Zone-level average from scraped listings (rejected — circular dependency; OMI is authoritative external reference).

### Decision: NetherlandsBAGEnricher — PDOK WFS API lookup

- **Decision**: Query the PDOK (Publieke Dienstverlening Op de Kaart) WFS service for BAG (Basisregistraties Adressen en Gebouwen) building data. Use Funda's `bag_id` field as a direct lookup key where available; fall back to address + postcode lookup.
- **Endpoint**: `https://service.pdok.nl/lv/bag/wfs/v2_0?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES=bag:pand&FILTER=...`
- **Response fields mapped**:
  - `bouwjaar` → year_built
  - `oppervlakte` → official_area_m2
  - `gebruiksdoel` → building_use (residential/commercial)
  - `geometry` (WKT) → building_geometry_wkt
- **Rate limiting**: PDOK WFS allows ~60 req/min; enricher uses asyncio.Semaphore(10) for concurrency control.
- **Rationale**: BAG is the authoritative Dutch address and building register. Building year and official area from BAG differ from portal-stated values in ~15% of listings (major enrichment signal).
- **Alternatives considered**: BAG bulk download (rejected — 8GB XML file; PDOK WFS API provides per-record lookups sufficient for real-time enrichment); third-party geocoding (rejected — BAG data is already official and free).

---

## 3. Zone Import Strategy

### Decision: GADM level-2/level-3 shapefiles + geopandas import

- **Decision**: Download GADM (gadm.org) GeoPackage files per country (GADM 4.1). Use geopandas to read and iterate features. Map GADM admin levels to platform zone levels:
  | Country | GADM level_0 | GADM level_1 | GADM level_2 | GADM level_3 |
  |---------|-------------|-------------|-------------|-------------|
  | Italy (IT) | country | regione | provincia | comune |
  | France (FR) | country | région | département | commune |
  | UK (GB) | country | country (ENG/SCT/WLS/NIR) | county | district |
  | Netherlands (NL) | country | provincie | gemeente | — |
  
  Platform zone levels: 0=country, 1=region, 2=province, 3=city.

- **Import script**: `scripts/import_gadm_zones.py` — reads GADM GeoPackage with `gpd.read_file("gadm_XX_gpkg")`, reprojects geometry to SRID 4326, generates slug from name, inserts with `asyncpg` bulk copy. Idempotent via `ON CONFLICT (slug) DO UPDATE`.
- **Geometry handling**: GADM provides MULTIPOLYGON geometry. Compute bbox from `geom.bounds`. Area from `geom.to_crs(epsg=3035).area / 1e6` (km²).
- **Rationale**: GADM is the standard open-access administrative boundary dataset covering all countries with consistent hierarchical levels. GeoPackage format is more efficient than individual shapefiles.
- **Alternatives considered**: OpenStreetMap Nominatim (rejected — no bulk boundary download; API rate limits); Eurostat NUTS regions (rejected — NUTS boundaries are statistical, not administrative; don't match common place names).

---

## 4. Currency Handling

### Decision: Extend existing exchange rate service for GBP

- **Decision**: The exchange rate cache introduced in feature 024 (for USD support) is extended to include GBP→EUR conversion. No new infrastructure required. The `NormalizedListing` already has `currency` (source) and `asking_price` (EUR-normalized) fields.
- **GBP-specific fields added to normalized listing**: `original_price_gbp`, `currency="GBP"`.
- **Rationale**: Reuses existing daily exchange rate refresh from ECB or similar source. GBP is treated identically to USD (another non-EUR currency already supported).

---

## 5. Field Completeness Tracking

### Decision: Completeness score computed in normalizer, stored on listing

- **Decision**: Each portal defines a set of "expected fields" in its YAML mapping. After normalization, the pipeline computes `completeness_score = populated_fields / expected_fields`. This existing mechanism requires no changes — only the new YAML files must declare which fields are expected.
- **Rationale**: The >75% completeness acceptance criterion from the spec maps directly to the existing `completeness_score` field on `NormalizedListing`. QA tests assert completeness ≥0.75 per portal.

---

## 6. Alembic Migrations Required

| Migration | Table | Purpose |
|-----------|-------|---------|
| `025_dvf_transactions.py` | `dvf_transactions` | France DVF historical sales |
| `026_uk_price_paid.py` | `uk_price_paid` | UK Land Registry transactions |
| `027_omi_zones.py` | `omi_zones` | Italy OMI zone price bands |
| (no new migration) | `zones` | GADM zones inserted via import script into existing table |

---

## 7. Testing Strategy

- **Spider unit tests**: Mock HTTP responses using `pytest-httpx`; assert `RawListing` field population and completeness.
- **Enricher unit tests**: Mock PostGIS queries and external API calls; assert `EnrichmentResult` fields.
- **Integration tests**: `testcontainers` PostgreSQL+PostGIS instance with seed data; test full enrichment pipeline per country.
- **Rate limiting tests**: Assert Funda spider never exceeds 0.5 req/s under controlled timing.
- **Zone import tests**: Load GADM fixture (small subset GeoJSON) into test DB; verify zone hierarchy traversal.
