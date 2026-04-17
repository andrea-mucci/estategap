# Feature Specification: US Portal Spiders & Country-Specific ML Models

**Feature Branch**: `026-us-spiders-country-ml`  
**Created**: 2026-04-17  
**Status**: Draft  

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Browse US Listings (Priority: P1)

A platform user searching for properties in the US market can see up-to-date listings from Zillow, Redfin, and Realtor.com with all US-specific fields — including Zestimate reference value, HOA fees, lot size, school ratings, and tax-assessed value — normalised alongside European listings so the same search, filter, and comparison tools work seamlessly.

**Why this priority**: Without US listings the entire US market is dark; this is the table-stakes deliverable for market expansion.

**Independent Test**: Deploy Zillow + Redfin spiders targeting NYC metro, verify ≥ 1,000 listings appear in the listings table with ≥ 70 % field completeness (area, price, bedrooms, bathrooms, location). US-specific fields (HOA, Zestimate, school rating) are present where available.

**Acceptance Scenarios**:

1. **Given** a spider run targeting NYC metro ZIP codes, **When** the Zillow spider completes, **Then** ≥ 1,000 listings are stored with `country = "US"`, prices in both USD and EUR, and area in both sqft and m².
2. **Given** a listing scraped from Redfin, **When** the normaliser processes it, **Then** `area_m2 = original_sqft × 0.092903` with tolerance ≤ 0.01 m².
3. **Given** a listing with HOA fees on Zillow, **When** the spider extracts it, **Then** `hoa_fees_monthly` is stored as a numeric USD value and available as an ML feature.
4. **Given** a Realtor.com listing with JSON-LD structured data, **When** the spider parses it, **Then** MLS ID, school rating, and crime index are extracted when present.

---

### User Story 2 - US Zone Hierarchy Navigation (Priority: P1)

A platform user can filter and browse US properties by state, county, city, ZIP code, and neighbourhood, matching the zone-based navigation available in European markets.

**Why this priority**: Zone-based search is the primary navigation metaphor; without it, US listings are unsearchable by geography.

**Independent Test**: Import TIGER/Line shapefiles for at least one US state (New York). Verify zones at all 5 administrative levels are importable and linkable to listings.

**Acceptance Scenarios**:

1. **Given** TIGER/Line shapefiles for New York state, **When** the zone importer runs, **Then** state, county, city, and ZIP code boundaries are stored in the `zones` table with `country = "US"` and valid PostGIS geometries.
2. **Given** a US listing with latitude/longitude, **When** zone assignment runs, **Then** the listing is associated with the correct ZIP code, city, county, and state zones.

---

### User Story 3 - Country-Specific Deal Scoring (Priority: P1)

Every listing in the platform — across Spain, Italy, France, UK, Netherlands, and USA — receives a deal score computed by a country-specific ML model that uses country-relevant features, so users get locally calibrated recommendations rather than a one-size-fits-all score.

**Why this priority**: Deal scoring is the platform's core value proposition; multi-country accuracy is required for credibility in each market.

**Independent Test**: Train a model for Spain (sufficient data), verify MAPE < 12 % on held-out Spanish listings. Train a model for USA using NYC metro data, verify MAPE < 12 %.

**Acceptance Scenarios**:

1. **Given** a country with ≥ 1,000 listings, **When** the training pipeline runs, **Then** an independent LightGBM model is trained using that country's feature set and exported to ONNX.
2. **Given** a Spanish model artefact stored in MinIO, **When** the scorer receives a US listing, **Then** it loads the US model (not the Spanish one) automatically based on `country` field.
3. **Given** per-country feature YAML files, **When** the trainer loads features for France, **Then** `dpe_rating` and `dvf_median_transaction_price` are included alongside base features; `hoa_fees` is not.
4. **Given** a country with < 5,000 listings but ≥ 1,000, **When** transfer learning is applied, **Then** the resulting model is initialised from the Spain model weights and fine-tuned with reduced learning rate and iteration count.

