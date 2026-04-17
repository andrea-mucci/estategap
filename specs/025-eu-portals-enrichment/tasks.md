# Tasks: EU Portals & Enrichment

**Input**: Design documents from `specs/025-eu-portals-enrichment/`
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/ ✅, quickstart.md ✅

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.
**Tests**: Included for spiders and enrichers per the acceptance criteria in spec.md.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no unresolved dependencies)
- **[Story]**: Which user story this task belongs to (US1–US5)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependencies, migrations, and registry wiring that unblock all user stories.

- [X] T001 Add new Python dependencies to `services/spider-workers/pyproject.toml`: beautifulsoup4 4.12+, playwright 1.43+, playwright-stealth, pytest-httpx 0.30+
- [X] T002 Add new Python dependencies to `services/pipeline/pyproject.toml`: rapidfuzz 3.6+, geopandas 0.14+, pytest-httpx 0.30+
- [ ] T003 [P] Install Playwright Chromium browser: `uv run playwright install chromium` in `services/spider-workers/`
- [X] T004 Create Alembic migration `services/pipeline/alembic/versions/025_eu_listing_fields.py` adding new listing columns: `council_tax_band`, `epc_rating`, `tenure`, `leasehold_years_remaining`, `seller_type`, `omi_zone_code`, `omi_price_min_eur_m2`, `omi_price_max_eur_m2`, `omi_period`, `price_vs_omi`, `bag_id`, `dvf_nearby_count`, `dvf_median_price_m2`, `uk_lr_match_count`, `uk_lr_last_price_gbp`, `uk_lr_last_date`
- [X] T005 [P] Create Alembic migration `services/pipeline/alembic/versions/025_dvf_transactions.py` — table `dvf_transactions` with GIST index on `geom`
- [X] T006 [P] Create Alembic migration `services/pipeline/alembic/versions/026_uk_price_paid.py` — table `uk_price_paid` with indexes on `postcode` and `transaction_uid`
- [X] T007 [P] Create Alembic migration `services/pipeline/alembic/versions/027_omi_zones.py` — table `omi_zones` with GIST index on `geometry`
- [ ] T008 Run `uv run alembic upgrade head` in `services/pipeline/` to apply all four migrations
- [X] T009 Add GBP currency support to exchange rate service: update `services/pipeline/src/pipeline/currency.py` (or equivalent) to handle `currency="GBP"` → EUR conversion alongside existing USD support

**Checkpoint**: Dependencies installed, all migrations applied, GBP conversion available.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Base configuration and registry wiring required before any spider or enricher can run.

**⚠️ CRITICAL**: No user story work begins until this phase is complete.

- [X] T010 [P] Create test fixture directory `services/spider-workers/tests/fixtures/` with empty `__init__.py`
- [X] T011 [P] Create test fixture directory `services/pipeline/tests/enricher/` with empty `__init__.py`
- [X] T012 [P] Create `services/pipeline/tests/integration/` directory with empty `__init__.py` and `conftest.py` (testcontainers PostgreSQL+PostGIS setup)
- [X] T013 Create `services/spider-workers/tests/spiders/conftest.py` with shared `pytest-httpx` fixtures and a factory for building `RawListing` test objects
- [X] T014 Create `services/pipeline/tests/enricher/conftest.py` with shared asyncpg test connection fixture and `NormalizedListing` factory

**Checkpoint**: Foundation ready — all story phases can now begin.

---

## Phase 3: User Story 1 — Italian Listings (Priority: P1) 🎯 MVP

**Goal**: Immobiliare.it and Idealista IT spiders scrape Italian listings; field mappings (superficie, locali, classe energetica, etc.) correctly populate the unified listing schema.

**Independent Test**: Run both Italian spiders for 5 pages in Rome, confirm ≥75% completeness score per listing, and verify `bedrooms`, `built_area_m2`, `energy_rating`, and `property_type` fields are populated.

### Tests for User Story 1

