# Feature Specification: EU Portals & Enrichment

**Feature Branch**: `025-eu-portals-enrichment`
**Created**: 2026-04-17
**Status**: Draft
**Input**: User description: "Implement spiders for the top European real estate portals and country-specific data enrichment sources."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Browse Italian Listings (Priority: P1)

A buyer searching for property in Italy opens the EstateGap dashboard, selects Italy as the country, and finds listings aggregated from both Immobiliare.it and Idealista IT, with Italian field labels resolved to unified attributes (surface area, rooms, bathrooms, floor, energy class, condition).

**Why this priority**: Italy is the first new country unlocked. Without functional Italian spiders, no Italian data reaches the pipeline. This is the gate for all downstream Italian features.

**Independent Test**: Run both Italian spiders against their target portals, verify 1000+ listings each are ingested with >75% completeness, and confirm field mappings (superficie → built_area_m2, locali → bedrooms, classe energetica → energy_rating).

**Acceptance Scenarios**:

1. **Given** the Immobiliare.it spider is deployed, **When** it scrapes a search page for Rome apartments, **Then** it returns listings with price (EUR), area (m²), rooms, floor, geo-coordinates, and source URL populated.
2. **Given** a listing scraped from Idealista IT, **When** it is normalized, **Then** the property_type, condition, and energy_rating fields match the Idealista Italian field vocabulary.

---

### User Story 2 - Browse French Listings (Priority: P1)

A French buyer uses EstateGap to search for property in Paris and surrounding areas. Listings from SeLoger, LeBonCoin Immobilier, and Bien'ici are unified under the French country view. The pièces (rooms) count maps correctly to the platform's bedrooms field. Both professional agency listings and private-seller listings (LeBonCoin) are visible.

**Why this priority**: France has the highest listing volume across 3 portals. Correct handling of the French field vocabulary (pièces, surface habitable, DPE rating) is required before any France-specific enrichment.

**Independent Test**: Run each French spider independently. Confirm pièces → bedrooms mapping, DPE energy rating extraction, and that LeBonCoin returns both `pro` and `particulier` listing types.

**Acceptance Scenarios**:

1. **Given** a SeLoger listing page, **When** scraped, **Then** pièces count is correctly mapped to the bedrooms field and DPE rating is captured as energy_rating.
2. **Given** a LeBonCoin search result, **When** processed, **Then** both professional and private seller listings appear with seller_type identified.
3. **Given** 1000 Paris listings ingested, **When** the France DVF enricher runs, **Then** ≥60% of listings are enriched with nearby historical transaction prices.

---

### User Story 3 - Browse UK Listings (Priority: P2)

A UK property investor opens EstateGap, selects the UK, and browses Rightmove listings. Each listing displays GBP asking price alongside the EUR-normalized price. Property-specific UK attributes — council tax band, EPC energy rating, and leasehold/freehold tenure — are visible in the listing detail.

**Why this priority**: The UK requires currency handling (GBP → EUR conversion) and country-specific legal fields (leasehold, council tax) not present in other markets.

**Independent Test**: Scrape Rightmove for 1000 London listings. Verify GBP prices are captured as original_price with currency=GBP, EUR-normalized price is computed, and at least 70% have leasehold/freehold tenure identified.

**Acceptance Scenarios**:

1. **Given** a Rightmove listing with a GBP price, **When** ingested, **Then** the listing record stores both the GBP original price and the EUR-normalized price.
2. **Given** a leasehold property on Rightmove, **When** scraped, **Then** tenure=leasehold is captured and years_remaining is extracted when present.
3. **Given** 1000 London listings, **When** the UK Land Registry enricher runs, **Then** ≥70% are matched to historical transaction records within 90% address similarity.

---

### User Story 4 - Browse Dutch Listings (Priority: P2)

A user searching for property in Amsterdam finds Funda listings on EstateGap with Dutch-specific attributes including BAG (Basisregistraties Adressen en Gebouwen) building data — official year of construction, official floor area, and building type — cross-referenced against the portal's stated figures.

**Why this priority**: Funda is the dominant Dutch portal. BAG enrichment adds verified government building data, a key differentiator for the Dutch market.