---

### User Story 4 - Low-Data Country Fallback (Priority: P2)

For markets where data volume is insufficient for reliable ML scoring (< 5,000 listings), the platform gracefully degrades to a zone-median heuristic, and operators are clearly notified of the model's confidence level.

**Why this priority**: Prevents misleading deal scores in thin markets; ensures product reliability before data volume grows.

**Independent Test**: Simulate a country with 2,000 listings. After transfer learning, if MAPE > 20 % the model is flagged "insufficient data" and the scorer falls back to zone-median pricing for that country.

**Acceptance Scenarios**:

1. **Given** a country with 2,000 listings where transfer-learned model MAPE > 20 %, **When** the scorer evaluates a listing from that country, **Then** it returns a zone-median-based estimate with `scoring_method = "heuristic"`.
2. **Given** a model flagged as "insufficient data", **When** the training pipeline runs again and country listing count exceeds 5,000, **Then** a full independent model is trained and the flag is cleared.

---

### Edge Cases

- What happens when Zillow's `__NEXT_DATA__` JSON structure changes between scrape runs?
- How does the system handle a listing without HOA fees (null vs zero)?
- What if a US listing's geolocation falls outside any TIGER/Line zone boundary (e.g., water areas, territories)?
- How does sqft → m² conversion handle listings where area is given as a range (e.g., "1,200–1,400 sqft")?
- What happens when the Spain model artefact is unavailable in MinIO during transfer learning initialisation?
- How does the scorer handle a listing for a country whose model has never been trained?

## Requirements *(mandatory)*

### Functional Requirements

**US Spider Requirements**

- **FR-001**: The Zillow spider MUST use Playwright with stealth mode and residential US proxies, rate-limited to 1 request per 3 seconds.
- **FR-002**: The Zillow spider MUST extract listing data from `__NEXT_DATA__` JSON embedded in page source, including: price (USD), area (sqft), bedrooms, bathrooms, lot size (sqft), HOA fees (monthly USD), Zestimate, tax history, and geolocation.
- **FR-003**: The Redfin spider MUST consume JSON API endpoints (`/api/home/details/...`) and extract: price, area (sqft), bedrooms, bathrooms, Compete Score, school ratings, and geolocation.
- **FR-004**: The Realtor.com spider MUST parse HTML + JSON-LD structured data to extract: price, area (sqft), bedrooms, bathrooms, MLS ID, school info, crime index, and geolocation.
- **FR-005**: All US spiders MUST convert sqft to m² using the factor 0.092903 and store both values.
- **FR-006**: All US spiders MUST store prices in USD (original currency) and EUR (converted at current exchange rate).
- **FR-007**: All US listings MUST conform to the unified listing schema (`country = "US"`) and be published to the existing NATS ingestion stream.

**US Zone Import Requirements**

- **FR-008**: The zone importer MUST support US Census Bureau TIGER/Line shapefiles for state, county, city, and ZIP code boundaries.
- **FR-009**: Imported US zones MUST be stored in the existing `zones` table with `country = "US"` and valid PostGIS geometry.
- **FR-010**: Every US listing MUST be assigned to the correct zone at all 5 administrative levels (state, county, city, ZIP, neighbourhood) via geospatial point-in-polygon lookup.

**Country-Specific ML Model Requirements**

- **FR-011**: The training pipeline MUST load country-specific feature sets from `config/ml/features_{country}.yaml` files.
- **FR-012**: The training pipeline MUST train an independent LightGBM model for each active country with ≥ 1,000 listings.
- **FR-013**: Each country feature YAML MUST define: base features (shared), country-specific optional features, and feature encoding rules.
- **FR-014**: Country-specific features MUST include at minimum:
  - Spain: `energy_cert_encoded`, `has_elevator`, `community_fees`, `orientation_encoded`
  - France: `dpe_rating`, `dvf_median_transaction_price`, `pièces`
  - UK: `council_tax_band_encoded`, `epc_rating`, `leasehold_flag`, `land_registry_last_price`
  - USA: `hoa_fees`, `lot_size_m2`, `tax_assessed_value`, `school_rating`, `zestimate_reference`
  - Italy: `ape_rating`, `omi_zone_min_price`, `omi_zone_max_price`