- [X] T015 [P] [US1] Create `services/spider-workers/tests/fixtures/it_immobiliare_search.json` — mock Immobiliare.it API response with 3 representative listings (appartamento, villa, ufficio)
- [X] T016 [P] [US1] Create `services/spider-workers/tests/fixtures/it_immobiliare_detail.html` — mock detail page HTML with JSON-LD block
- [X] T017 [P] [US1] Create `services/spider-workers/tests/fixtures/it_idealista_search.json` — mock Idealista IT API response

### Implementation for User Story 1

- [X] T018 [P] [US1] Create `services/pipeline/config/mappings/it_immobiliare.yaml` — full field mapping: prezzo→asking_price, superficie→built_area_m2, locali→bedrooms, bagni→bathrooms, piano→floor_number, annoCostruzione→year_built, classeEnergetica→energy_rating, tipologia→property_type (with property_type_map and condition_map), latitudine/longitudine→_lat/_lon; set `expected_fields` list for completeness scoring
- [X] T019 [P] [US1] Create `services/pipeline/config/mappings/it_idealista.yaml` — Idealista IT field mapping (same structure as `es_idealista.yaml` but with Italian field names: precio→prezzo etc., COUNTRY=IT); include `tipologiaImmobile`, `statoImmobile`, `riscaldamento`
- [X] T020 [P] [US1] Create `services/spider-workers/estategap_spiders/spiders/it_immobiliare_parser.py` — pure functions: `parse_search_result(item: dict) -> dict` and `parse_detail_page(html: str) -> dict`
- [X] T021 [P] [US1] Create `services/spider-workers/estategap_spiders/spiders/it_idealista_parser.py` — pure functions: `parse_api_response(data: dict) -> dict` and `parse_detail_page(html: str) -> dict`
- [X] T022 [US1] Create `services/spider-workers/estategap_spiders/spiders/it_immobiliare.py` — `ImmobiliareSpider(BaseSpider)` with `COUNTRY="IT"`, `PORTAL="immobiliare"`, `API_BASE="https://www.immobiliare.it/api/v1"`; implement `scrape_search_page()` (JSON API primary, HTML fallback via parsel), `scrape_listing_detail()`, `detect_new_listings()` (sort by publicationDate desc)
- [X] T023 [US1] Create `services/spider-workers/estategap_spiders/spiders/it_idealista.py` — `IdealistaITSpider(BaseSpider)` with `COUNTRY="IT"`, `PORTAL="idealista"`, API endpoint `/3.5/it/`; implement all 3 abstract methods reusing Idealista API pattern from `es_idealista.py`
- [X] T024 [US1] Register both Italian spiders in `services/spider-workers/estategap_spiders/spiders/__init__.py`: add `from estategap_spiders.spiders.it_immobiliare import ImmobiliareSpider` and `from estategap_spiders.spiders.it_idealista import IdealistaITSpider`
- [X] T025 [US1] Create `services/spider-workers/tests/spiders/test_it_immobiliare.py` — unit tests using `pytest-httpx`: test `scrape_search_page()` parses fixture JSON correctly, test field completeness ≥75%, test `property_type_map` for all known tipologia values, test HTML fallback path
- [X] T026 [US1] Create `services/spider-workers/tests/spiders/test_it_idealista.py` — unit tests: test API response parsing, test Italian field name mapping, test `detect_new_listings()` dedup against Redis mock

**Checkpoint**: `get_spider("IT", "immobiliare")` and `get_spider("IT", "idealista")` return spider classes; both spiders scrape and produce `RawListing` objects with ≥75% completeness.

---

## Phase 4: User Story 2 — French Listings (Priority: P1)

**Goal**: SeLoger, LeBonCoin, and Bien'ici spiders scrape French listings with correct pièces→bedrooms mapping and DPE energy rating; FranceDVFEnricher enriches ≥60% of Paris listings with nearby transaction prices.

**Independent Test**: Run each French spider for 3 pages in Paris. Confirm `bedrooms` = pièces count for all listings. Run DVF enricher on 100 Paris listings; confirm ≥60% return `dvf_nearby_count > 0`.