**Independent Test**: Run the Funda spider for 1000 Amsterdam listings with strict 1 req/2s rate limiting. Confirm BAG enrichment attaches year_built and official_area_m2 from the PDOK API.

**Acceptance Scenarios**:

1. **Given** a Funda listing with an Amsterdam address, **When** the BAG enricher runs, **Then** it returns the official year_built, official area, and building_type from the Dutch government register.
2. **Given** the Funda spider crawling at full speed, **When** monitored over 10 minutes, **Then** the request rate does not exceed 0.5 requests/second to avoid rate-limit blocks.

---

### User Story 5 - Zone Hierarchy Navigation (Priority: P3)

A user browsing EstateGap can navigate the zone hierarchy for Italy, France, UK, and Netherlands — selecting a country, then region, province/county, and city — and see listings count per zone.

**Why this priority**: Zone hierarchies are required for the dashboard map and zone-based analytics. Without zone data for new countries, listings cannot be associated with browsable geographic units.

**Independent Test**: Import GADM zone data for all 4 new countries. Verify 4-level hierarchy (country → region → province → city) is navigable via the zones API endpoint for each country.

**Acceptance Scenarios**:

1. **Given** GADM shapefiles imported for France, **When** the zones API is queried for level=1 (regions), **Then** 13 metropolitan regions are returned with correct geometry.
2. **Given** a UK listing with a known postcode, **When** zone assignment runs, **Then** the listing is associated with the correct county and city zone.

---

### Edge Cases

- What happens when a portal returns a listing with missing price or area? → Listing is ingested with available fields; completeness score reflects missing fields; downstream pipeline skips enrichment requiring those fields.
- How does the system handle GBP→EUR conversion when exchange rate service is unavailable? → Last known rate from cache is used; staleness is flagged on the listing record.
- What happens when the France DVF CSV download fails or is partially corrupted? → Import job logs failure, retries up to 3 times; enricher falls back to "no_match" status without blocking listing ingestion.
- How does LeBonCoin session management handle expired sessions mid-scrape? → Session refresh is triggered automatically; the request is retried once with the new session before the URL is quarantined.
- What happens when PDOK WFS API is unavailable for BAG lookups? → NetherlandsBAGEnricher returns status="failed"; listing is ingested without BAG data; enrichment retry is scheduled.

## Requirements *(mandatory)*

### Functional Requirements

**Spiders**

- **FR-001**: System MUST implement an Immobiliare.it spider using the portal's JSON API as the primary data source, with HTML fallback.
- **FR-002**: System MUST implement an Idealista IT spider reusing the existing Idealista Spain codebase with country=IT and Italian-specific field mappings.
- **FR-003**: System MUST implement a SeLoger spider using Playwright for anti-bot bypass, extracting listing data from JSON-LD embedded in HTML.
- **FR-004**: System MUST implement a LeBonCoin spider using Playwright with session management, capturing both professional and private seller listings.
- **FR-005**: System MUST implement a Bien'ici spider using HTML parsing with embedded JSON extraction.
- **FR-006**: System MUST implement a Rightmove spider using BeautifulSoup HTML parsing and JSON-LD structured data, capturing council tax band, EPC rating, and leasehold/freehold tenure.
- **FR-007**: System MUST implement a Funda spider with a maximum request rate of 0.5 requests/second (1 req/2s), using HTML parsing with embedded JSON data.
- **FR-008**: All spiders MUST extend BaseSpider and auto-register in the spider registry upon class definition.
- **FR-009**: Each spider MUST have a corresponding YAML field mapping file defining source field → unified field translations.
- **FR-010**: Each spider MUST have a separate parser module for field extraction logic.
- **FR-011**: All spiders MUST store prices in the original currency AND as EUR-normalized values.
- **FR-012**: French spiders MUST map pièces to the bedrooms field.
- **FR-013**: UK spider MUST capture council_tax_band, epc_rating, tenure (leasehold/freehold), and leasehold_years_remaining.

**Enrichment**