- **FR-015**: Trained models MUST be exported to ONNX format and stored in MinIO with country-keyed paths.
- **FR-016**: The ML scorer MUST automatically load the correct country model based on the `country` field of the listing being scored.

**Transfer Learning Requirements**

- **FR-017**: For countries with ≥ 1,000 and < 5,000 listings, the trainer MUST apply transfer learning: initialise from the Spain LightGBM model (`.txt` format via `init_model`) with learning rate 0.01 and maximum 100 iterations.
- **FR-018**: After transfer learning, if the resulting model's MAPE on held-out data exceeds 20 %, the trainer MUST flag the model as `confidence = "insufficient_data"` and the scorer MUST fall back to zone-median heuristic for that country.
- **FR-019**: When a previously flagged country's listing count grows to ≥ 5,000, the next training run MUST retrain a full independent model and clear the flag.

### Key Entities

- **USListing**: A property listing scraped from a US portal, extending the unified listing schema with `hoa_fees_monthly`, `lot_size_m2`, `tax_assessed_value`, `school_rating`, `zestimate_reference`, `compete_score`, `mls_id`.
- **CountryFeatureConfig**: A YAML-backed configuration entity defining base and country-specific ML features, encoding rules, and optional feature flags per country code.
- **ModelVersion**: Existing entity extended with `transfer_learned: bool`, `base_country: str | null`, `confidence: "full" | "transfer" | "insufficient_data"`.
- **USAdminZone**: A zone record at one of 5 US administrative levels (state, county, city, ZIP, neighbourhood) derived from TIGER/Line shapefiles.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zillow spider produces ≥ 1,000 US listings from the NYC metro area per run with ≥ 70 % field completeness across price, area, bedrooms, bathrooms, and location.
- **SC-002**: Redfin spider produces ≥ 1,000 US listings from the NYC metro area per run with ≥ 70 % field completeness.
- **SC-003**: sqft → m² conversion is accurate to within 0.01 m² for all tested values.
- **SC-004**: ML model MAPE is < 12 % for each country with a fully trained independent model (Spain, Italy, France, UK, Netherlands, USA) on a held-out test set.
- **SC-005**: Per-city MAPE metrics are computed and logged for major metros (Madrid, Rome, Paris, London, Amsterdam, NYC) in each training run.
- **SC-006**: The scorer correctly routes each listing to its country-specific model with zero misrouting on a 1,000-listing multi-country test set.
- **SC-007**: Transfer-learned models for low-data countries produce reasonable estimates (MAPE < 20 %) or correctly trigger the heuristic fallback.
- **SC-008**: US zone import covers all 50 states with valid PostGIS geometry and correct 5-level hierarchy.

## Assumptions

- The existing spider worker framework (`services/spiders/`) and NATS ingestion stream are operational; US spiders will register as new workers within that framework.
- Residential US proxies are available via the existing proxy rotation configuration used by other Playwright-based spiders.
- Spain has sufficient historical listings (≥ 5,000) to serve as the transfer learning base model for low-data countries.
- Exchange rate for USD → EUR is fetched from the existing currency conversion service and cached.
- The ML trainer can access PostgreSQL read replica and MinIO for training data and artefact storage respectively.
- Netherlands is treated as a low-data country (< 5,000 listings) and will use transfer learning from Spain model initially.
- County assessor data integration is out of scope for this feature; `tax_assessed_value` is sourced from portal scraping only.
- Zillow's `__NEXT_DATA__` JSON schema is assumed stable within the scope of this feature; schema-change detection is handled by existing spider health monitoring.