### Tests for User Story 2

- [X] T027 [P] [US2] Create `services/spider-workers/tests/fixtures/fr_seloger_detail.html` — mock Playwright-rendered SeLoger listing page with JSON-LD RealEstateListing block
- [X] T028 [P] [US2] Create `services/spider-workers/tests/fixtures/fr_leboncoin_search.html` — mock LeBonCoin search results page with both `pro` and `particulier` listing cards
- [X] T029 [P] [US2] Create `services/spider-workers/tests/fixtures/fr_bienici_search.html` — mock Bien'ici page with `window.__PRELOADED_STATE__` JSON block
- [X] T030 [P] [US2] Create `services/pipeline/tests/enricher/fixtures/dvf_sample.sql` — seed SQL with 50 DVF transactions around Paris coordinates for enricher tests

### Implementation for User Story 2 — Spiders

- [X] T031 [P] [US2] Create `services/pipeline/config/mappings/fr_seloger.yaml` — field mapping: JSON-LD `numberOfRooms`→bedrooms, `floorSize.value`→built_area_m2, `offers.price`→asking_price (EUR), `energyEfficiencyScaleMin`→energy_rating (DPE A–G); set `country_uses_pieces: true`
- [X] T032 [P] [US2] Create `services/pipeline/config/mappings/fr_leboncoin.yaml` — field mapping: `price.value`→asking_price, `attributes.rooms_count`→bedrooms, `attributes.square`→built_area_m2, `attributes.real_estate_type`→property_type, `location.lng/lat`→coordinates, `owner.type`→seller_type; set `country_uses_pieces: true`
- [X] T033 [P] [US2] Create `services/pipeline/config/mappings/fr_bienici.yaml` — field mapping from `window.__PRELOADED_STATE__`: `bien.prixAffiche`→asking_price, `bien.nbPieces`→bedrooms, `bien.surfaceTotal`→built_area_m2, `bien.typeBien`→property_type, `bien.dpe.classe`→energy_rating; set `country_uses_pieces: true`
- [X] T034 [P] [US2] Create `services/spider-workers/estategap_spiders/spiders/fr_seloger_parser.py` — `parse_json_ld(html: str) -> dict` extracting schema.org RealEstateListing from `<script type="application/ld+json">` blocks; `parse_search_page(html: str) -> list[dict]`
- [X] T035 [P] [US2] Create `services/spider-workers/estategap_spiders/spiders/fr_leboncoin_parser.py` — `parse_listing_card(card: Tag) -> dict` using BeautifulSoup; `detect_seller_type(card: Tag) -> str` returning "pro" or "private"
- [X] T036 [P] [US2] Create `services/spider-workers/estategap_spiders/spiders/fr_bienici_parser.py` — `extract_preloaded_state(html: str) -> dict` using regex on `window.__PRELOADED_STATE__`; `parse_listing(data: dict) -> dict`
- [X] T037 [US2] Create `services/spider-workers/estategap_spiders/spiders/fr_seloger.py` — `SeLogerSpider(BaseSpider)` with `COUNTRY="FR"`, `PORTAL="seloger"`; uses `playwright-stealth` Playwright context for page render; extract JSON-LD via parser; implement all 3 abstract methods
- [X] T038 [US2] Create `services/spider-workers/estategap_spiders/spiders/fr_leboncoin.py` — `LeBonCoinSpider(BaseSpider)` with `COUNTRY="FR"`, `PORTAL="leboncoin"`; Playwright + persistent session cookies; parse both pro and private listing cards; implement all 3 abstract methods
- [X] T039 [US2] Create `services/spider-workers/estategap_spiders/spiders/fr_bienici.py` — `BienIciSpider(BaseSpider)` with `COUNTRY="FR"`, `PORTAL="bienici"`; httpx requests + regex extraction of `window.__PRELOADED_STATE__`; implement all 3 abstract methods
- [X] T040 [US2] Register all 3 French spiders in `services/spider-workers/estategap_spiders/spiders/__init__.py`