- **FR-014**: System MUST implement a FranceDVFEnricher that imports the DVF open transaction dataset (data.gouv.fr) into a dedicated PostgreSQL table and matches listings by geographic proximity (≤200m) and property type.
- **FR-015**: FranceDVFEnricher MUST return the 5 nearest historical transactions with their prices for each matched listing.
- **FR-016**: System MUST implement a UKLandRegistryEnricher that imports Price Paid Data CSV files and matches listings by normalized address with a similarity threshold of ≥90%.
- **FR-017**: System MUST implement an ItalyOMIEnricher that imports Agenzia delle Entrate OMI zone reference price ranges (min/max €/m²) and compares each listing's asking price against the OMI range for its zone.
- **FR-018**: System MUST implement a NetherlandsBAGEnricher that queries the PDOK WFS API by address/postcode and returns official year_built, floor area, building type, and geometry.
- **FR-019**: All enrichers MUST register with the country-based enricher registry using the @register_enricher decorator.

**Zone Import**

- **FR-020**: System MUST import GADM administrative zone shapefiles for Italy (IT), France (FR), United Kingdom (GB), and Netherlands (NL).
- **FR-021**: Zone import MUST map GADM administrative levels to platform zone levels (country=0, region=1, province=2, city=3).
- **FR-022**: Imported zones MUST include name, name_local, geometry (MULTIPOLYGON), bbox, area_km2, and OSM ID where available.
- **FR-023**: Zone import script MUST be idempotent (re-runnable without creating duplicates).

### Key Entities

- **DVFTransaction**: A historical French property sale record from the Demandes de Valeurs Foncières open dataset. Key attributes: sale date, price, address, floor area, property type, geo-coordinates.
- **UKTransaction**: A UK property sale from the Land Registry Price Paid Data. Key attributes: transaction date, price (GBP), full address, property type, tenure.
- **OMIZone**: An Italian Agenzia delle Entrate reference price zone. Key attributes: zone code, zone name, property type, min €/m², max €/m², period (semi-annual).
- **BAGBuilding**: A Dutch government building register record. Key attributes: BAG ID, address, official floor area (m²), year built, building type, geometry.
- **AdministrativeZone**: An existing platform entity extended with data for Italy, France, UK, Netherlands (4-level hierarchy).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Each of the 7 new portal spiders scrapes ≥1,000 listings per run with ≥75% data completeness (fields populated / total expected fields).
- **SC-002**: French field mapping is correct: pièces maps to bedrooms for 100% of French listings.
- **SC-003**: UK listings carry GBP original price and EUR-normalized price for 100% of Rightmove listings.
- **SC-004**: ≥60% of Paris listings are enriched with at least one nearby DVF historical transaction.
- **SC-005**: ≥70% of London listings are matched to at least one UK Land Registry transaction record.
- **SC-006**: Zone hierarchies for Italy, France, UK, and Netherlands are fully navigable (4 levels) via the zones API, with geometry data for all imported zones.
- **SC-007**: Funda spider does not exceed 0.5 requests/second under normal operation.
- **SC-008**: All 7 spiders respect robots.txt and operate with geo-targeted proxy rotation.

## Assumptions

- Existing BaseSpider, BaseEnricher, and enricher registry infrastructure (from feature 011 and 013) are in production and stable; this feature adds new implementations without modifying the base interfaces.
- The Idealista IT spider reuses the existing Idealista Spain spider codebase with a country_code=IT override and separate YAML mapping; a new file is created rather than modifying the Spain spider.
- EUR exchange rates for GBP→EUR conversion are provided by an existing exchange rate service (introduced in feature 024 for USD handling); GBP is added as a new supported source currency.
- GDPR compliance for scraped personal data (private seller listings from LeBonCoin) is handled at the pipeline normalization layer (feature 012) and is out of scope for this feature.
- DVF and UK Land Registry bulk data imports are one-time initial loads followed by incremental updates; the initial bulk import (~2GB DVF, ~5GB Land Registry) is handled by a one-off import script, not a real-time scraper.
- OMI data is updated semi-annually; the ItalyOMIEnricher includes a scheduled refresh mechanism but the refresh schedule configuration is handled by the scrape orchestrator (feature 010), not this feature.
- GADM shapefiles are downloaded manually and placed in a designated import directory; the zone import script reads from this directory. Automated GADM download is out of scope.
- Mobile support and frontend changes for new countries are out of scope for this feature; existing country-agnostic frontend components handle new countries automatically.