### Implementation for User Story 2 — DVF Enricher

- [X] T041 [US2] Create `scripts/import_dvf.py` — CLI script: downloads annual DVF CSV files from `data.gouv.fr`, geocodes addresses via BAN API (batch), bulk-inserts to `dvf_transactions` via asyncpg `copy_records_to_table`; supports `--year-from` / `--year-to` args; idempotent via `ON CONFLICT (date_mutation, adresse_full, valeur_fonciere) DO NOTHING`
- [X] T042 [US2] Create `services/pipeline/src/pipeline/enricher/fr_dvf.py` — `FranceDVFEnricher(BaseEnricher)` decorated with `@register_enricher("FR")`; implement `enrich()`: parse `listing.location_wkt` for (lon, lat), run `ST_DWithin` PostGIS query within 200m matching `type_local` to listing property_type, return `EnrichmentResult` with `dvf_nearby_count` and `dvf_median_price_m2`
- [X] T043 [US2] Register `FranceDVFEnricher` in `services/pipeline/src/pipeline/enricher/__init__.py`
- [X] T044 [US2] Create `services/spider-workers/tests/spiders/test_fr_seloger.py` — unit tests with `pytest-httpx`: test JSON-LD extraction, pièces→bedrooms mapping, DPE rating extraction
- [X] T045 [US2] Create `services/spider-workers/tests/spiders/test_fr_leboncoin.py` — unit tests: test pro vs private seller_type detection, pièces mapping
- [X] T046 [US2] Create `services/spider-workers/tests/spiders/test_fr_bienici.py` — unit tests: test `__PRELOADED_STATE__` extraction, pièces mapping
- [X] T047 [US2] Create `services/pipeline/tests/enricher/test_fr_dvf.py` — unit tests with mocked asyncpg: test spatial match returns ≤5 results, test `no_match` when no DVF rows within 200m, test median price calculation

**Checkpoint**: All 3 French spiders produce `RawListing` with `bedrooms` = pièces; DVF enricher returns transaction data for Paris listings.

---

## Phase 5: User Story 3 — UK Listings (Priority: P2)

**Goal**: Rightmove spider captures GBP prices (with EUR normalization), council tax band, EPC rating, and tenure; UKLandRegistryEnricher matches ≥70% of London listings to historical transactions.

**Independent Test**: Run Rightmove spider for 5 pages in London. Confirm `original_price` in GBP and `asking_price` in EUR both populated; `tenure` present on ≥70% of listings. Run Land Registry enricher; confirm ≥70% match rate.

### Tests for User Story 3

- [X] T048 [P] [US3] Create `services/spider-workers/tests/fixtures/gb_rightmove_search.html` — mock Rightmove search results page with JSON-LD blocks plus `.dp-council-tax`, `.dp-epc-rating`, `.dp-tenure` sections
- [X] T049 [P] [US3] Create `services/pipeline/tests/enricher/fixtures/uk_pp_sample.sql` — seed SQL with 100 UK Price Paid rows for London postcodes, covering leasehold and freehold

### Implementation for User Story 3 — Spider

- [X] T050 [P] [US3] Create `services/pipeline/config/mappings/gb_rightmove.yaml` — field mapping: JSON-LD `offers.price`→asking_price, `numberOfRooms`→bedrooms, `floorSize.value`→built_area_m2; CSS selector targets for `council_tax_band`, `epc_rating`, `tenure`, `leasehold_years_remaining`; set `currency_field: GBP`; `expected_fields` includes UK-specific fields
- [X] T051 [P] [US3] Create `services/spider-workers/estategap_spiders/spiders/gb_rightmove_parser.py` — `parse_json_ld(html: str) -> dict`; `parse_uk_fields(soup: BeautifulSoup) -> dict` extracting council_tax_band, epc_rating, tenure, leasehold_years_remaining from CSS selectors
- [X] T052 [US3] Create `services/spider-workers/estategap_spiders/spiders/gb_rightmove.py` — `RightmoveSpider(BaseSpider)` with `COUNTRY="GB"`, `PORTAL="rightmove"`; httpx + BeautifulSoup; extract JSON-LD for core fields, CSS selectors for UK-specific fields; set `currency="GBP"` and `original_price` in raw_json; implement all 3 abstract methods
- [X] T053 [US3] Register `RightmoveSpider` in `services/spider-workers/estategap_spiders/spiders/__init__.py`

### Implementation for User Story 3 — Land Registry Enricher

- [X] T054 [US3] Create `scripts/import_uk_land_registry.py` — CLI script: downloads Price Paid Data complete CSV from gov.uk, streams via `csv.reader`, bulk-inserts to `uk_price_paid` via asyncpg; computes `address_normalized` column; supports `--complete` and `--monthly YYYY-MM` args; idempotent via `ON CONFLICT (transaction_uid) DO NOTHING`
- [X] T055 [US3] Create `services/pipeline/src/pipeline/enricher/gb_land_registry.py` — `UKLandRegistryEnricher(BaseEnricher)` decorated with `@register_enricher("GB")`; implement `enrich()`: query `uk_price_paid` by `postcode`, apply `rapidfuzz.fuzz.token_sort_ratio` on `address_normalized` vs listing address (threshold ≥90), return `EnrichmentResult` with `uk_lr_match_count`, `uk_lr_last_price_gbp`, `uk_lr_last_date`
- [X] T056 [US3] Register `UKLandRegistryEnricher` in `services/pipeline/src/pipeline/enricher/__init__.py`
- [X] T057 [US3] Create `services/spider-workers/tests/spiders/test_gb_rightmove.py` — unit tests: test JSON-LD price in GBP captured, test CSS selector extraction of council_tax_band/epc_rating/tenure, test leasehold_years_remaining nullable path
- [X] T058 [US3] Create `services/pipeline/tests/enricher/test_gb_land_registry.py` — unit tests: test rapidfuzz match at threshold 90, test `no_match` for unrecognized address, test match returns most recent transaction date

**Checkpoint**: Rightmove listings have GBP+EUR prices and UK-specific fields; Land Registry enricher matches addresses with ≥90 similarity.

---

## Phase 6: User Story 4 — Dutch Listings (Priority: P2)

**Goal**: Funda spider scrapes Dutch listings at ≤0.5 req/s; NetherlandsBAGEnricher attaches official building data (year_built, official_area_m2) from the Dutch government PDOK WFS API.

**Independent Test**: Run Funda spider for 3 pages in Amsterdam with timing assertions. Confirm request interval ≥2s. Run BAG enricher on 20 listings with known postcodes; confirm `year_built` populated on ≥80%.

### Tests for User Story 4

- [X] T059 [P] [US4] Create `services/spider-workers/tests/fixtures/nl_funda_search.html` — mock Funda search results page with Nuxt embedded JSON in `<script id="nuxt-data">` containing 3 listings including `bag_id`, `constructionYear`, `livingArea`
- [X] T060 [P] [US4] Create `services/pipeline/tests/enricher/fixtures/pdok_response.xml` — mock PDOK WFS `GetFeature` XML response for a single BAG pand record

### Implementation for User Story 4 — Spider

- [X] T061 [P] [US4] Create `services/pipeline/config/mappings/nl_funda.yaml` — field mapping: `price.amount`→asking_price (EUR), `livingArea`→built_area_m2, `numberOfRooms`→bedrooms, `constructionYear`→year_built, `energyLabel`→energy_rating, `bag_id`→bag_id (pass-through for enricher), `latitude/longitude`→coordinates; property_type_map for Dutch types (appartement, woning, villa, etc.)
- [X] T062 [P] [US4] Create `services/spider-workers/estategap_spiders/spiders/nl_funda_parser.py` — `extract_nuxt_data(html: str) -> dict` using regex on `<script id="nuxt-data">`; `parse_listing(item: dict) -> dict`
- [X] T063 [US4] Create `services/spider-workers/estategap_spiders/spiders/nl_funda.py` — `FundaSpider(BaseSpider)` with `COUNTRY="NL"`, `PORTAL="funda"`; httpx requests with enforced `asyncio.sleep(2.0)` between requests (rate limit 0.5 req/s); extract Nuxt embedded JSON via parser; implement all 3 abstract methods
- [X] T064 [US4] Register `FundaSpider` in `services/spider-workers/estategap_spiders/spiders/__init__.py`

### Implementation for User Story 4 — BAG Enricher

- [X] T065 [US4] Create `services/pipeline/src/pipeline/enricher/nl_bag.py` — `NetherlandsBAGEnricher(BaseEnricher)` decorated with `@register_enricher("NL")`; implement `enrich()`: if `listing.bag_id` is set, use direct BAG ID WFS lookup; otherwise use address+postcode lookup; query PDOK WFS `https://service.pdok.nl/lv/bag/wfs/v2_0`; parse XML response for `bouwjaar`, `oppervlakte`, `gebruiksdoel`, geometry; respect rate limit via `asyncio.Semaphore(10)`; return `EnrichmentResult` with `year_built`, `official_area_m2`, `bag_id`, `building_geometry_wkt`
- [X] T066 [US4] Register `NetherlandsBAGEnricher` in `services/pipeline/src/pipeline/enricher/__init__.py`
- [X] T067 [US4] Create `services/spider-workers/tests/spiders/test_nl_funda.py` — unit tests: test Nuxt JSON extraction, test field mapping, test rate-limiting assertion (mock sleep, verify call count)
- [X] T068 [US4] Create `services/pipeline/tests/enricher/test_nl_bag.py` — unit tests with mocked httpx: test BAG ID direct lookup path, test address fallback path, test XML parsing of PDOK response, test `no_match` when PDOK returns empty FeatureCollection

**Checkpoint**: Funda spider enforces ≥2s between requests; BAG enricher attaches `year_built` and `official_area_m2` to Dutch listings.

---

## Phase 7: User Story 5 — Zone Hierarchy Navigation (Priority: P3)

**Goal**: GADM administrative zones for Italy, France, UK, and Netherlands are imported into the `zones` table with 3–4-level hierarchy; zones API returns correct structure per country.

**Independent Test**: Import GADM fixture for France. Query `GET /zones?country=FR&level=1`; confirm 13 metropolitan regions returned with geometry. Query `GET /zones?country=IT&level=2`; confirm 107 provinces.

### Tests for User Story 5

- [X] T069 [P] [US5] Create `services/pipeline/tests/integration/fixtures/gadm_fr_sample.geojson` — 3-region subset of France GADM level-1 data for import script tests
- [X] T070 [P] [US5] Create `services/pipeline/tests/integration/test_gadm_import.py` — integration test using testcontainers: run import script against sample GeoJSON fixture, verify zone count and hierarchy, test idempotency (run twice, same count)

### Implementation for User Story 5

- [X] T071 [US5] Create `scripts/import_gadm_zones.py` — CLI: `--country` (IT/FR/GB/NL), `--file` (path to GADM GeoPackage); uses geopandas `gpd.read_file()`, reprojects to SRID 4326, computes area_km2 (EPSG:3035), generates `slug` from `{country_code}-{name_path}`, builds parent_id hierarchy (level_0 → level_1 → level_2 → level_3), bulk-inserts via asyncpg with `ON CONFLICT (slug) DO UPDATE`; applies `LEVEL_MAP` per country (see plan.md §1.4)
- [X] T072 [US5] Add `country_uses_pieces` and GADM level map constants for NL 3-level hierarchy to `scripts/import_gadm_zones.py` (Netherlands has no level_3; gemeente = city = level_2)
- [X] T073 [US5] Add ItalyOMIEnricher: create `services/pipeline/src/pipeline/enricher/it_omi.py` — `ItalyOMIEnricher(BaseEnricher)` decorated with `@register_enricher("IT")`; implement `enrich()`: query `omi_zones` via `ST_Within(ST_SetSRID(ST_MakePoint($lon,$lat),4326), geometry)` filtering by `tipologia` matching listing property_type and latest `period`; return `EnrichmentResult` with `omi_zone_code`, `omi_price_min_eur_m2`, `omi_price_max_eur_m2`, `omi_period`, `price_vs_omi`
- [X] T074 [US5] Register `ItalyOMIEnricher` in `services/pipeline/src/pipeline/enricher/__init__.py`
- [X] T075 [US5] Create `scripts/import_omi.py` — CLI: `--period` (e.g., `2024-H2`); downloads OMI CSV/XLS from Agenzia delle Entrate open data portal, parses zona_omi code, comune ISTAT, tipologia, price_min, price_max; imports to `omi_zones`; idempotent via `ON CONFLICT (zona_omi, period, tipologia) DO UPDATE`
- [X] T076 [US5] Create `services/pipeline/tests/enricher/test_it_omi.py` — unit tests: test ST_Within zone match, test `tipologia` mapping from listing property_type, test `price_vs_omi` calculation, test `no_match` for listing outside all OMI zones

**Checkpoint**: GADM zones for all 4 countries importable; zones API returns correct hierarchy; ItalyOMIEnricher attaches price band to IT listings.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T077 [P] Create `scripts/check_completeness.py` — QA script: connects to DB, queries per-portal completeness scores (populated fields / expected_fields), prints pass/fail per portal vs the ≥75% threshold
- [X] T078 [P] Create `scripts/check_enrichment_rate.py` — QA script: queries enrichment coverage per country/city/enricher type, prints pass/fail vs acceptance thresholds (DVF ≥60% Paris, UK LR ≥70% London)
- [X] T079 [P] Create `services/pipeline/tests/integration/test_eu_pipeline_it.py` — end-to-end integration test (testcontainers): simulate IT listing ingestion → normalization → OMI enrichment → verify enriched fields on listing record
- [X] T080 [P] Create `services/pipeline/tests/integration/test_eu_pipeline_fr.py` — end-to-end: FR listing → DVF enrichment → verify `dvf_nearby_count` populated
- [X] T081 [P] Create `services/pipeline/tests/integration/test_eu_pipeline_gb.py` — end-to-end: GB listing → Land Registry enrichment → verify `uk_lr_last_price_gbp` populated
- [X] T082 [P] Create `services/pipeline/tests/integration/test_eu_pipeline_nl.py` — end-to-end: NL listing → BAG enrichment (PDOK mock) → verify `year_built` and `official_area_m2` populated
- [X] T083 Add `IMMOBILIARE_API_TOKEN` and `IDEALISTA_IT_API_TOKEN` environment variable references to `services/spider-workers/estategap_spiders/config.py` following the existing `idealista_api_token` pattern
- [ ] T084 Run `uv run ruff check .` and `uv run mypy .` across `services/spider-workers/` and `services/pipeline/`; fix all reported issues
- [ ] T085 Run full test suite: `uv run pytest tests/ -v` in both `services/spider-workers/` and `services/pipeline/`; confirm all tests pass

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately; T005, T006, T007 can run in parallel with T004
- **Phase 2 (Foundational)**: Depends on Phase 1 completion (T008 must run after T004–T007)
- **Phase 3 (US1 — Italy)**: Depends on Phase 2; T018–T021 can run in parallel; T022/T023 depend on their parsers (T020/T021)
- **Phase 4 (US2 — France)**: Depends on Phase 2; T031–T036 can run in parallel; T037–T039 depend on their parsers; T042 depends on T041
- **Phase 5 (US3 — UK)**: Depends on Phase 2; T050/T051 parallel; T052 depends on T051; T055 depends on T054
- **Phase 6 (US4 — Netherlands)**: Depends on Phase 2; T061/T062 parallel; T063 depends on T062; T065 depends on T060
- **Phase 7 (US5 — Zones)**: Depends on Phase 1 (migrations); T071/T072 can start independently of US1–US4 after T008
- **Phase 8 (Polish)**: Depends on all prior phases; T079–T082 parallel with each other

### User Story Dependencies

| Story | Depends On | Can Parallelize With |
|-------|-----------|---------------------|
| US1 (Italy) | Phase 2 | US2, US3, US4, US5 |
| US2 (France) | Phase 2 | US1, US3, US4, US5 |
| US3 (UK) | Phase 2 | US1, US2, US4, US5 |
| US4 (Netherlands) | Phase 2 | US1, US2, US3, US5 |
| US5 (Zones) | T008 (migrations) | US1, US2, US3, US4 |

### Within Each User Story

- YAML mapping → parser module → spider class (sequential)
- Import script → enricher → register (sequential)
- Tests can be written at any point but should fail before implementation

---

## Parallel Examples

### Running US1 (Italy) Setup Tasks in Parallel

```bash
# These tasks have no interdependency:
Task T018: "Create it_immobiliare.yaml mapping"
Task T019: "Create it_idealista.yaml mapping"
Task T020: "Create it_immobiliare_parser.py"
Task T021: "Create it_idealista_parser.py"
Task T015: "Create fixture it_immobiliare_search.json"
Task T016: "Create fixture it_immobiliare_detail.html"
Task T017: "Create fixture it_idealista_search.json"
```

### Running French Spider Setup in Parallel (US2)

```bash
Task T031: "Create fr_seloger.yaml"
Task T032: "Create fr_leboncoin.yaml"
Task T033: "Create fr_bienici.yaml"
Task T034: "Create fr_seloger_parser.py"
Task T035: "Create fr_leboncoin_parser.py"
Task T036: "Create fr_bienici_parser.py"
```

### Running Phase 8 Integration Tests in Parallel

```bash
Task T079: "Integration test EU pipeline Italy"
Task T080: "Integration test EU pipeline France"
Task T081: "Integration test EU pipeline UK"
Task T082: "Integration test EU pipeline Netherlands"
```

---

## Implementation Strategy

### MVP First (US1 — Italian Listings Only)

1. Complete Phase 1: Setup (T001–T009)
2. Complete Phase 2: Foundational (T010–T014)
3. Complete Phase 3: US1 Italy (T015–T026)
4. **STOP AND VALIDATE**: Run Italian spiders, confirm ≥75% completeness
5. Demo: Italian listings browsable on dashboard

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. US1 (Italy) → 2 portals live; Italian market operational
3. US2 (France) → 3 more portals + DVF enrichment live
4. US3 (UK) → Rightmove + Land Registry live; GBP pricing working
5. US4 (Netherlands) → Funda + BAG enrichment live
6. US5 (Zones) → Zone hierarchies for all 4 countries browsable
7. Polish → QA scripts, integration tests, linting

### Parallel Team Strategy

With 4 developers after Phase 2:
- Dev A: US1 (Italy) — T015–T026
- Dev B: US2 (France spiders) — T027–T046
- Dev C: US3 (UK) — T047–T058
- Dev D: US4 (Netherlands) + US5 (Zones) — T059–T076

---

## Notes

- [P] tasks target different files with no blocking predecessor in the same phase
- `country_uses_pieces: true` in YAML is the only config change needed for pièces→bedrooms mapping; the normalizer reads this flag automatically
- Funda's rate limit is enforced in the spider, not in config — hardcode `asyncio.sleep(2.0)` per request cycle
- DVF and UK Land Registry bulk import scripts are one-time/monthly jobs; run them as Kubernetes Jobs (not long-running services)
- All enricher `enrich()` methods MUST NOT raise exceptions — catch all errors and return `EnrichmentResult(status="failed", error=str(e))`
- Test fixtures (HTML/JSON) should represent real portal response shapes but with anonymized/synthetic data
